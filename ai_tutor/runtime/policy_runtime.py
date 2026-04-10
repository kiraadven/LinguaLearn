"""
PolicyRuntime - Graph-aware policy selector.

Replaces the old RuleBasedPolicy. Reads current LiveNode's allowed actions,
combines with HotMemory state, and applies rule cascade to select:
- policy_action: what teaching move to make
- tool_action: what classroom tool to invoke (nullable)
- delivery_style: how to say it (maps to voice model params)

LLM is NOT involved. This is pure rule-based, low-latency decision making.
"""

from __future__ import annotations
from typing import Optional

from ..graph.schema import LiveNode
from .memory import HotMemory


class PolicyRuntime:
    INTERACTIVE_ACTIONS = {
        "ask_open", "ask_check", "ask_recall",
        "hint_light", "hint_strong", "scaffold_step",
    }

    NEW_KNOWLEDGE_NODE_TYPES = {
        "hook",
        "explain",
        "vocabulary_focus",
        "worked_example",
        "listening_comprehension",
        "reading_comprehension",
        "cultural_note",
        "transition",
    }

    TEACHER_LED_PATTERNS = {"teacher_monologue"}

    HIGH_ENERGY = {"high"}

    @staticmethod
    def _suffix_count(items: list[dict], predicate) -> int:
        count = 0
        for item in reversed(items):
            if predicate(item):
                count += 1
            else:
                break
        return count

    def select_action(
        self,
        current_node: LiveNode,
        hot_memory: HotMemory,
        assessment: dict,
    ) -> tuple[str, Optional[str], str]:
        """Select (policy_action, tool_action, delivery_style) for this turn.

        Rule cascade:
        1. If fatigue > 0.7 -> encourage + calm_reset
        2. If in repair mode -> constrained repair actions
        3. If student correct -> advance + appropriate celebration
        4. If student error -> hint/re-explain based on error count vs budget
        5. If silence -> pause_wait or encourage
        6. Default: node default action + style
        """
        allowed = current_node.policy_profile.get("allowed_actions", [])
        default_style = current_node.policy_profile.get("default_style", "neutral_teach")
        failure_budget = current_node.policy_profile.get("failure_budget", 2)

        fatigue = assessment.get("fatigue", 0.0)
        engagement = assessment.get("engagement", 0.5)
        is_correct = assessment.get("is_correct", False)
        error_type = assessment.get("error_type", "")
        is_silence = assessment.get("is_silence", False)
        consecutive_failures = current_node.failure_count

        policy_action = ""
        tool_action: Optional[str] = None
        delivery_style = default_style

        # Rule 1: Fatigue override
        if fatigue > 0.7:
            policy_action = self._pick(allowed, "encourage", "pause_wait")
            delivery_style = "calm_reset"

        # Rule 2: Repair mode
        elif hot_memory.is_repair_mode:
            if is_correct:
                policy_action = self._pick(allowed, "advance", "encourage")
                delivery_style = "celebrate_success"
            else:
                policy_action = self._pick(allowed, "re_explain_simplify",
                                           "hint_strong", "scaffold_step")
                delivery_style = "slow_repair"

        # Rule 3: Student correct
        elif is_correct:
            if current_node.success_count >= 1:
                policy_action = self._pick(allowed, "advance")
                delivery_style = "energetic_advance"
            else:
                policy_action = self._pick(allowed, "encourage", "advance")
                delivery_style = "warm_encourage"

        # Rule 4: Student error
        elif error_type:
            if consecutive_failures >= failure_budget:
                policy_action = self._pick(allowed, "direct_correct",
                                           "re_explain_simplify")
                delivery_style = "firm_corrective"
            elif consecutive_failures >= 1:
                policy_action = self._pick(allowed, "hint_strong",
                                           "re_explain_brief", "scaffold_step")
                delivery_style = "gentle_corrective"
            else:
                policy_action = self._pick(allowed, "hint_light", "ask_recall")
                delivery_style = "curious_probe"

        # Rule 5: Silence
        elif is_silence:
            policy_action = self._pick(allowed, "pause_wait", "encourage",
                                       "hint_light")
            delivery_style = "warm_encourage"

        # Rule 6: Default
        else:
            policy_action = self._pick(allowed, "ask_open", "ask_check")
            delivery_style = default_style

        # Tool action: context-dependent
        tool_action = self._select_tool(current_node, assessment)

        rhythm = self._build_rhythm_context(hot_memory, current_node)
        policy_action, tool_action, delivery_style = self._apply_rhythm_adjustments(
            allowed=allowed,
            current_node=current_node,
            assessment=assessment,
            rhythm=rhythm,
            policy_action=policy_action,
            tool_action=tool_action,
            delivery_style=delivery_style,
        )

        return policy_action, tool_action, delivery_style

    def determine_event(
        self,
        current_node: LiveNode,
        assessment: dict,
        hot_memory: HotMemory,
    ) -> str:
        """Map assessment to transition event for graph traversal."""
        is_correct = assessment.get("is_correct", False)
        is_silence = assessment.get("is_silence", False)
        is_off_topic = assessment.get("is_off_topic", False)
        error_severity = assessment.get("error_severity", 0.0)

        if is_off_topic:
            return "on_off_topic"
        if is_silence:
            return "on_silence"
        if is_correct:
            return "on_success"
        if error_severity > 0.7:
            return "on_major_error"
        return "on_minor_error"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick(allowed: list[str], *preferences: str) -> str:
        """Pick the first preferred action that is in the allowed list."""
        for pref in preferences:
            if pref in allowed:
                return pref
        return allowed[0] if allowed else "encourage"

    def _build_rhythm_context(self, hot: HotMemory, current_node: LiveNode) -> dict:
        trace = list(hot.recent_node_trace[-8:])
        if not trace:
            trace = [{
                "node_type": current_node.node_type,
                "interaction_pattern": current_node.interaction_pattern,
                "cognitive_level": current_node.cognitive_level,
                "energy_level": current_node.energy_level,
                "language_skill": list(current_node.language_skill),
            }]

        speaking_streak = self._suffix_count(
            trace,
            lambda i: "speaking" in set(i.get("language_skill", [])),
        )
        high_energy_streak = self._suffix_count(
            trace,
            lambda i: i.get("energy_level", "") in self.HIGH_ENERGY,
        )
        new_knowledge_streak = self._suffix_count(
            trace,
            lambda i: (
                i.get("node_type", "") in self.NEW_KNOWLEDGE_NODE_TYPES
                or i.get("cognitive_level", "") == "recognition"
            ),
        )
        monologue_streak = self._suffix_count(
            trace,
            lambda i: i.get("interaction_pattern", "") in self.TEACHER_LED_PATTERNS,
        )

        recent_turns = hot.recent_turns[-6:]
        teacher_turn_streak = self._suffix_count(
            recent_turns,
            lambda t: t.get("role") == "teacher",
        )

        return {
            "speaking_streak": speaking_streak,
            "high_energy_streak": high_energy_streak,
            "new_knowledge_streak": new_knowledge_streak,
            "monologue_streak": monologue_streak,
            "teacher_turn_streak": teacher_turn_streak,
        }

    def _apply_rhythm_adjustments(
        self,
        allowed: list[str],
        current_node: LiveNode,
        assessment: dict,
        rhythm: dict,
        policy_action: str,
        tool_action: Optional[str],
        delivery_style: str,
    ) -> tuple[str, Optional[str], str]:
        """Post-process base policy with classroom rhythm constraints."""
        is_silence = assessment.get("is_silence", False)
        error_type = assessment.get("error_type", "")
        is_correct = assessment.get("is_correct", False)

        # Energy curve: after high-intensity streak, force a low-intensity beat.
        if rhythm.get("high_energy_streak", 0) >= 2:
            policy_action = self._pick(
                allowed, "encourage", "pause_wait", "re_explain_brief", policy_action,
            )
            delivery_style = "calm_reset"

        # Modality switch proxy: prolonged speaking streak -> introduce material/listening-reading.
        if not error_type and not is_silence and rhythm.get("speaking_streak", 0) >= 3:
            if "open_material_section" in current_node.tool_profile.get("allowed_tool_actions", []):
                tool_action = "open_material_section"
            if policy_action == "advance":
                policy_action = self._pick(
                    allowed, "ask_check", "ask_recall", "re_explain_brief", "encourage", policy_action,
                )
            if delivery_style in ("energetic_advance", "curious_probe"):
                delivery_style = "neutral_teach"

        # Cognitive load: too many new-knowledge chunks -> consolidation turn first.
        if not error_type and is_correct and rhythm.get("new_knowledge_streak", 0) >= 3:
            policy_action = self._pick(
                allowed, "ask_recall", "ask_check", "scaffold_step", "hint_light", policy_action,
            )
            delivery_style = "curious_probe"

        # Interaction density: long teacher-led stretch -> force student participation prompt.
        if (
            not error_type
            and not is_silence
            and (
                rhythm.get("monologue_streak", 0) >= 2
                or rhythm.get("teacher_turn_streak", 0) >= 2
            )
        ):
            if policy_action not in self.INTERACTIVE_ACTIONS:
                policy_action = self._pick(
                    allowed, "ask_open", "ask_check", "ask_recall", "hint_light", policy_action,
                )
            if delivery_style in ("energetic_advance", "neutral_teach"):
                delivery_style = "curious_probe"

        return policy_action, tool_action, delivery_style

    @staticmethod
    def _select_tool(node: LiveNode, assessment: dict) -> Optional[str]:
        """Select tool action based on context."""
        allowed_tools = node.tool_profile.get("allowed_tool_actions", [])
        if not allowed_tools:
            return None

        # If student made error related to video content -> rewind
        if assessment.get("error_type") and "rewind_video_5s" in allowed_tools:
            return "rewind_video_5s"

        # If presenting content -> open material section.
        if (
            node.node_type in (
                "explain",
                "vocabulary_focus",
                "listening_comprehension",
                "reading_comprehension",
                "cultural_note",
            )
            and "open_material_section" in allowed_tools
        ):
            return "open_material_section"

        return None
