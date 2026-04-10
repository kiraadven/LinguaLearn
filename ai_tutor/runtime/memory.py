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
import math
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
    recent_node_trace: list[dict] = field(default_factory=list)  # last N node contexts for pacing
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
    fatigue_history: list[float] = field(default_factory=list)
    engagement_history: list[float] = field(default_factory=list)
    last_assessment_fatigue: Optional[float] = None
    last_assessment_engagement: Optional[float] = None
    last_focus_skill: str = ""
    last_assessed_node_id: str = ""
    last_student_text: str = ""


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
    last_practiced_timestamp: float = 0.0
    half_life_hours: float = 24.0
    next_review_timestamp: float = 0.0
    last_recall_prob: float = 0.0


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

    DEFAULT_HALF_LIFE_HOURS = 24.0
    MIN_HALF_LIFE_HOURS = 2.0
    MAX_HALF_LIFE_HOURS = 24.0 * 90.0
    REVIEW_TARGET_RECALL = 0.6
    REVIEW_DUE_RECALL_THRESHOLD = 0.45
    ENRICH_MIN_EFFECTIVE_MASTERY = 0.85

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
        lesson.last_focus_skill = skill or lesson.last_focus_skill
        lesson.last_assessed_node_id = node_id or lesson.last_assessed_node_id
        lesson.last_student_text = assessment.get("student_text", "").strip()

        # Persist continuous state signals from assessment.
        fatigue = assessment.get("fatigue")
        if fatigue is not None:
            fatigue = max(0.0, min(1.0, float(fatigue)))
            lesson.last_assessment_fatigue = fatigue
            lesson.fatigue_history.append(fatigue)
            if len(lesson.fatigue_history) > 20:
                lesson.fatigue_history = lesson.fatigue_history[-20:]

        engagement = assessment.get("engagement")
        if engagement is not None:
            engagement = max(0.0, min(1.0, float(engagement)))
            lesson.last_assessment_engagement = engagement
            lesson.engagement_history.append(engagement)
            if len(lesson.engagement_history) > 20:
                lesson.engagement_history = lesson.engagement_history[-20:]

        # Aggregate timing signals for cross-turn fatigue estimation.
        lesson.total_student_speaking_time_ms += int(assessment.get("duration_ms", 0) or 0)
        lesson.total_silence_time_ms += int(assessment.get("silence_before_ms", 0) or 0)

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
                learner.skills[skill] = MasteryRecord(
                    half_life_hours=self.DEFAULT_HALF_LIFE_HOURS,
                )
            mr = learner.skills[skill]
            now_ts = time.time()
            recall_before = self._compute_recall_probability(mr, now_ts)
            effective_before = self._compute_effective_mastery(
                mr, now_ts, recall_prob=recall_before,
            )
            mr.exposures += 1

            if is_correct:
                mr.consecutive_correct += 1
                mr.consecutive_wrong = 0
                mr.mastery = min(1.0, effective_before + 0.12 * (1.0 - effective_before))
                growth = 1.15 + min(0.5, recall_before * 0.35 + mr.consecutive_correct * 0.06)
                mr.half_life_hours = min(
                    self.MAX_HALF_LIFE_HOURS,
                    max(self.MIN_HALF_LIFE_HOURS, mr.half_life_hours * growth),
                )
                mr.last_recall_prob = 1.0
            else:
                mr.consecutive_correct = 0
                mr.consecutive_wrong += 1
                mr.mastery = max(0.0, effective_before * 0.8 - 0.05)
                shrink = max(0.35, 0.72 - min(0.25, mr.consecutive_wrong * 0.06))
                mr.half_life_hours = max(
                    self.MIN_HALF_LIFE_HOURS,
                    mr.half_life_hours * shrink,
                )
                mr.last_error = assessment.get("error_type", "")
                mr.last_error_time = now_ts
                mr.last_recall_prob = max(0.0, recall_before - 0.2)

            mr.last_practiced_timestamp = now_ts
            mr.review_due = False
            self._schedule_next_review(mr, now_ts)

    def record_node_visit(self, session_id: str, node_id: str) -> None:
        lesson = self._lesson[session_id]
        lesson.visited_node_path.append(node_id)

    def record_explanation(self, session_id: str, explanation: str) -> None:
        self._lesson[session_id].explanations_given.append(explanation)

    def record_example(self, session_id: str, example: str) -> None:
        self._lesson[session_id].examples_given.append(example)

    def record_subgraph(self, session_id: str, subgraph_id: str) -> None:
        self._lesson[session_id].subgraphs_inserted.append(subgraph_id)

    def record_node_context(self, session_id: str, node) -> None:
        """Append lightweight node metadata for rhythm-aware policy decisions."""
        hot = self._hot[session_id]
        trace_item = {
            "node_id": getattr(node, "node_id", ""),
            "node_type": getattr(node, "node_type", ""),
            "modality": getattr(node, "modality", ""),
            "interaction_pattern": getattr(node, "interaction_pattern", ""),
            "cognitive_level": getattr(node, "cognitive_level", ""),
            "energy_level": getattr(node, "energy_level", ""),
            "language_skill": list(getattr(node, "language_skill", []) or []),
            "timestamp": time.time(),
        }
        hot.recent_node_trace.append(trace_item)
        if len(hot.recent_node_trace) > 20:
            hot.recent_node_trace = hot.recent_node_trace[-20:]

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
        - mastery: dict[str, float] (decayed by forgetting model)
        - mastery_raw: dict[str, float] (pre-decay)
        - review_due_skills: list[str]
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
            "mastery_raw": {},
            "review_due_skills": [],
            "consecutive_failures": 0,
            "error_severity": 0.5,
            "time_pressure": 0.0,
        }

        now_ts = time.time()

        # Mastery snapshot with forgetting curve applied.
        for skill, mr in learner.skills.items():
            recall_prob = self._compute_recall_probability(mr, now_ts)
            effective_mastery = self._compute_effective_mastery(
                mr, now_ts, recall_prob=recall_prob,
            )
            signals["mastery"][skill] = effective_mastery
            signals["mastery_raw"][skill] = mr.mastery
            mr.last_recall_prob = recall_prob
            mr.review_due = self._is_review_due(mr, now_ts, recall_prob)

        signals["review_due_skills"] = [
            skill for skill, mr in learner.skills.items() if mr.review_due
        ]

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
            effective_mastery = signals["mastery"].get(skill, mr.mastery)
            if effective_mastery > self.ENRICH_MIN_EFFECTIVE_MASTERY and mr.consecutive_correct >= 3:
                if skill not in lesson.covered_skills or mr.consecutive_correct >= 5:
                    signals["should_enrich"] = True
                    signals["enrich_skill"] = skill
                    break

        # Should backtrack? detect explicit requests to revisit old content.
        backtrack_intent = self._detect_backtrack_intent(lesson.last_student_text)
        if backtrack_intent:
            skill = self._detect_backtrack_skill(lesson.last_student_text, lesson, learner)
            target_node = self._find_backtrack_target_node(
                lesson, current_node_id=hot.current_node_id, skill=skill,
            )
            if skill:
                signals["should_backtrack"] = True
                signals["backtrack_skill"] = skill
                signals["backtrack_target"] = target_node

        # Time pressure
        elapsed = time.time() - lesson.lesson_start_time
        # Assume 30-minute lesson
        signals["time_pressure"] = min(1.0, max(0.0, elapsed / 1800.0))

        # Fatigue: prioritize assessment value, then blend with trend + heuristic.
        heuristic_fatigue = min(
            1.0,
            hot.turn_number * 0.02 + lesson.total_silence_time_ms / 60000.0 * 0.1,
        )
        fatigue_values = lesson.fatigue_history[-3:]
        recent_fatigue = (
            sum(fatigue_values) / len(fatigue_values)
            if fatigue_values else lesson.last_assessment_fatigue
        )
        if recent_fatigue is None:
            signals["fatigue"] = heuristic_fatigue
        else:
            signals["fatigue"] = max(
                0.0,
                min(1.0, 0.75 * recent_fatigue + 0.25 * heuristic_fatigue),
            )

        # Engagement: use assessment history instead of constant default.
        engagement_values = lesson.engagement_history[-3:]
        if engagement_values:
            signals["engagement"] = max(
                0.0, min(1.0, sum(engagement_values) / len(engagement_values)),
            )
        elif lesson.last_assessment_engagement is not None:
            signals["engagement"] = lesson.last_assessment_engagement

        # Should slow down? high fatigue or low engagement
        if signals["fatigue"] > 0.7 or signals["engagement"] < 0.3:
            signals["should_slow_down"] = True

        return signals

    # --- Internal signal helpers ---

    @staticmethod
    def _detect_backtrack_intent(student_text: str) -> bool:
        text = (student_text or "").strip().lower()
        if not text:
            return False

        keywords = (
            "again", "go back", "backtrack", "review", "earlier", "before",
            "previous", "last time", "what did", "can we revisit",
            "之前", "刚才", "前面", "上一个", "回到", "复习", "再讲", "再说",
        )
        return any(k in text for k in keywords)

    def _detect_backtrack_skill(
        self,
        student_text: str,
        lesson: LessonMemory,
        learner: LearnerMemory,
    ) -> str:
        text = (student_text or "").lower()
        if not text:
            return lesson.last_focus_skill

        candidate_skills = set(lesson.covered_skills) | set(learner.skills.keys())
        matches = [skill for skill in candidate_skills if skill and skill.lower() in text]
        if matches:
            # Prefer the longest match to avoid short-token accidental hits.
            matches.sort(key=len, reverse=True)
            return matches[0]

        # Fall back to most recently assessed/errored skill.
        if lesson.last_focus_skill:
            return lesson.last_focus_skill
        if lesson.error_log:
            return lesson.error_log[-1].get("skill", "")
        return ""

    @staticmethod
    def _find_backtrack_target_node(
        lesson: LessonMemory,
        current_node_id: Optional[str],
        skill: str,
    ) -> str:
        if skill:
            for err in reversed(lesson.error_log):
                if err.get("skill") == skill and err.get("node_id") != current_node_id:
                    return err.get("node_id", "")

        for node_id in reversed(lesson.visited_node_path):
            if node_id and node_id != current_node_id:
                return node_id

        if lesson.last_assessed_node_id and lesson.last_assessed_node_id != current_node_id:
            return lesson.last_assessed_node_id
        return ""

    # --- Spaced repetition / forgetting model ---

    def get_due_reviews(
        self,
        student_id: str,
        now_ts: Optional[float] = None,
        limit: int = 20,
    ) -> list[dict]:
        if student_id not in self._learner:
            return []
        now_ts = now_ts or time.time()
        learner = self._learner[student_id]
        self._refresh_review_flags(learner, now_ts)

        due: list[dict] = []
        for skill, mr in learner.skills.items():
            if not mr.review_due:
                continue
            recall_prob = self._compute_recall_probability(mr, now_ts)
            effective_mastery = self._compute_effective_mastery(
                mr, now_ts, recall_prob=recall_prob,
            )
            hours_since_practice = 0.0
            if mr.last_practiced_timestamp > 0:
                hours_since_practice = max(
                    0.0, (now_ts - mr.last_practiced_timestamp) / 3600.0,
                )

            overdue_hours = 0.0
            if mr.next_review_timestamp > 0 and now_ts > mr.next_review_timestamp:
                overdue_hours = (now_ts - mr.next_review_timestamp) / 3600.0

            urgency = (
                (1.0 - recall_prob)
                + 0.5 * (1.0 - effective_mastery)
                + min(0.4, max(0, mr.consecutive_wrong) * 0.08)
                + min(0.4, max(0.0, overdue_hours) / 24.0 * 0.15)
            )

            due.append({
                "skill": skill,
                "urgency": urgency,
                "recall_prob": recall_prob,
                "effective_mastery": effective_mastery,
                "raw_mastery": mr.mastery,
                "half_life_hours": mr.half_life_hours,
                "hours_since_practice": hours_since_practice,
                "last_practiced_timestamp": mr.last_practiced_timestamp,
                "next_review_timestamp": mr.next_review_timestamp,
                "consecutive_wrong": mr.consecutive_wrong,
            })

        due.sort(key=lambda x: x["urgency"], reverse=True)
        return due[:max(1, limit)]

    def get_review_schedule(
        self,
        student_id: str,
        now_ts: Optional[float] = None,
        limit: int = 50,
    ) -> list[dict]:
        if student_id not in self._learner:
            return []
        now_ts = now_ts or time.time()
        learner = self._learner[student_id]
        self._refresh_review_flags(learner, now_ts)

        schedule: list[dict] = []
        for skill, mr in learner.skills.items():
            recall_prob = self._compute_recall_probability(mr, now_ts)
            effective_mastery = self._compute_effective_mastery(
                mr, now_ts, recall_prob=recall_prob,
            )
            schedule.append({
                "skill": skill,
                "review_due": mr.review_due,
                "next_review_timestamp": mr.next_review_timestamp,
                "recall_prob": recall_prob,
                "effective_mastery": effective_mastery,
                "half_life_hours": mr.half_life_hours,
            })

        schedule.sort(key=lambda x: (x["next_review_timestamp"] <= 0, x["next_review_timestamp"]))
        return schedule[:max(1, limit)]

    def _refresh_review_flags(self, learner: LearnerMemory, now_ts: float) -> None:
        for mr in learner.skills.values():
            if mr.half_life_hours <= 0:
                mr.half_life_hours = self.DEFAULT_HALF_LIFE_HOURS
            if mr.last_practiced_timestamp > 0 and mr.next_review_timestamp <= 0:
                self._schedule_next_review(mr, mr.last_practiced_timestamp)
            recall_prob = self._compute_recall_probability(mr, now_ts)
            mr.last_recall_prob = recall_prob
            mr.review_due = self._is_review_due(mr, now_ts, recall_prob)

    def _compute_recall_probability(
        self,
        mr: MasteryRecord,
        now_ts: float,
    ) -> float:
        if mr.last_practiced_timestamp <= 0:
            return max(0.0, min(1.0, mr.mastery))

        elapsed_hours = max(0.0, (now_ts - mr.last_practiced_timestamp) / 3600.0)
        half_life = max(self.MIN_HALF_LIFE_HOURS, min(self.MAX_HALF_LIFE_HOURS, mr.half_life_hours))
        recall_prob = 2.0 ** (-elapsed_hours / half_life)
        return max(0.0, min(1.0, recall_prob))

    def _compute_effective_mastery(
        self,
        mr: MasteryRecord,
        now_ts: float,
        recall_prob: Optional[float] = None,
    ) -> float:
        if mr.last_practiced_timestamp <= 0:
            return max(0.0, min(1.0, mr.mastery))
        recall_prob = (
            recall_prob if recall_prob is not None
            else self._compute_recall_probability(mr, now_ts)
        )
        effective = mr.mastery * recall_prob
        return max(0.0, min(1.0, effective))

    def _schedule_next_review(self, mr: MasteryRecord, now_ts: float) -> None:
        target = max(0.05, min(0.95, self.REVIEW_TARGET_RECALL))
        delta_hours = max(0.5, mr.half_life_hours * math.log2(1.0 / target))
        mr.next_review_timestamp = now_ts + delta_hours * 3600.0

    def _is_review_due(
        self,
        mr: MasteryRecord,
        now_ts: float,
        recall_prob: Optional[float] = None,
    ) -> bool:
        if mr.last_practiced_timestamp <= 0:
            return False
        recall_prob = (
            recall_prob if recall_prob is not None
            else self._compute_recall_probability(mr, now_ts)
        )
        if mr.next_review_timestamp > 0 and now_ts >= mr.next_review_timestamp:
            return True
        if recall_prob <= self.REVIEW_DUE_RECALL_THRESHOLD:
            return True
        if mr.consecutive_wrong >= 2 and recall_prob < 0.7:
            return True
        return False

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
        learner = self._learner[student_id]
        self._refresh_review_flags(learner, time.time())
        return learner

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

        # Refresh cross-session review schedule (forgetting-aware).
        now_ts = time.time()
        self._refresh_review_flags(learner, now_ts)
        due_reviews = self.get_due_reviews(student_id, now_ts=now_ts, limit=50)

        # Add review history entry
        learner.review_history.append({
            "session_id": session_id,
            "skills_covered": list(lesson.covered_skills),
            "subgraphs_inserted": lesson.subgraphs_inserted,
            "total_errors": len(lesson.error_log),
            "due_review_count": len(due_reviews),
            "due_review_skills": [r["skill"] for r in due_reviews[:10]],
            "timestamp": now_ts,
        })
