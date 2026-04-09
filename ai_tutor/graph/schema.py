"""
Graph Schema - All shared data structures for the Dynamic Lesson Graph.

Defines the contracts between graph engine, mutator, assembler,
content connector, and WebSocket protocol.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Offline template (loaded from YAML)
# ---------------------------------------------------------------------------

@dataclass
class NodeTemplate:
    """Multi-granularity building block for lesson nodes.
    Templates are NOT complete nodes -- they are instantiated and
    parameterized at runtime by the GraphAssembler or SubgraphFactory."""

    template_id: str                        # e.g. "explain_grammar_v1"
    node_type: str                          # hook | explain | worked_example |
                                            # guided_practice | free_practice |
                                            # check_understanding | repair | review |
                                            # transition | wrap_up
    granularity: str                        # "micro" (1-2 turns) |
                                            # "standard" (3-5 turns) |
                                            # "macro" (compound, contains sub-nodes)
    phase: str                              # intro | present | practice | produce | review

    teacher_goal_template: str              # Jinja2 template, e.g. "Help student understand {{skill}}"
    expected_evidence_types: list[str]       # ["corrected_sentence", "rule_explanation", ...]

    allowed_policy_actions: list[str]        # subset of the 16 policy actions
    allowed_tool_actions: list[str]          # subset of tool actions
    default_delivery_style: str              # e.g. "neutral_teach"

    content_pack_slots: list[str]            # ["script_outline", "examples", "common_mistakes"]
    failure_budget: int                      # max consecutive failures before transition
    success_threshold: str                   # e.g. "student_correct_once", "student_explain_rule"

    memory_writeback_spec: dict = field(default_factory=dict)
    # {"update_skills": True, "record_misconceptions": True, ...}

    llm_supervisor_allowed: bool = True
    tags: list[str] = field(default_factory=list)           # ["grammar", "vocabulary", ...]
    prerequisites: list[str] = field(default_factory=list)  # skill IDs
    estimated_duration_seconds: int = 120


# ---------------------------------------------------------------------------
# Runtime live node (instantiated from template)
# ---------------------------------------------------------------------------

@dataclass
class LiveNode:
    """A runtime-instantiated node in the lesson graph.
    Created by NodeTemplateLibrary.instantiate() or SubgraphFactory."""

    node_id: str                            # unique, e.g. "node_003" or "repair_003_a"
    template_id: str
    node_type: str
    phase: str
    title: str
    learning_targets: list[str]             # skill IDs

    teacher_goal: str                       # instantiated from template
    expected_student_evidence: list[str]

    content_pack: dict = field(default_factory=dict)
    # resolved content: script_outline, examples, common_mistakes, media_anchors

    policy_profile: dict = field(default_factory=dict)
    # allowed_actions, default_style, success_threshold, failure_budget

    tool_profile: dict = field(default_factory=dict)
    # allowed_tool_actions

    transitions: dict[str, str] = field(default_factory=dict)
    # event -> target_node_id (static transitions from assembler, dynamic ones from mutator)

    memory_writeback: dict = field(default_factory=dict)
    llm_supervisor_allowed: bool = True

    # --- Runtime mutable state ---
    visit_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    status: str = "pending"                 # pending | active | completed | skipped | resumed
    inserted_at: float = 0.0                # timestamp when node was added to graph
    subgraph_origin: Optional[str] = None   # if this node is part of an inserted subgraph


# ---------------------------------------------------------------------------
# Edge specification
# ---------------------------------------------------------------------------

@dataclass
class EdgeSpec:
    """Directed edge in the lesson graph."""

    source_id: str
    target_id: str
    event: str                              # on_success | on_minor_error | on_major_error |
                                            # on_silence | on_off_topic | on_backtrack |
                                            # auto_advance
    weight: float = 1.0                     # lower = more preferred (cost semantics)
    priority: int = 0                       # higher = preferred when multiple edges match same event
    conditions: dict = field(default_factory=dict)  # optional guard conditions


# ---------------------------------------------------------------------------
# Subgraph specification (for dynamic insertion)
# ---------------------------------------------------------------------------

@dataclass
class SubgraphSpec:
    """A pre-built mini-graph that can be inserted into the main graph.
    Created by SubgraphFactory for repair/backtrack/enrichment/assessment."""

    subgraph_id: str
    entry_node_id: str
    exit_node_id: str
    nodes: list[LiveNode] = field(default_factory=list)
    edges: list[EdgeSpec] = field(default_factory=list)
    purpose: str = ""                       # repair | backtrack | enrichment | assessment
    target_skill: str = ""                  # the skill this subgraph addresses
    source_node_id: str = ""                # the original node that triggered this subgraph


# ---------------------------------------------------------------------------
# Graph mutation record (for WebSocket diff broadcasting)
# ---------------------------------------------------------------------------

@dataclass
class GraphMutation:
    """A single mutation operation on the graph.
    Accumulated by LessonGraph, drained by WS server for diff broadcast."""

    op: str                                 # add_node | remove_node | update_node_status |
                                            # add_edge | remove_edge | update_edge_weight |
                                            # move_cursor | insert_subgraph | remove_subgraph
    data: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Voice model input (bridge between graph/runtime and voice system)
# ---------------------------------------------------------------------------

@dataclass
class VoiceModelInput:
    """Complete input for the self-thinking voice model.
    Assembled by VoiceDispatcher from graph state + memory + policy output."""

    # --- Graph State ---
    current_node_type: str = ""             # one-hot over 10 node types
    current_phase: str = ""                 # one-hot over 5 phases
    node_visit_count: int = 0
    node_success_count: int = 0
    node_failure_count: int = 0
    lesson_progress: float = 0.0            # 0.0 to 1.0
    is_repair_mode: bool = False

    # --- Policy Decision ---
    policy_action: str = ""                 # one-hot over 16 policy actions
    tool_action: Optional[str] = None       # one-hot over tool actions (nullable)
    delivery_style: str = "neutral_teach"   # one-hot over 10 delivery styles

    # --- Student State ---
    student_error_type: str = ""
    student_confidence: float = 0.5
    student_fatigue: float = 0.0
    student_engagement: float = 0.5
    student_lang_level: str = "B1"          # A1 | A2 | B1 | B2 | C1 | C2
    consecutive_failures: int = 0
    student_last_utterance_duration_ms: int = 0
    student_silence_duration_ms: int = 0

    # --- Persona Parameters (fixed identity + personality) ---
    persona_warmth: float = 0.5
    persona_formality: float = 0.5
    persona_humor: float = 0.3
    persona_patience: float = 0.7
    persona_energy: float = 0.6
    persona_gender: str = "female"
    persona_age_range: str = "young_adult"  # young_adult | middle_aged | mature

    # --- Delivery Style Parameters (computed per-turn) ---
    speaking_speed: float = 1.0             # 0.5 to 2.0 multiplier
    pause_tendency: float = 0.3             # 0.0 to 1.0
    emphasis_intensity: float = 0.3         # 0.0 to 1.0
    emotion_amplitude: float = 0.3          # 0.0 to 1.0
    intonation_variability: float = 0.3     # 0.0 to 1.0
    backchannel_frequency: float = 0.2      # 0.0 to 1.0
    sentence_final_pattern: str = "falling" # falling | rising | sustained

    # --- Content Context (pre-computed embeddings) ---
    content_pack_embedding: list[float] = field(default_factory=list)
    recent_turns_embedding: list[float] = field(default_factory=list)
    target_skill_embedding: list[float] = field(default_factory=list)
