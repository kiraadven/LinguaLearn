"""
LessonGraph - NetworkX-backed live lesson graph.

The central runtime artifact. Every other component reads from or writes to
this graph. Supports construction, traversal, subgraph insertion, edge weight
updates, and mutation logging for WebSocket diff broadcasting.
"""

from __future__ import annotations
import time
from typing import Optional

import networkx as nx

from .schema import LiveNode, EdgeSpec, SubgraphSpec, GraphMutation


class LessonGraph:

    def __init__(self):
        self.G: nx.DiGraph = nx.DiGraph()
        self.current_node_id: Optional[str] = None
        self.start_node_id: Optional[str] = None
        self.graph_id: str = ""
        self.lesson_objectives: list[str] = []
        self._version: int = 0
        self._mutation_log: list[GraphMutation] = []

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def add_node(self, node: LiveNode) -> None:
        self.G.add_node(node.node_id, data=node)
        self._log("add_node", {
            "node_id": node.node_id,
            "node_type": node.node_type,
            "title": node.title,
            "phase": node.phase,
            "learning_targets": node.learning_targets,
        })

    def add_edge(self, edge: EdgeSpec) -> None:
        self.G.add_edge(
            edge.source_id, edge.target_id,
            event=edge.event,
            weight=edge.weight,
            priority=edge.priority,
            conditions=edge.conditions,
        )
        self._log("add_edge", {
            "source": edge.source_id,
            "target": edge.target_id,
            "event": edge.event,
            "weight": edge.weight,
        })

    def remove_node(self, node_id: str) -> None:
        self.G.remove_node(node_id)
        self._log("remove_node", {"node_id": node_id})

    def remove_edge(self, source_id: str, target_id: str) -> None:
        self.G.remove_edge(source_id, target_id)
        self._log("remove_edge", {"source": source_id, "target": target_id})

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> LiveNode:
        return self.G.nodes[node_id]["data"]

    def get_current_node(self) -> LiveNode:
        if self.current_node_id is None:
            raise RuntimeError("No current node set")
        return self.get_node(self.current_node_id)

    def get_outgoing_edges(self, node_id: str) -> list[dict]:
        """Return all outgoing edges for a node, sorted by priority (desc)."""
        edges = []
        for _, target, data in self.G.out_edges(node_id, data=True):
            edges.append({"target": target, **data})
        edges.sort(key=lambda e: e.get("priority", 0), reverse=True)
        return edges

    def resolve_transition(self, node_id: str, event: str,
                           context: Optional[dict] = None) -> Optional[str]:
        """Given an event and optional context, find the best target node.

        Evaluates edges matching the event, checks guard conditions,
        returns target_node_id with highest priority and lowest weight.
        Returns None if no matching edge found.
        """
        context = context or {}
        candidates = []

        for _, target, data in self.G.out_edges(node_id, data=True):
            if data.get("event") != event:
                continue
            # Check guard conditions
            conditions = data.get("conditions", {})
            if not self._evaluate_conditions(conditions, context):
                continue
            candidates.append((
                data.get("priority", 0),
                -data.get("weight", 1.0),  # negate so lower weight is preferred
                target,
            ))

        if not candidates:
            return None

        # Sort by priority desc, then by weight asc (negated, so desc)
        candidates.sort(reverse=True)
        return candidates[0][2]

    def advance_to(self, target_node_id: str) -> LiveNode:
        """Move current_node_id to target. Mark old node completed."""
        if self.current_node_id is not None:
            old = self.get_node(self.current_node_id)
            if old.status == "active":
                old.status = "completed"
                self._log("update_node_status", {
                    "node_id": old.node_id, "status": "completed",
                })

        self.current_node_id = target_node_id
        new_node = self.get_node(target_node_id)
        new_node.status = "active"
        new_node.visit_count += 1
        self._log("move_cursor", {
            "from": self.current_node_id,
            "to": target_node_id,
        })
        return new_node

    # ------------------------------------------------------------------
    # Subgraph insertion
    # ------------------------------------------------------------------

    def insert_subgraph(self, subgraph: SubgraphSpec,
                        attach_after: str, return_to: str) -> list[str]:
        """Insert a subgraph between attach_after and return_to.

        Mechanical steps:
        1. Remove direct edge attach_after -> return_to (if exists)
        2. Add all subgraph nodes to G
        3. Add entry edge: attach_after -> subgraph.entry_node_id
        4. Add exit edge: subgraph.exit_node_id -> return_to
        5. Add all internal subgraph edges
        6. Log as single insert_subgraph mutation

        Returns list of new node IDs added.
        """
        # Step 1: remove direct edge if exists
        if self.G.has_edge(attach_after, return_to):
            self.G.remove_edge(attach_after, return_to)

        # Step 2: add subgraph nodes
        new_node_ids = []
        for node in subgraph.nodes:
            node.inserted_at = time.time()
            node.subgraph_origin = subgraph.subgraph_id
            self.G.add_node(node.node_id, data=node)
            new_node_ids.append(node.node_id)

        # Step 3: entry edge
        self.G.add_edge(
            attach_after, subgraph.entry_node_id,
            event=f"on_{subgraph.purpose}",
            weight=0.5,  # high priority (low weight)
            priority=10,
            conditions={},
        )

        # Step 4: exit edge
        self.G.add_edge(
            subgraph.exit_node_id, return_to,
            event="on_success",
            weight=1.0,
            priority=5,
            conditions={},
        )

        # Step 5: internal edges
        for edge in subgraph.edges:
            self.G.add_edge(
                edge.source_id, edge.target_id,
                event=edge.event,
                weight=edge.weight,
                priority=edge.priority,
                conditions=edge.conditions,
            )

        # Step 6: log
        self._log("insert_subgraph", {
            "subgraph_id": subgraph.subgraph_id,
            "purpose": subgraph.purpose,
            "attach_after": attach_after,
            "return_to": return_to,
            "new_node_ids": new_node_ids,
            "entry": subgraph.entry_node_id,
            "exit": subgraph.exit_node_id,
        })

        return new_node_ids

    def remove_subgraph(self, subgraph_id: str, reconnect_from: str,
                        reconnect_to: str) -> None:
        """Remove a previously inserted subgraph. Reconnect broken edges."""
        nodes_to_remove = [
            nid for nid, data in self.G.nodes(data=True)
            if data.get("data") and data["data"].subgraph_origin == subgraph_id
        ]
        for nid in nodes_to_remove:
            self.G.remove_node(nid)

        # Reconnect
        self.G.add_edge(
            reconnect_from, reconnect_to,
            event="auto_advance", weight=1.0, priority=0, conditions={},
        )
        self._log("remove_subgraph", {
            "subgraph_id": subgraph_id,
            "removed_nodes": nodes_to_remove,
        })

    # ------------------------------------------------------------------
    # Weight management
    # ------------------------------------------------------------------

    def update_edge_weight(self, source_id: str, target_id: str,
                           new_weight: float) -> None:
        if self.G.has_edge(source_id, target_id):
            self.G[source_id][target_id]["weight"] = new_weight
            self._log("update_edge_weight", {
                "source": source_id, "target": target_id, "weight": new_weight,
            })

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_snapshot(self) -> dict:
        """Full graph state for initial WS push or reconnect."""
        nodes = []
        for nid, data in self.G.nodes(data=True):
            n: LiveNode = data["data"]
            nodes.append({
                "node_id": n.node_id,
                "node_type": n.node_type,
                "title": n.title,
                "status": n.status,
                "phase": n.phase,
                "learning_targets": n.learning_targets,
                "visit_count": n.visit_count,
                "success_count": n.success_count,
                "failure_count": n.failure_count,
            })

        edges = []
        for src, tgt, data in self.G.edges(data=True):
            edges.append({
                "source": src,
                "target": tgt,
                "event": data.get("event", ""),
                "weight": data.get("weight", 1.0),
                "is_active": src == self.current_node_id,
            })

        completed = sum(1 for n in nodes if n["status"] == "completed")
        return {
            "graph_id": self.graph_id,
            "version": self._version,
            "current_node_id": self.current_node_id,
            "nodes": nodes,
            "edges": edges,
            "lesson_objectives": self.lesson_objectives,
            "progress": {
                "completed_nodes": completed,
                "total_nodes": len(nodes),
            },
        }

    def drain_mutations(self) -> list[dict]:
        """Return and clear the mutation log. Used by WS server for diff broadcast."""
        mutations = [{"op": m.op, "data": m.data} for m in self._mutation_log]
        self._mutation_log.clear()
        return mutations

    @property
    def version(self) -> int:
        return self._version

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_path_to(self, target_node_id: str) -> list[str]:
        """Shortest path from current node to target."""
        if self.current_node_id is None:
            return []
        try:
            return nx.shortest_path(self.G, self.current_node_id, target_node_id)
        except nx.NetworkXNoPath:
            return []

    def get_nodes_by_status(self, status: str) -> list[str]:
        return [
            nid for nid, data in self.G.nodes(data=True)
            if data.get("data") and data["data"].status == status
        ]

    def get_nodes_by_skill(self, skill: str) -> list[str]:
        return [
            nid for nid, data in self.G.nodes(data=True)
            if data.get("data") and skill in data["data"].learning_targets
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _log(self, op: str, data: dict) -> None:
        self._mutation_log.append(GraphMutation(op=op, data=data))
        self._version += 1

    @staticmethod
    def _evaluate_conditions(conditions: dict, context: dict) -> bool:
        """Evaluate guard conditions against context.
        Simple key-value matching for now."""
        for key, expected in conditions.items():
            if context.get(key) != expected:
                return False
        return True
