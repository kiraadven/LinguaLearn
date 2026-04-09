"""
GraphAssembler - Converts offline lesson plans into initial LessonGraphs.

The offline plan provides ordered segments with skills and depth levels.
The assembler selects templates, creates a linear backbone with branching,
and resolves content for each node.
"""

from __future__ import annotations
import uuid
from typing import Optional

from .schema import LiveNode, EdgeSpec
from .graph_engine import LessonGraph
from .node_templates import NodeTemplateLibrary
from .content_connector import ContentConnector


class GraphAssembler:

    def __init__(
        self,
        template_library: NodeTemplateLibrary,
        content_connector: ContentConnector,
    ):
        self._templates = template_library
        self._content = content_connector

    def assemble(
        self,
        lesson_plan: list[dict],
        lesson_objectives: list[str],
        policy_package: Optional[dict] = None,
        voice_defaults: Optional[dict] = None,
    ) -> LessonGraph:
        """Build an initial LessonGraph from an offline lesson plan.

        Args:
            lesson_plan: List of segment dicts, each with:
                - skill: str
                - depth: "light" | "standard" | "deep"
                - node_types: list[str] (optional, auto-selected if missing)
                - content_pack: dict (optional, resolved if missing)
            lesson_objectives: Global learning objectives
            policy_package: Policy configuration (optional)
            voice_defaults: Default voice/delivery settings (optional)

        Returns:
            Fully connected LessonGraph ready for runtime.
        """
        graph = LessonGraph()
        graph.graph_id = f"lesson_{uuid.uuid4().hex[:8]}"
        graph.lesson_objectives = lesson_objectives

        all_nodes: list[LiveNode] = []

        # --- Phase 1: Hook node ---
        hook = self._create_phase_node("hook", "intro", lesson_objectives, lesson_plan)
        all_nodes.append(hook)

        # --- Phase 2: Per-segment nodes ---
        for i, segment in enumerate(lesson_plan):
            skill = segment["skill"]
            depth = segment.get("depth", "standard")
            node_types = segment.get("node_types") or self._default_types_for_depth(depth)

            for node_type in node_types:
                content = segment.get("content_pack") or self._content.resolve(
                    skill, node_type,
                )
                node = self._create_segment_node(node_type, skill, content, i)
                all_nodes.append(node)

        # --- Phase 3: Wrap-up node ---
        wrapup = self._create_phase_node("wrap_up", "review", lesson_objectives, lesson_plan)
        all_nodes.append(wrapup)

        # --- Add all nodes to graph ---
        for node in all_nodes:
            graph.add_node(node)

        # --- Build edges: linear backbone + branching ---
        for i in range(len(all_nodes) - 1):
            current = all_nodes[i]
            next_node = all_nodes[i + 1]

            # Main success path
            graph.add_edge(EdgeSpec(
                current.node_id, next_node.node_id,
                event="on_success", weight=1.0, priority=5,
            ))

            # Auto-advance for non-interactive nodes
            if current.node_type in ("hook", "explain", "transition", "wrap_up"):
                graph.add_edge(EdgeSpec(
                    current.node_id, next_node.node_id,
                    event="auto_advance", weight=0.8, priority=3,
                ))

            # Error handling: minor error stays, major error goes back
            if current.node_type in ("guided_practice", "free_practice", "check_understanding"):
                # Minor error: retry current node (self-loop hint)
                graph.add_edge(EdgeSpec(
                    current.node_id, current.node_id,
                    event="on_minor_error", weight=1.5, priority=3,
                ))
                # Major error: go back one node for re-explanation
                if i > 0:
                    prev_node = all_nodes[i - 1]
                    graph.add_edge(EdgeSpec(
                        current.node_id, prev_node.node_id,
                        event="on_major_error", weight=2.0, priority=2,
                    ))

            # Silence handling
            graph.add_edge(EdgeSpec(
                current.node_id, current.node_id,
                event="on_silence", weight=1.8, priority=1,
            ))

        # --- Set start node ---
        graph.start_node_id = all_nodes[0].node_id
        graph.current_node_id = all_nodes[0].node_id
        all_nodes[0].status = "active"
        all_nodes[0].visit_count = 1

        return graph

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_types_for_depth(depth: str) -> list[str]:
        if depth == "light":
            return ["explain", "check_understanding"]
        elif depth == "deep":
            return ["explain", "worked_example", "guided_practice",
                    "free_practice", "check_understanding"]
        else:  # standard
            return ["explain", "guided_practice", "check_understanding"]

    def _create_phase_node(
        self, node_type: str, phase: str,
        objectives: list[str], plan: list[dict],
    ) -> LiveNode:
        templates = self._templates.query(node_type=node_type, phase=phase)
        if templates:
            return self._templates.instantiate(
                templates[0].template_id,
                params={
                    "learning_targets": objectives,
                    "skill": ", ".join(objectives),
                    "content_pack": {},
                    "title": f"{node_type.replace('_', ' ').title()}",
                },
            )
        return LiveNode(
            node_id=f"{node_type}_{uuid.uuid4().hex[:8]}",
            template_id=f"{node_type}_default",
            node_type=node_type,
            phase=phase,
            title=f"{node_type.replace('_', ' ').title()}",
            learning_targets=objectives,
            teacher_goal=f"{node_type} for lesson",
            expected_student_evidence=[],
            policy_profile={"allowed_actions": ["encourage", "advance"], "failure_budget": 1},
        )

    def _create_segment_node(
        self, node_type: str, skill: str,
        content: dict, segment_idx: int,
    ) -> LiveNode:
        phase = self._type_to_phase(node_type)
        templates = self._templates.query(node_type=node_type, phase=phase)
        if templates:
            return self._templates.instantiate(
                templates[0].template_id,
                params={
                    "learning_targets": [skill],
                    "skill": skill,
                    "content_pack": content,
                    "title": f"{node_type.replace('_', ' ').title()}: {skill}",
                },
            )
        return LiveNode(
            node_id=f"{node_type}_{segment_idx}_{uuid.uuid4().hex[:6]}",
            template_id=f"{node_type}_default",
            node_type=node_type,
            phase=phase,
            title=f"{node_type.replace('_', ' ').title()}: {skill}",
            learning_targets=[skill],
            teacher_goal=f"{node_type} for {skill}",
            expected_student_evidence=["student_response"],
            content_pack=content,
            policy_profile={
                "allowed_actions": [
                    "ask_open", "hint_light", "re_explain_brief",
                    "direct_correct", "encourage",
                ],
                "default_style": "neutral_teach",
                "failure_budget": 2,
            },
        )

    @staticmethod
    def _type_to_phase(node_type: str) -> str:
        mapping = {
            "hook": "intro",
            "explain": "present",
            "worked_example": "present",
            "guided_practice": "practice",
            "free_practice": "produce",
            "check_understanding": "practice",
            "repair": "practice",
            "review": "review",
            "transition": "present",
            "wrap_up": "review",
        }
        return mapping.get(node_type, "practice")
