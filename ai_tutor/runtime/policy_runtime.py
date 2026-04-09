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

    @staticmethod
    def _select_tool(node: LiveNode, assessment: dict) -> Optional[str]:
        """Select tool action based on context."""
        allowed_tools = node.tool_profile.get("allowed_tool_actions", [])
        if not allowed_tools:
            return None

        # If student made error related to video content -> rewind
        if assessment.get("error_type") and "rewind_video_5s" in allowed_tools:
            return "rewind_video_5s"

        # If explaining -> open material
        if node.node_type == "explain" and "open_material_section" in allowed_tools:
            return "open_material_section"

        return None
