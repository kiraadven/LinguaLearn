"""
4-Layer Memory System for AI Tutor.

Layers:
1. HotMemory      - Current-turn volatile state (rebuilt every turn)
2. LessonMemory   - Single lesson session accumulation
3. LearnerMemory  - Cross-session stable student profile
4. TeacherControlMemory - Teacher persona + session control state

The critical bridge method is MemoryManager.get_graph_mutation_signals()
which cross-queries all 4 layers to produce signals for GraphMutator.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import time


# ---------------------------------------------------------------------------
# Layer 1: Hot Memory (per-turn, volatile)
# ---------------------------------------------------------------------------

@dataclass
class HotMemory:
    """Current-turn state. Rebuilt every turn from latest data."""
    current_node_id: str = ""
    current_policy_id: str = ""
    allowed_actions: list[str] = field(default_factory=list)
    recent_turns: list[dict] = field(default_factory=list)  # last 3-5 turns
    current_media_position: dict = field(default_factory=dict)
    # {"video_time_ms": int, "material_page": int}
    is_repair_mode: bool = False
    turn_number: int = 0
    last_event: str = ""  # event that led to current node


# ---------------------------------------------------------------------------
# Layer 2: Lesson Memory (per-session)
# ---------------------------------------------------------------------------

@dataclass
class LessonMemory:
    """Accumulated state within a single lesson session."""
    visited_node_path: list[str] = field(default_factory=list)
    node_outcomes: dict = field(default_factory=dict)
    # node_id -> {"success_count": int, "failure_count": int, "attempts": int}
    covered_skills: set = field(default_factory=set)
    error_log: list[dict] = field(default_factory=list)
    # [{"skill": str, "error_type": str, "node_id": str, "turn": int}, ...]
    explanations_given: list[str] = field(default_factory=list)
    examples_given: list[str] = field(default_factory=list)
    quiz_results: list[dict] = field(default_factory=list)
    subgraphs_inserted: list[str] = field(default_factory=list)
    lesson_start_time: float = 0.0
    total_student_speaking_time_ms: int = 0
    total_silence_time_ms: int = 0


# ---------------------------------------------------------------------------
# Layer 3: Learner Memory (cross-session, persistent)
# ---------------------------------------------------------------------------

@dataclass
class MasteryRecord:
    mastery: float = 0.0           # 0.0 to 1.0
    exposures: int = 0
    last_error: str = ""
    last_error_time: float = 0.0
    review_due: bool = False
    consecutive_correct: int = 0
    consecutive_wrong: int = 0


@dataclass
class LearnerMemory:
    """Cross-session stable student profile."""
    student_id: str = ""
    lang_level: str = "B1"
    goals: list[str] = field(default_factory=list)
    skills: dict[str, MasteryRecord] = field(default_factory=dict)
    high_frequency_errors: list[str] = field(default_factory=list)
    stuck_node_types: list[str] = field(default_factory=list)
    pace_preference: str = "normal"           # slow | normal | fast
    hint_strength_preference: str = "medium"  # light | medium | strong
    preferred_correction_style: str = "gentle_corrective"
    review_history: list[dict] = field(default_factory=list)
    total_sessions: int = 0
    total_study_time_minutes: float = 0.0
    # Voice persona identity for cross-session consistency
    assigned_persona_id: str = ""


# ---------------------------------------------------------------------------
# Layer 4: Teacher Control Memory (per-session)
# ---------------------------------------------------------------------------

@dataclass
class TeacherControlMemory:
    """Teacher persona and session control state."""
    persona_id: str = ""
    persona_params: dict = field(default_factory=dict)
    # {warmth, formality, humor, patience, energy, gender, age_range}
    default_delivery_style: str = "neutral_teach"
    allowed_tools: list[str] = field(default_factory=list)
    banned_expressions: list[str] = field(default_factory=list)
    banned_actions: list[str] = field(default_factory=list)
    current_policy_version: str = ""
    last_supervisor_intervention: Optional[dict] = None
    # {"reason": str, "node_id": str, "timestamp": float}
    session_discipline_mode: str = "normal"  # normal | strict | relaxed


# ---------------------------------------------------------------------------
# MemoryManager - Unified interface to all 4 layers
# ---------------------------------------------------------------------------

class MemoryManager:
    """Unified read/write interface to all memory layers.
    One instance per running server, manages multiple sessions."""

    def __init__(self, db_backend=None):
        self._hot: dict[str, HotMemory] = {}            # session_id -> HotMemory
        self._lesson: dict[str, LessonMemory] = {}       # session_id -> LessonMemory
        self._learner: dict[str, LearnerMemory] = {}     # student_id -> LearnerMemory
        self._teacher: dict[str, TeacherControlMemory] = {}  # session_id -> TeacherControlMemory
        self._session_student_map: dict[str, str] = {}   # session_id -> student_id
        self._db = db_backend  # future: persistent storage

    # --- Session lifecycle ---

    def init_session(self, session_id: str, student_id: str,
                     persona_id: str, persona_params: dict) -> None:
        self._session_student_map[session_id] = student_id
        self._hot[session_id] = HotMemory()
        self._lesson[session_id] = LessonMemory(lesson_start_time=time.time())

        if student_id not in self._learner:
            self._learner[student_id] = LearnerMemory(
                student_id=student_id,
                assigned_persona_id=persona_id,
            )
        learner = self._learner[student_id]
        learner.total_sessions += 1

        self._teacher[session_id] = TeacherControlMemory(
            persona_id=persona_id,
            persona_params=persona_params,
        )

    def end_session(self, session_id: str) -> None:
        self.compress_lesson_to_learner(session_id)
        # Cleanup session-scoped memory
        self._hot.pop(session_id, None)
        self._lesson.pop(session_id, None)
        self._teacher.pop(session_id, None)
        self._session_student_map.pop(session_id, None)

    # --- Hot memory ---

    def update_hot(self, session_id: str, **kwargs) -> HotMemory:
        hot = self._hot[session_id]
        for k, v in kwargs.items():
            if hasattr(hot, k):
                setattr(hot, k, v)
        return hot

    def get_hot(self, session_id: str) -> HotMemory:
        return self._hot[session_id]

    # --- Assessment application ---

    def apply_assessment(self, session_id: str, assessment: dict) -> None:
        """Apply a StudentAssessment to all relevant memory layers.

        assessment dict keys:
        - error_type: str
        - focus_skill: str
        - confidence: float
        - fatigue: float
        - engagement: float
        - is_correct: bool
        - node_id: str
        - turn_number: int
        """
        student_id = self._session_student_map[session_id]
        lesson = self._lesson[session_id]
        learner = self._learner[student_id]

        skill = assessment.get("focus_skill", "")
        node_id = assessment.get("node_id", "")
        is_correct = assessment.get("is_correct", False)

        # Update lesson memory
        if skill:
            lesson.covered_skills.add(skill)
        if not is_correct and assessment.get("error_type"):
            lesson.error_log.append({
                "skill": skill,
                "error_type": assessment["error_type"],
                "node_id": node_id,
                "turn": assessment.get("turn_number", 0),
            })

        # Update node outcomes
        if node_id:
            if node_id not in lesson.node_outcomes:
                lesson.node_outcomes[node_id] = {
                    "success_count": 0, "failure_count": 0, "attempts": 0,
                }
            outcome = lesson.node_outcomes[node_id]
            outcome["attempts"] += 1
            if is_correct:
                outcome["success_count"] += 1
            else:
                outcome["failure_count"] += 1

        # Update learner memory (skill mastery)
        if skill:
            if skill not in learner.skills:
                learner.skills[skill] = MasteryRecord()
            mr = learner.skills[skill]
            mr.exposures += 1
            if is_correct:
                mr.consecutive_correct += 1
                mr.consecutive_wrong = 0
                mr.mastery = min(1.0, mr.mastery + 0.05 * (1.0 - mr.mastery))
            else:
                mr.consecutive_correct = 0
                mr.consecutive_wrong += 1
                mr.mastery = max(0.0, mr.mastery - 0.03)
                mr.last_error = assessment.get("error_type", "")
                mr.last_error_time = time.time()

    def record_node_visit(self, session_id: str, node_id: str) -> None:
        lesson = self._lesson[session_id]
        lesson.visited_node_path.append(node_id)

    def record_explanation(self, session_id: str, explanation: str) -> None:
        self._lesson[session_id].explanations_given.append(explanation)

    def record_example(self, session_id: str, example: str) -> None:
        self._lesson[session_id].examples_given.append(example)

    def record_subgraph(self, session_id: str, subgraph_id: str) -> None:
        self._lesson[session_id].subgraphs_inserted.append(subgraph_id)

    # --- Cross-layer queries ---

    def get_graph_mutation_signals(self, session_id: str) -> dict:
        """THE CRITICAL BRIDGE: Cross-query all 4 layers to produce signals
        for GraphMutator.

        Returns dict with:
        - should_repair: bool
        - repair_skill: str
        - should_backtrack: bool
        - backtrack_target: str
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
        """
        student_id = self._session_student_map[session_id]
        hot = self._hot[session_id]
        lesson = self._lesson[session_id]
        learner = self._learner[student_id]

        signals = {
            "should_repair": False,
            "repair_skill": "",
            "should_backtrack": False,
            "backtrack_target": "",
            "backtrack_skill": "",
            "should_enrich": False,
            "enrich_skill": "",
            "should_slow_down": False,
            "fatigue": 0.0,
            "engagement": 0.5,
            "mastery": {},
            "consecutive_failures": 0,
            "error_severity": 0.5,
            "time_pressure": 0.0,
        }

        # Mastery snapshot
        signals["mastery"] = {
            skill: mr.mastery for skill, mr in learner.skills.items()
        }

        # Current node outcome analysis
        node_id = hot.current_node_id
        if node_id and node_id in lesson.node_outcomes:
            outcome = lesson.node_outcomes[node_id]
            consecutive_fails = outcome["failure_count"]
            signals["consecutive_failures"] = consecutive_fails

            # Should repair? consecutive failures >= 2 on current node
            if consecutive_fails >= 2:
                # Find the skill for this node from error log
                recent_errors = [
                    e for e in lesson.error_log
                    if e["node_id"] == node_id
                ]
                if recent_errors:
                    signals["should_repair"] = True
                    signals["repair_skill"] = recent_errors[-1].get("skill", "")

        # Error severity from recent errors
        recent_errors = lesson.error_log[-3:] if lesson.error_log else []
        if recent_errors:
            major_count = sum(1 for e in recent_errors if e.get("error_type", "").startswith("major"))
            signals["error_severity"] = min(1.0, 0.3 + major_count * 0.25)

        # Should enrich? skill mastery > 0.85 and student is engaged
        for skill, mr in learner.skills.items():
            if mr.mastery > 0.85 and mr.consecutive_correct >= 3:
                if skill not in lesson.covered_skills or mr.consecutive_correct >= 5:
                    signals["should_enrich"] = True
                    signals["enrich_skill"] = skill
                    break

        # Time pressure
        elapsed = time.time() - lesson.lesson_start_time
        # Assume 30-minute lesson
        signals["time_pressure"] = min(1.0, max(0.0, elapsed / 1800.0))

        # Fatigue: estimate from turn count and silence
        signals["fatigue"] = min(1.0, hot.turn_number * 0.02 +
                                 lesson.total_silence_time_ms / 60000.0 * 0.1)

        # Should slow down? high fatigue or low engagement
        if signals["fatigue"] > 0.7:
            signals["should_slow_down"] = True

        return signals

    def get_voice_context(self, session_id: str) -> dict:
        """Assemble context needed by the voice model."""
        student_id = self._session_student_map[session_id]
        teacher = self._teacher[session_id]
        learner = self._learner[student_id]
        hot = self._hot[session_id]

        return {
            "persona_id": teacher.persona_id,
            "persona_params": teacher.persona_params,
            "default_delivery_style": teacher.default_delivery_style,
            "student_lang_level": learner.lang_level,
            "is_repair_mode": hot.is_repair_mode,
            "turn_number": hot.turn_number,
            "recent_turns": hot.recent_turns[-5:],
        }

    # --- Getters ---

    def get_learner(self, student_id: str) -> LearnerMemory:
        if student_id not in self._learner:
            self._learner[student_id] = LearnerMemory(student_id=student_id)
        return self._learner[student_id]

    def get_lesson(self, session_id: str) -> LessonMemory:
        return self._lesson[session_id]

    def get_teacher_control(self, session_id: str) -> TeacherControlMemory:
        return self._teacher[session_id]

    # --- Compression ---

    def compress_lesson_to_learner(self, session_id: str) -> None:
        """End-of-lesson: compress LessonMemory into LearnerMemory updates."""
        student_id = self._session_student_map.get(session_id)
        if not student_id:
            return
        lesson = self._lesson.get(session_id)
        learner = self._learner.get(student_id)
        if not lesson or not learner:
            return

        # Update total study time
        elapsed = time.time() - lesson.lesson_start_time
        learner.total_study_time_minutes += elapsed / 60.0

        # Identify high-frequency errors from this lesson
        error_counts: dict[str, int] = {}
        for err in lesson.error_log:
            et = err.get("error_type", "")
            error_counts[et] = error_counts.get(et, 0) + 1
        for et, count in error_counts.items():
            if count >= 2 and et not in learner.high_frequency_errors:
                learner.high_frequency_errors.append(et)

        # Mark skills needing review
        for skill, mr in learner.skills.items():
            if mr.consecutive_wrong >= 2:
                mr.review_due = True

        # Add review history entry
        learner.review_history.append({
            "session_id": session_id,
            "skills_covered": list(lesson.covered_skills),
            "subgraphs_inserted": lesson.subgraphs_inserted,
            "total_errors": len(lesson.error_log),
            "timestamp": time.time(),
        })
