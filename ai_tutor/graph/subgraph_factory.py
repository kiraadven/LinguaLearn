"""
SubgraphFactory - Builds subgraphs for dynamic insertion.

Four subgraph types:
- repair:      Student failed a skill -> explain -> practice -> check
- backtrack:   Student asks about earlier content -> review -> check -> (practice)
- enrichment:  Advanced student -> challenge -> free_practice
- assessment:  Multi-skill micro quiz -> quiz_1 -> quiz_2 -> summary
"""

from __future__ import annotations
import uuid

from .schema import LiveNode, EdgeSpec, SubgraphSpec
from .node_templates import NodeTemplateLibrary


class SubgraphFactory:

    def __init__(self, template_library: NodeTemplateLibrary):
        self._templates = template_library

    def build_repair_subgraph(
        self,
        failed_skill: str,
        original_node_id: str,
        content_pack: dict,
        depth: str = "standard",
    ) -> SubgraphSpec:
        """Build a repair subgraph for a skill the student failed on.

        Depth levels:
        - micro:    repair_explain -> repair_check
        - standard: repair_explain -> repair_practice -> repair_check
        - deep:     repair_explain -> repair_worked_example -> repair_practice -> repair_check
        """
        sg_id = f"repair_{uuid.uuid4().hex[:8]}"
        nodes: list[LiveNode] = []
        edges: list[EdgeSpec] = []

        # Always start with explain
        explain = self._make_node(sg_id, "repair", "explain", failed_skill, content_pack)
        nodes.append(explain)

        if depth == "deep":
            worked = self._make_node(sg_id, "repair", "worked_example", failed_skill, content_pack)
            nodes.append(worked)
            edges.append(EdgeSpec(explain.node_id, worked.node_id, "on_success"))

        if depth in ("standard", "deep"):
            practice = self._make_node(sg_id, "repair", "guided_practice", failed_skill, content_pack)
            nodes.append(practice)
            prev = nodes[-2]
            edges.append(EdgeSpec(prev.node_id, practice.node_id, "on_success"))

        # Always end with check
        check = self._make_node(sg_id, "repair", "check_understanding", failed_skill, content_pack)
        nodes.append(check)
        prev = nodes[-2]
        edges.append(EdgeSpec(prev.node_id, check.node_id, "on_success"))

        # Retry loop: check failure -> back to explain
        edges.append(EdgeSpec(check.node_id, explain.node_id, "on_major_error", weight=2.0))

        return SubgraphSpec(
            subgraph_id=sg_id,
            entry_node_id=explain.node_id,
            exit_node_id=check.node_id,
            nodes=nodes,
            edges=edges,
            purpose="repair",
            target_skill=failed_skill,
            source_node_id=original_node_id,
        )

    def build_backtrack_subgraph(
        self,
        target_skill: str,
        previous_node_id: str,
        content_pack: dict,
    ) -> SubgraphSpec:
        """Build a subgraph that reviews previously-covered material.

        Structure: review_recall -> review_check -> (optional review_practice)
        """
        sg_id = f"backtrack_{uuid.uuid4().hex[:8]}"

        recall = self._make_node(sg_id, "backtrack", "review", target_skill, content_pack)
        check = self._make_node(sg_id, "backtrack", "check_understanding", target_skill, content_pack)

        edges = [
            EdgeSpec(recall.node_id, check.node_id, "on_success"),
            EdgeSpec(check.node_id, recall.node_id, "on_major_error", weight=2.0),
        ]

        return SubgraphSpec(
            subgraph_id=sg_id,
            entry_node_id=recall.node_id,
            exit_node_id=check.node_id,
            nodes=[recall, check],
            edges=edges,
            purpose="backtrack",
            target_skill=target_skill,
            source_node_id=previous_node_id,
        )

    def build_enrichment_subgraph(
        self,
        skill: str,
        content_pack: dict,
    ) -> SubgraphSpec:
        """Build enrichment subgraph for advanced students.

        Structure: enrichment_challenge -> enrichment_free_practice
        """
        sg_id = f"enrich_{uuid.uuid4().hex[:8]}"

        challenge = self._make_node(sg_id, "enrichment", "guided_practice", skill, content_pack)
        free = self._make_node(sg_id, "enrichment", "free_practice", skill, content_pack)

        edges = [EdgeSpec(challenge.node_id, free.node_id, "on_success")]

        return SubgraphSpec(
            subgraph_id=sg_id,
            entry_node_id=challenge.node_id,
            exit_node_id=free.node_id,
            nodes=[challenge, free],
            edges=edges,
            purpose="enrichment",
            target_skill=skill,
        )

    def build_assessment_subgraph(
        self,
        skills: list[str],
        content_packs: Optional[dict] = None,
    ) -> SubgraphSpec:
        """Build micro-assessment subgraph testing multiple skills.

        Structure: quiz_node_1 -> quiz_node_2 -> ... -> summary_node
        """
        sg_id = f"assess_{uuid.uuid4().hex[:8]}"
        content_packs = content_packs or {}
        nodes: list[LiveNode] = []
        edges: list[EdgeSpec] = []

        for skill in skills:
            quiz = self._make_node(sg_id, "assessment", "check_understanding", skill,
                                   content_packs.get(skill, {}))
            if nodes:
                edges.append(EdgeSpec(nodes[-1].node_id, quiz.node_id, "on_success"))
                edges.append(EdgeSpec(nodes[-1].node_id, quiz.node_id, "on_minor_error"))
            nodes.append(quiz)

        # Summary node
        summary = LiveNode(
            node_id=f"{sg_id}_summary",
            template_id="wrap_up_generic",
            node_type="wrap_up",
            phase="review",
            title="Assessment Summary",
            learning_targets=skills,
            teacher_goal="Summarize assessment results",
            expected_student_evidence=[],
            policy_profile={"allowed_actions": ["wrap_up", "encourage"], "failure_budget": 0},
        )
        nodes.append(summary)
        if len(nodes) >= 2:
            edges.append(EdgeSpec(nodes[-2].node_id, summary.node_id, "on_success"))
            edges.append(EdgeSpec(nodes[-2].node_id, summary.node_id, "on_minor_error"))

        return SubgraphSpec(
            subgraph_id=sg_id,
            entry_node_id=nodes[0].node_id,
            exit_node_id=summary.node_id,
            nodes=nodes,
            edges=edges,
            purpose="assessment",
        )

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _make_node(self, sg_id: str, purpose: str, node_type: str,
                   skill: str, content_pack: dict) -> LiveNode:
        """Create a LiveNode for a subgraph, using template library if available."""
        node_id = f"{sg_id}_{node_type}_{uuid.uuid4().hex[:6]}"

        # Try to find a matching template
        templates = self._templates.query(node_type=node_type, tags=[purpose])
        if not templates:
            templates = self._templates.query(node_type=node_type)

        if templates:
            return self._templates.instantiate(
                templates[0].template_id,
                params={
                    "learning_targets": [skill],
                    "skill": skill,
                    "content_pack": content_pack,
                    "title": f"{purpose} {node_type}: {skill}",
                },
                node_id=node_id,
            )

        # Fallback: create minimal node without template
        return LiveNode(
            node_id=node_id,
            template_id=f"{purpose}_{node_type}_fallback",
            node_type=node_type,
            phase="practice" if "practice" in node_type else "review",
            title=f"{purpose} {node_type}: {skill}",
            learning_targets=[skill],
            teacher_goal=f"{purpose}: {node_type} for {skill}",
            expected_student_evidence=["student_response"],
            content_pack=content_pack,
            policy_profile={
                "allowed_actions": ["hint_light", "re_explain_brief", "encourage", "direct_correct"],
                "default_style": "gentle_corrective",
                "failure_budget": 2,
            },
        )


# Type hint for optional import
from typing import Optional  # noqa: E402
