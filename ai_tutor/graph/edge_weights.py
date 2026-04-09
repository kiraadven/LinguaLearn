"""
EdgeWeightComputer - Computes edge weights from memory layer signals.

Weight semantics: LOWER weight = MORE preferred path (cost).

Signals from MemoryManager drive weight adjustments:
- Student mastery of target skill
- Fatigue level
- Engagement level
- Error severity and consecutive failure count
- Time pressure (lesson time remaining)
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .graph_engine import LessonGraph


# Base weights for different edge event types
BASE_WEIGHTS = {
    "on_success": 1.0,
    "on_minor_error": 1.5,
    "on_major_error": 2.0,
    "on_silence": 1.8,
    "on_off_topic": 2.5,
    "on_backtrack": 1.2,
    "auto_advance": 0.8,
}


class EdgeWeightComputer:
    """Computes dynamic edge weights based on student state signals.

    For each outgoing edge from a node:

    on_success edge:
      weight = base * (1 - mastery_of_target_skill)
      -> Lower when student has HIGH mastery -> prefer advancing

    on_minor_error / on_major_error edge:
      weight = base * (1 - fatigue) * error_severity
      -> Lower when student is tired (prefer gentler path)

    repair edge:
      weight = base / (1 + consecutive_failure_count)
      -> Lower (preferred) when student is failing repeatedly

    Additional modifiers:
    - Low engagement -> increase "same topic" weights, decrease "interactive" weights
    - High fatigue -> decrease "encourage/break" edge weights
    - Time pressure -> increase optional enrichment edge weights
    """

    def compute_weights(
        self,
        graph: LessonGraph,
        node_id: str,
        signals: dict,
    ) -> dict[tuple[str, str], float]:
        """Compute new weights for all outgoing edges from node_id.

        Args:
            graph: The lesson graph
            node_id: Node to compute weights for
            signals: Memory signals dict with keys:
                - mastery: dict[str, float]  (skill_id -> 0.0-1.0)
                - fatigue: float (0.0-1.0)
                - engagement: float (0.0-1.0)
                - consecutive_failures: int
                - error_severity: float (0.0-1.0)
                - time_pressure: float (0.0-1.0, higher = less time)

        Returns:
            {(source_id, target_id): new_weight}
        """
        mastery = signals.get("mastery", {})
        fatigue = signals.get("fatigue", 0.0)
        engagement = signals.get("engagement", 0.5)
        consecutive_failures = signals.get("consecutive_failures", 0)
        error_severity = signals.get("error_severity", 0.5)
        time_pressure = signals.get("time_pressure", 0.0)

        result: dict[tuple[str, str], float] = {}

        for _, target, data in graph.G.out_edges(node_id, data=True):
            event = data.get("event", "auto_advance")
            base = BASE_WEIGHTS.get(event, 1.0)

            # Get target node's skill for mastery lookup
            target_node = graph.get_node(target)
            target_mastery = max(
                (mastery.get(s, 0.5) for s in target_node.learning_targets),
                default=0.5,
            )

            weight = base

            if event == "on_success":
                # High mastery -> lower weight -> prefer advancing
                weight = base * (1.0 - target_mastery * 0.6)

            elif event in ("on_minor_error", "on_major_error"):
                # Fatigue modifies error handling preference
                fatigue_factor = max(0.3, 1.0 - fatigue * 0.5)
                weight = base * fatigue_factor * max(0.3, error_severity)

            elif event == "on_backtrack":
                # More preferred when consecutive failures are high
                weight = base / (1.0 + consecutive_failures * 0.3)

            elif event == "auto_advance":
                # Time pressure makes auto-advance more preferred
                weight = base * (1.0 - time_pressure * 0.3)

            # Global modifiers
            # Low engagement -> prefer interactive nodes
            if engagement < 0.3 and target_node.node_type in ("guided_practice", "free_practice"):
                weight *= 0.7
            elif engagement < 0.3 and target_node.node_type == "explain":
                weight *= 1.3

            # High fatigue -> prefer wrap_up, transition
            if fatigue > 0.7 and target_node.node_type in ("wrap_up", "transition"):
                weight *= 0.6

            # Time pressure -> penalize enrichment
            if time_pressure > 0.6 and target_node.node_type in ("free_practice",):
                weight *= 1.5

            result[(node_id, target)] = max(0.1, weight)

        return result
