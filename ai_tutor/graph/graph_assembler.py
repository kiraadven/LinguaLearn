"""
GraphAssembler - Converts offline lesson plans into initial LessonGraphs.

The offline plan provides ordered segments with skills and depth levels.
The assembler selects templates, creates a linear backbone with branching,
and resolves content for each node.
"""

from __future__ import annotations
import uuid
from typing import Optional

from .schema import LiveNode, EdgeSpec, normalize_content_pack
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
        warm_up = self._create_phase_node("warm_up", "intro", lesson_objectives, lesson_plan)
        all_nodes.append(warm_up)

        # --- Phase 2: Per-segment nodes ---
        for i, segment in enumerate(lesson_plan):
            skill = segment["skill"]
            skill_type = str(segment.get("skill_type", "")).strip().lower()
            depth = segment.get("depth", "standard")
            node_types = segment.get("node_types") or self._default_types_for_depth(depth)

            for node_type in node_types:
                raw_content = segment.get("content_pack")
                if isinstance(raw_content, dict) and raw_content:
                    content = normalize_content_pack(
                        raw_content,
                        node_type=node_type,
                        source_lang=str(segment.get("source_lang", "")),
                        target_lang=str(segment.get("target_lang", "")),
                    )
                else:
                    content = self._content.resolve(skill, node_type)
                node = self._create_segment_node(
                    node_type=node_type,
                    skill=skill,
                    content=content,
                    segment_idx=i,
                    skill_type=skill_type,
                )
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
            if current.node_type in ("hook", "explain", "cultural_note", "transition", "wrap_up"):
                graph.add_edge(EdgeSpec(
                    current.node_id, next_node.node_id,
                    event="auto_advance", weight=0.8, priority=3,
                ))

            # Error handling: minor error stays, major error goes back
            if current.node_type in (
                "guided_practice",
                "free_practice",
                "check_understanding",
                "vocabulary_focus",
                "pronunciation_drill",
                "listening_comprehension",
                "reading_comprehension",
                "dialogue_practice",
                "dictation",
                "error_analysis",
            ):
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
        dims = self._default_node_dimensions(node_type)
        default_actions = ["encourage", "advance"]
        if node_type == "warm_up":
            default_actions = ["ask_open", "ask_recall", "encourage", "advance"]
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
            language_skill=dims["language_skill"],
            exercise_type=dims["exercise_type"],
            cognitive_level=dims["cognitive_level"],
            modality=dims["modality"],
            interaction_pattern=dims["interaction_pattern"],
            scaffolding_level=dims["scaffolding_level"],
            scaffolding_supported_range=[dims["scaffolding_level_min"], dims["scaffolding_level_max"]],
            energy_level=dims["energy_level"],
            policy_profile={"allowed_actions": default_actions, "failure_budget": 1},
        )

    def _create_segment_node(
        self, node_type: str, skill: str,
        content: dict, segment_idx: int, skill_type: str = "",
    ) -> LiveNode:
        if content:
            content = normalize_content_pack(content, node_type=node_type)
        dims = self._default_node_dimensions(node_type)
        # Forward lang metadata when available from pre-resolved content.
        dims["target_language"] = str(content.get("target_lang", "")) if isinstance(content, dict) else ""
        dims["source_language"] = str(content.get("source_lang", "")) if isinstance(content, dict) else ""
        phase = self._type_to_phase(node_type)
        templates = []
        if skill_type:
            templates = self._templates.query(node_type=node_type, phase=phase, tags=[skill_type])
        if not templates:
            templates = self._templates.query(node_type=node_type, phase=phase)
            non_matrix = [t for t in templates if "matrix" not in set(t.tags)]
            if non_matrix:
                templates = non_matrix
        if templates:
            template_params = {
                "learning_targets": [skill],
                "skill": skill,
                "content_pack": content,
                "title": f"{node_type.replace('_', ' ').title()}: {skill}",
            }
            if dims["target_language"]:
                template_params["target_language"] = dims["target_language"]
            if dims["source_language"]:
                template_params["source_language"] = dims["source_language"]
            return self._templates.instantiate(
                templates[0].template_id,
                params=template_params,
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
            language_skill=dims["language_skill"],
            exercise_type=dims["exercise_type"],
            cognitive_level=dims["cognitive_level"],
            target_language=dims["target_language"],
            source_language=dims["source_language"],
            modality=dims["modality"],
            interaction_pattern=dims["interaction_pattern"],
            scaffolding_level=dims["scaffolding_level"],
            scaffolding_supported_range=[dims["scaffolding_level_min"], dims["scaffolding_level_max"]],
            energy_level=dims["energy_level"],
            content_pack=content,
            policy_profile={
                "allowed_actions": [
                    "ask_open", "hint_light", "re_explain_brief",
                    "direct_correct", "encourage",
                ],
                "default_style": "neutral_teach",
                "failure_budget": 2,
                "scaffolding_min": dims["scaffolding_level_min"],
                "scaffolding_max": dims["scaffolding_level_max"],
                "interaction_pattern": dims["interaction_pattern"],
                "energy_level": dims["energy_level"],
            },
        )

    @staticmethod
    def _type_to_phase(node_type: str) -> str:
        mapping = {
            "hook": "intro",
            "warm_up": "intro",
            "explain": "present",
            "vocabulary_focus": "present",
            "worked_example": "present",
            "guided_practice": "practice",
            "pronunciation_drill": "practice",
            "listening_comprehension": "practice",
            "reading_comprehension": "practice",
            "dictation": "practice",
            "free_practice": "produce",
            "dialogue_practice": "produce",
            "error_analysis": "review",
            "cultural_note": "present",
            "check_understanding": "practice",
            "repair": "practice",
            "review": "review",
            "transition": "present",
            "wrap_up": "review",
        }
        return mapping.get(node_type, "practice")

    @staticmethod
    def _default_node_dimensions(node_type: str) -> dict:
        """Fallback pedagogical dimensions when templates don't declare them."""
        mapping = {
            "hook": {
                "language_skill": ["listening", "speaking"],
                "exercise_type": "open_prompt",
                "cognitive_level": "recognition",
                "modality": "audio",
                "interaction_pattern": "dialogue",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 3,
                "scaffolding_level": 2,
                "energy_level": "high",
            },
            "warm_up": {
                "language_skill": ["listening", "speaking"],
                "exercise_type": "schema_activation",
                "cognitive_level": "recall",
                "modality": "audio",
                "interaction_pattern": "dialogue",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 3,
                "scaffolding_level": 2,
                "energy_level": "medium",
            },
            "explain": {
                "language_skill": ["listening", "reading"],
                "exercise_type": "concept_explanation",
                "cognitive_level": "recognition",
                "modality": "text",
                "interaction_pattern": "teacher_monologue",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 3,
                "scaffolding_level": 2,
                "energy_level": "low",
            },
            "vocabulary_focus": {
                "language_skill": ["reading", "speaking", "listening"],
                "exercise_type": "vocabulary_focus",
                "cognitive_level": "recall",
                "modality": "multimodal",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 4,
                "scaffolding_level": 2,
                "energy_level": "medium",
            },
            "worked_example": {
                "language_skill": ["reading", "listening"],
                "exercise_type": "worked_example",
                "cognitive_level": "recall",
                "modality": "text",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 2,
                "scaffolding_level_max": 4,
                "scaffolding_level": 3,
                "energy_level": "medium",
            },
            "guided_practice": {
                "language_skill": ["speaking", "writing"],
                "exercise_type": "fill_blank",
                "cognitive_level": "controlled_production",
                "modality": "text",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 2,
                "scaffolding_level_max": 5,
                "scaffolding_level": 3,
                "energy_level": "medium",
            },
            "pronunciation_drill": {
                "language_skill": ["listening", "speaking"],
                "exercise_type": "pronunciation_drill",
                "cognitive_level": "controlled_production",
                "modality": "audio",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 2,
                "scaffolding_level_max": 5,
                "scaffolding_level": 3,
                "energy_level": "high",
            },
            "listening_comprehension": {
                "language_skill": ["listening", "reading"],
                "exercise_type": "listening_comprehension",
                "cognitive_level": "recall",
                "modality": "audio",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 4,
                "scaffolding_level": 2,
                "energy_level": "medium",
            },
            "reading_comprehension": {
                "language_skill": ["reading", "speaking"],
                "exercise_type": "reading_comprehension",
                "cognitive_level": "recall",
                "modality": "text",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 4,
                "scaffolding_level": 2,
                "energy_level": "medium",
            },
            "free_practice": {
                "language_skill": ["speaking", "writing"],
                "exercise_type": "role_play",
                "cognitive_level": "free_production",
                "modality": "audio",
                "interaction_pattern": "dialogue",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 4,
                "scaffolding_level": 2,
                "energy_level": "high",
            },
            "dialogue_practice": {
                "language_skill": ["listening", "speaking"],
                "exercise_type": "role_play",
                "cognitive_level": "free_production",
                "modality": "audio",
                "interaction_pattern": "peer_simulation",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 4,
                "scaffolding_level": 2,
                "energy_level": "high",
            },
            "dictation": {
                "language_skill": ["listening", "writing"],
                "exercise_type": "dictation",
                "cognitive_level": "controlled_production",
                "modality": "audio",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 2,
                "scaffolding_level_max": 5,
                "scaffolding_level": 3,
                "energy_level": "medium",
            },
            "error_analysis": {
                "language_skill": ["speaking", "writing", "reading"],
                "exercise_type": "error_analysis",
                "cognitive_level": "recall",
                "modality": "text",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 2,
                "scaffolding_level_max": 5,
                "scaffolding_level": 3,
                "energy_level": "low",
            },
            "cultural_note": {
                "language_skill": ["listening", "reading"],
                "exercise_type": "cultural_note",
                "cognitive_level": "recognition",
                "modality": "multimodal",
                "interaction_pattern": "teacher_monologue",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 2,
                "scaffolding_level": 1,
                "energy_level": "low",
            },
            "check_understanding": {
                "language_skill": ["reading", "speaking"],
                "exercise_type": "multiple_choice",
                "cognitive_level": "recall",
                "modality": "text",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 3,
                "scaffolding_level": 2,
                "energy_level": "medium",
            },
            "repair": {
                "language_skill": ["listening", "speaking"],
                "exercise_type": "scaffolded_correction",
                "cognitive_level": "controlled_production",
                "modality": "text",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 3,
                "scaffolding_level_max": 5,
                "scaffolding_level": 4,
                "energy_level": "low",
            },
            "review": {
                "language_skill": ["reading", "speaking"],
                "exercise_type": "recall",
                "cognitive_level": "recall",
                "modality": "text",
                "interaction_pattern": "IRE",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 4,
                "scaffolding_level": 2,
                "energy_level": "medium",
            },
            "transition": {
                "language_skill": ["listening"],
                "exercise_type": "transition",
                "cognitive_level": "recognition",
                "modality": "audio",
                "interaction_pattern": "teacher_monologue",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 2,
                "scaffolding_level": 1,
                "energy_level": "low",
            },
            "wrap_up": {
                "language_skill": ["listening", "speaking"],
                "exercise_type": "summary_reflection",
                "cognitive_level": "recall",
                "modality": "audio",
                "interaction_pattern": "dialogue",
                "scaffolding_level_min": 1,
                "scaffolding_level_max": 3,
                "scaffolding_level": 2,
                "energy_level": "low",
            },
        }
        dims = dict(mapping.get(node_type, mapping["guided_practice"]))
        dims["target_language"] = ""
        dims["source_language"] = ""
        return dims
