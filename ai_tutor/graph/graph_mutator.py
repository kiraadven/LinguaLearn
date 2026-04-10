"""
GraphMutator - Applies memory-driven mutations to the lesson graph.

Called after every turn by the SessionOrchestrator.
Decision logic is RULE-BASED (no LLM involvement).

Mutation types:
1. Insert repair subgraph (student failed a skill)
2. Insert backtrack subgraph (student asks about earlier content)
3. Insert enrichment subgraph (student excelling)
4. Adjust edge weights (based on mastery/engagement/fatigue)
5. Skip nodes (student already mastered content)
"""

from __future__ import annotations
from typing import Optional

from .graph_engine import LessonGraph
from .subgraph_factory import SubgraphFactory
from .edge_weights import EdgeWeightComputer
from .content_connector import ContentConnector


class GraphMutator:

    def __init__(
        self,
        graph: LessonGraph,
        subgraph_factory: SubgraphFactory,
        edge_weight_computer: EdgeWeightComputer,
        content_connector: ContentConnector,
    ):
        self._graph = graph
        self._subgraph_factory = subgraph_factory
        self._edge_weights = edge_weight_computer
        self._content = content_connector

    def apply_mutations(self, signals: dict) -> list[dict]:
        """Apply graph mutations based on memory signals.

        Args:
            signals: from MemoryManager.get_graph_mutation_signals(), containing:
                - should_repair: bool
                - repair_skill: str
                - should_backtrack: bool
                - backtrack_target: str (node_id of the node to revisit)
                - backtrack_skill: str
                - should_enrich: bool
                - enrich_skill: str
                - should_slow_down: bool
                - edge_weight_adjustments: list[dict]
                - fatigue: float
                - engagement: float
                - mastery: dict[str, float]
                - consecutive_failures: int
                - error_severity: float
                - time_pressure: float

        Returns:
            List of mutation dicts applied (for WS broadcasting).
            Max one subgraph insertion per turn to prevent graph explosion.
        """
        current_id = self._graph.current_node_id
        if current_id is None:
            return []

        mutations_before = self._graph.version

        # Priority: repair > backtrack > enrichment (only one per turn)
        subgraph_inserted = False

        if signals.get("should_repair") and not subgraph_inserted:
            subgraph_inserted = self._try_insert_repair(
                signals["repair_skill"], current_id,
            )

        if signals.get("should_backtrack") and not subgraph_inserted:
            subgraph_inserted = self._try_insert_backtrack(
                signals.get("backtrack_skill", ""),
                signals.get("backtrack_target", ""),
                current_id,
            )

        if signals.get("should_enrich") and not subgraph_inserted:
            subgraph_inserted = self._try_insert_enrichment(
                signals["enrich_skill"], current_id,
            )

        # Always update edge weights
        self._update_edge_weights(current_id, signals)

        return self._graph.drain_mutations()

    # ------------------------------------------------------------------
    # Private mutation methods
    # ------------------------------------------------------------------

    def _try_insert_repair(self, skill: str, current_id: str) -> bool:
        content = self._content.resolve(skill, "repair")
        subgraph = self._subgraph_factory.build_repair_subgraph(
            failed_skill=skill,
            original_node_id=current_id,
            content_pack=content,
            depth="standard",
        )
        self._graph.insert_subgraph(subgraph, attach_after=current_id, return_to=current_id)
        return True

    def _try_insert_backtrack(self, skill: str, target_node_id: str,
                              current_id: str) -> bool:
        if not skill:
            return False
        content = self._content.resolve(skill, "review")
        subgraph = self._subgraph_factory.build_backtrack_subgraph(
            target_skill=skill,
            previous_node_id=target_node_id,
            content_pack=content,
        )
        self._graph.insert_subgraph(subgraph, attach_after=current_id, return_to=current_id)
        return True

    def _try_insert_enrichment(self, skill: str, current_id: str) -> bool:
        content = self._content.resolve(skill, "enrichment")
        # Find the next node to attach enrichment before
        edges = self._graph.get_outgoing_edges(current_id)
        next_id: Optional[str] = None
        for e in edges:
            if e.get("event") == "on_success":
                next_id = e["target"]
                break
        if next_id is None:
            return False

        subgraph = self._subgraph_factory.build_enrichment_subgraph(
            skill=skill, content_pack=content,
        )
        self._graph.insert_subgraph(subgraph, attach_after=current_id, return_to=next_id)
        return True

    def _update_edge_weights(self, current_id: str, signals: dict) -> None:
        weight_map = self._edge_weights.compute_weights(
            self._graph, current_id, signals,
        )
        for (src, tgt, edge_key), weight in weight_map.items():
            self._graph.update_edge_weight(src, tgt, weight, edge_key=edge_key)
