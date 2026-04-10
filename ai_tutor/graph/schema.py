"""
Graph Schema - All shared data structures for the Dynamic Lesson Graph.

Defines the contracts between graph engine, mutator, assembler,
content connector, and WebSocket protocol.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional, TypedDict, cast


# ---------------------------------------------------------------------------
# Content pack schema contract
# ---------------------------------------------------------------------------

CONTENT_PACK_SCHEMA_VERSION = 1


class ContentPackExample(TypedDict):
    source: str
    target: str


class ContentPackErrorExample(TypedDict):
    wrong: str
    correct: str
    explanation: str


class ContentPackCommonMistakes(TypedDict):
    l1_transfer: str
    correction_strategy: str
    error_examples: list[ContentPackErrorExample]


class ContentPackSupplementaryLink(TypedDict):
    title: str
    url: str


class ContentPack(TypedDict):
    schema_version: int
    node_type: str
    lang_level: str
    source_lang: str
    target_lang: str
    target_item: dict[str, Any]
    script_outline: list[str]
    examples: list[ContentPackExample]
    common_mistakes: ContentPackCommonMistakes
    media_anchors: list[dict[str, Any]]
    supplementary_links: list[ContentPackSupplementaryLink]
    collocations: list[str]
    mnemonic: str
    teaching_tip: str
    exercises: list[dict[str, Any]]
    scaffolding_hints: list[dict[str, Any]]
    quiz_items: list[dict[str, Any]]
    follow_up_on_error: str
    simplified_explanation: str
    analogy: str
    minimal_examples: list[ContentPackExample]
    micro_exercise: dict[str, Any]
    problem: str
    step_by_step: list[dict[str, Any]]
    key_insight: str
    recall_prompt: str
    quick_summary: str
    retrieval_exercise: dict[str, Any]
    teacher_line: str
    error: str
    extras: dict[str, Any]


CONTENT_PACK_CANONICAL_KEYS: tuple[str, ...] = (
    "schema_version",
    "node_type",
    "lang_level",
    "source_lang",
    "target_lang",
    "target_item",
    "script_outline",
    "examples",
    "common_mistakes",
    "media_anchors",
    "supplementary_links",
    "collocations",
    "mnemonic",
    "teaching_tip",
    "exercises",
    "scaffolding_hints",
    "quiz_items",
    "follow_up_on_error",
    "simplified_explanation",
    "analogy",
    "minimal_examples",
    "micro_exercise",
    "problem",
    "step_by_step",
    "key_insight",
    "recall_prompt",
    "quick_summary",
    "retrieval_exercise",
    "teacher_line",
    "error",
    "extras",
)


def _coerce_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    text = str(value).strip()
    return text if text else default


def _coerce_text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _coerce_text(item)
        if text:
            out.append(text)
    return out


def _coerce_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _coerce_dict_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [dict(value)]
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(dict(item))
        elif isinstance(item, str):
            text = item.strip()
            if text:
                out.append({"text": text})
    return out


def _coerce_examples(value: Any) -> list[ContentPackExample]:
    raw_items = value if isinstance(value, list) else [value] if isinstance(value, (dict, str)) else []
    out: list[ContentPackExample] = []
    for item in raw_items:
        if isinstance(item, dict):
            source = _coerce_text(item.get("source") or item.get("sentence") or item.get("text"))
            target = _coerce_text(item.get("target") or item.get("translation"))
        else:
            source = _coerce_text(item)
            target = ""
        if source or target:
            out.append({"source": source, "target": target})
    return out


def _coerce_common_mistakes(value: Any) -> ContentPackCommonMistakes:
    out: ContentPackCommonMistakes = {
        "l1_transfer": "",
        "correction_strategy": "",
        "error_examples": [],
    }
    if isinstance(value, dict):
        out["l1_transfer"] = _coerce_text(value.get("l1_transfer"))
        out["correction_strategy"] = _coerce_text(value.get("correction_strategy"))
        raw_examples = value.get("error_examples", [])
    elif isinstance(value, list):
        raw_examples = value
    else:
        raw_examples = []

    for item in raw_examples if isinstance(raw_examples, list) else []:
        if isinstance(item, dict):
            wrong = _coerce_text(item.get("wrong"))
            correct = _coerce_text(item.get("correct"))
            explanation = _coerce_text(item.get("explanation"))
        else:
            wrong = _coerce_text(item)
            correct = ""
            explanation = ""
        if wrong or correct or explanation:
            out["error_examples"].append({
                "wrong": wrong,
                "correct": correct,
                "explanation": explanation,
            })
    return out


def _coerce_links(value: Any) -> list[ContentPackSupplementaryLink]:
    raw_items = value if isinstance(value, list) else [value] if isinstance(value, (dict, str)) else []
    out: list[ContentPackSupplementaryLink] = []
    for item in raw_items:
        if isinstance(item, dict):
            title = _coerce_text(item.get("title"))
            url = _coerce_text(item.get("url"))
        else:
            title = ""
            url = _coerce_text(item)
        if title or url:
            out.append({"title": title, "url": url})
    return out


def normalize_content_pack(
    raw: Optional[dict[str, Any]],
    *,
    node_type: str = "",
    lang_level: str = "",
    source_lang: str = "",
    target_lang: str = "",
) -> ContentPack:
    """Normalize arbitrary content_pack dicts into a canonical structure.

    The returned mapping always contains all canonical keys. Unknown keys are
    preserved in `extras` and also left at top level for backward compatibility.
    """
    data = raw if isinstance(raw, dict) else {}

    resolved_node_type = _coerce_text(data.get("node_type"), node_type)
    resolved_level = _coerce_text(data.get("lang_level"), lang_level)
    resolved_source_lang = _coerce_text(data.get("source_lang"), source_lang)
    resolved_target_lang = _coerce_text(
        data.get("target_lang") or data.get("learning_lang"),
        target_lang,
    )

    common_mistakes = _coerce_common_mistakes(data.get("common_mistakes"))
    media_anchors = _coerce_dict_list(data.get("media_anchors"))
    supplementary_links = _coerce_links(data.get("supplementary_links"))

    normalized: dict[str, Any] = {
        "schema_version": CONTENT_PACK_SCHEMA_VERSION,
        "node_type": resolved_node_type,
        "lang_level": resolved_level,
        "source_lang": resolved_source_lang,
        "target_lang": resolved_target_lang,
        "target_item": _coerce_dict(data.get("target_item")),
        "script_outline": _coerce_text_list(data.get("script_outline")),
        "examples": _coerce_examples(data.get("examples")),
        "common_mistakes": common_mistakes,
        "media_anchors": media_anchors,
        "supplementary_links": supplementary_links,
        "collocations": _coerce_text_list(data.get("collocations")),
        "mnemonic": _coerce_text(data.get("mnemonic")),
        "teaching_tip": _coerce_text(data.get("teaching_tip")),
        "exercises": _coerce_dict_list(data.get("exercises")),
        "scaffolding_hints": _coerce_dict_list(data.get("scaffolding_hints")),
        "quiz_items": _coerce_dict_list(data.get("quiz_items")),
        "follow_up_on_error": _coerce_text(data.get("follow_up_on_error")),
        "simplified_explanation": _coerce_text(data.get("simplified_explanation")),
        "analogy": _coerce_text(data.get("analogy")),
        "minimal_examples": _coerce_examples(data.get("minimal_examples")),
        "micro_exercise": _coerce_dict(data.get("micro_exercise")),
        "problem": _coerce_text(data.get("problem")),
        "step_by_step": _coerce_dict_list(data.get("step_by_step")),
        "key_insight": _coerce_text(data.get("key_insight")),
        "recall_prompt": _coerce_text(data.get("recall_prompt")),
        "quick_summary": _coerce_text(data.get("quick_summary")),
        "retrieval_exercise": _coerce_dict(data.get("retrieval_exercise")),
        "teacher_line": _coerce_text(data.get("teacher_line")),
        "error": _coerce_text(data.get("error")),
        "extras": {},
    }

    known_keys = set(CONTENT_PACK_CANONICAL_KEYS)
    extras: dict[str, Any] = {}
    for key, value in data.items():
        if key not in known_keys and key != "extras":
            extras[key] = value
    legacy_extras = data.get("extras")
    if isinstance(legacy_extras, dict):
        extras.update(legacy_extras)
    normalized["extras"] = extras

    # Keep unknown keys at top level to avoid breaking legacy consumers.
    for key, value in extras.items():
        normalized.setdefault(key, value)

    return cast(ContentPack, normalized)


# ---------------------------------------------------------------------------
# Offline template (loaded from YAML)
# ---------------------------------------------------------------------------

@dataclass
class NodeTemplate:
    """Multi-granularity building block for lesson nodes.
    Templates are NOT complete nodes -- they are instantiated and
    parameterized at runtime by the GraphAssembler or SubgraphFactory."""

    template_id: str                        # e.g. "explain_grammar_v1"
    node_type: str                          # hook | warm_up | explain | vocabulary_focus |
                                            # worked_example | guided_practice | free_practice |
                                            # pronunciation_drill | listening_comprehension |
                                            # reading_comprehension | dialogue_practice |
                                            # dictation | error_analysis | cultural_note |
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

    # Pedagogical dimensions (explicitly modeled for runtime adaptation)
    language_skill: list[str] = field(default_factory=list)
    # listening | speaking | reading | writing (one or more)
    exercise_type: str = "generic"
    # multiple_choice | fill_blank | translation | shadowing | role_play | dictation | ...
    cognitive_level: str = "recognition"
    # recognition | recall | controlled_production | free_production
    target_language: str = ""
    source_language: str = ""
    modality: str = "text"
    # text | audio | video | image | multimodal
    interaction_pattern: str = "dialogue"
    # teacher_monologue | IRE | dialogue | peer_simulation
    scaffolding_level_min: int = 1
    scaffolding_level_max: int = 5
    energy_level: str = "medium"
    # high | medium | low
    l1_aware_error_patterns: dict[str, list[str]] = field(default_factory=dict)
    # Example:
    # {
    #   "zh->en": ["article_omission", "tense_confusion"],
    #   "ja->en": ["article_confusion", "relative_clause"]
    # }

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

    # Pedagogical dimensions copied from NodeTemplate (or fallback defaults)
    language_skill: list[str] = field(default_factory=list)
    exercise_type: str = "generic"
    cognitive_level: str = "recognition"
    target_language: str = ""
    source_language: str = ""
    modality: str = "text"
    interaction_pattern: str = "dialogue"
    scaffolding_level: int = 3
    scaffolding_supported_range: list[int] = field(default_factory=lambda: [1, 5])
    energy_level: str = "medium"
    l1_aware_error_patterns: dict[str, list[str]] = field(default_factory=dict)

    content_pack: dict[str, Any] = field(default_factory=dict)
    # normalized structure via normalize_content_pack(); empty dict means unresolved.

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

VOICE_NODE_TYPE_VOCAB: tuple[str, ...] = (
    "hook",
    "warm_up",
    "explain",
    "vocabulary_focus",
    "worked_example",
    "guided_practice",
    "free_practice",
    "pronunciation_drill",
    "listening_comprehension",
    "reading_comprehension",
    "dialogue_practice",
    "dictation",
    "error_analysis",
    "cultural_note",
    "check_understanding",
    "repair",
    "review",
    "transition",
    "wrap_up",
)

VOICE_PHASE_VOCAB: tuple[str, ...] = (
    "intro",
    "present",
    "practice",
    "produce",
    "review",
)

VOICE_POLICY_ACTION_VOCAB: tuple[str, ...] = (
    "advance",
    "encourage",
    "pause_wait",
    "re_explain_simplify",
    "hint_strong",
    "scaffold_step",
    "direct_correct",
    "re_explain_brief",
    "hint_light",
    "ask_recall",
    "ask_open",
    "ask_check",
)

VOICE_DELIVERY_STYLE_VOCAB: tuple[str, ...] = (
    "neutral_teach",
    "warm_encourage",
    "gentle_corrective",
    "firm_corrective",
    "slow_repair",
    "energetic_advance",
    "curious_probe",
    "surprised_react",
    "celebrate_success",
    "calm_reset",
)

VOICE_TOOL_ACTION_VOCAB: tuple[str, ...] = (
    "open_material_section",
    "rewind_video_5s",
)


def _categorical_id(value: Optional[str], vocab: tuple[str, ...]) -> int:
    if not value:
        return -1
    try:
        return vocab.index(value)
    except ValueError:
        return -1


def _one_hot(value: Optional[str], vocab: tuple[str, ...]) -> list[float]:
    vec = [0.0] * len(vocab)
    idx = _categorical_id(value, vocab)
    if idx >= 0:
        vec[idx] = 1.0
    return vec


@dataclass
class VoiceModelInput:
    """Complete input for the self-thinking voice model.
    Assembled by VoiceDispatcher from graph state + memory + policy output."""

    # --- Graph State ---
    current_node_type: str = ""             # categorical label (see VOICE_NODE_TYPE_VOCAB)
    current_phase: str = ""                 # categorical label (see VOICE_PHASE_VOCAB)
    node_visit_count: int = 0
    node_success_count: int = 0
    node_failure_count: int = 0
    lesson_progress: float = 0.0            # 0.0 to 1.0
    is_repair_mode: bool = False

    # --- Policy Decision ---
    policy_action: str = ""                 # categorical label (see VOICE_POLICY_ACTION_VOCAB)
    tool_action: Optional[str] = None       # categorical label (see VOICE_TOOL_ACTION_VOCAB)
    delivery_style: str = "neutral_teach"   # categorical label (see VOICE_DELIVERY_STYLE_VOCAB)

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

    # --- Encoded Categorical Features (deterministic mapping) ---
    current_node_type_id: int = -1
    current_phase_id: int = -1
    policy_action_id: int = -1
    tool_action_id: int = -1
    delivery_style_id: int = -1

    current_node_type_one_hot: list[float] = field(default_factory=list)
    current_phase_one_hot: list[float] = field(default_factory=list)
    policy_action_one_hot: list[float] = field(default_factory=list)
    tool_action_one_hot: list[float] = field(default_factory=list)
    delivery_style_one_hot: list[float] = field(default_factory=list)

    def apply_categorical_encodings(self) -> "VoiceModelInput":
        """Populate ids and one-hot vectors from categorical labels.
        Unknown labels are encoded as id=-1 and all-zero vectors."""
        self.current_node_type_id = _categorical_id(self.current_node_type, VOICE_NODE_TYPE_VOCAB)
        self.current_phase_id = _categorical_id(self.current_phase, VOICE_PHASE_VOCAB)
        self.policy_action_id = _categorical_id(self.policy_action, VOICE_POLICY_ACTION_VOCAB)
        self.tool_action_id = _categorical_id(self.tool_action, VOICE_TOOL_ACTION_VOCAB)
        self.delivery_style_id = _categorical_id(self.delivery_style, VOICE_DELIVERY_STYLE_VOCAB)

        self.current_node_type_one_hot = _one_hot(self.current_node_type, VOICE_NODE_TYPE_VOCAB)
        self.current_phase_one_hot = _one_hot(self.current_phase, VOICE_PHASE_VOCAB)
        self.policy_action_one_hot = _one_hot(self.policy_action, VOICE_POLICY_ACTION_VOCAB)
        self.tool_action_one_hot = _one_hot(self.tool_action, VOICE_TOOL_ACTION_VOCAB)
        self.delivery_style_one_hot = _one_hot(self.delivery_style, VOICE_DELIVERY_STYLE_VOCAB)
        return self
