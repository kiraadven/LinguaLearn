"""
NodeTemplateLibrary - Loads and indexes offline YAML node templates.

Templates are multi-granularity building blocks. At runtime, the library
selects and instantiates templates into LiveNodes based on query criteria.
"""

from __future__ import annotations
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Optional

import yaml

from .schema import NodeTemplate, LiveNode


class NodeTemplateLibrary:
    """Loads templates from YAML files, indexes by type/tag/phase/granularity."""

    def __init__(self, templates_dir: Optional[Path] = None):
        self._templates: dict[str, NodeTemplate] = {}
        self._index_by_type: dict[str, list[str]] = defaultdict(list)
        self._index_by_tag: dict[str, list[str]] = defaultdict(list)
        self._index_by_phase: dict[str, list[str]] = defaultdict(list)
        self._index_by_granularity: dict[str, list[str]] = defaultdict(list)

        if templates_dir:
            self.load(templates_dir)

    def load(self, templates_dir: Path) -> None:
        """Walk templates_dir, parse YAML files, populate indices."""
        for yaml_file in templates_dir.rglob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not data:
                continue

            # Support single template or list of templates per file
            items = data if isinstance(data, list) else [data]
            for item in items:
                tpl = NodeTemplate(**item)
                self._templates[tpl.template_id] = tpl
                self._index_by_type[tpl.node_type].append(tpl.template_id)
                self._index_by_phase[tpl.phase].append(tpl.template_id)
                self._index_by_granularity[tpl.granularity].append(tpl.template_id)
                for tag in tpl.tags:
                    self._index_by_tag[tag].append(tpl.template_id)

    def get(self, template_id: str) -> NodeTemplate:
        return self._templates[template_id]

    def query(
        self,
        node_type: Optional[str] = None,
        phase: Optional[str] = None,
        tags: Optional[list[str]] = None,
        granularity: Optional[str] = None,
    ) -> list[NodeTemplate]:
        """Multi-criteria lookup. Returns templates matching ALL specified criteria."""
        candidate_ids: Optional[set[str]] = None

        if node_type:
            ids = set(self._index_by_type.get(node_type, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if phase:
            ids = set(self._index_by_phase.get(phase, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if granularity:
            ids = set(self._index_by_granularity.get(granularity, []))
            candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if tags:
            for tag in tags:
                ids = set(self._index_by_tag.get(tag, []))
                candidate_ids = ids if candidate_ids is None else candidate_ids & ids

        if candidate_ids is None:
            return list(self._templates.values())

        return [self._templates[tid] for tid in candidate_ids if tid in self._templates]

    def instantiate(
        self,
        template_id: str,
        params: dict,
        node_id: Optional[str] = None,
    ) -> LiveNode:
        """Create a LiveNode from a template + runtime params.

        params should include:
        - skill / learning_targets
        - content_pack (resolved content)
        - title (optional override)
        - Any template variable values for Jinja2 goal template
        """
        tpl = self._templates[template_id]

        if node_id is None:
            node_id = f"{tpl.node_type}_{uuid.uuid4().hex[:8]}"

        # Instantiate teacher_goal from template
        teacher_goal = tpl.teacher_goal_template
        for key, val in params.items():
            teacher_goal = teacher_goal.replace("{{" + key + "}}", str(val))

        learning_targets = params.get("learning_targets", [])
        if isinstance(learning_targets, str):
            learning_targets = [learning_targets]

        return LiveNode(
            node_id=node_id,
            template_id=template_id,
            node_type=tpl.node_type,
            phase=tpl.phase,
            title=params.get("title", f"{tpl.node_type}: {', '.join(learning_targets)}"),
            learning_targets=learning_targets,
            teacher_goal=teacher_goal,
            expected_student_evidence=list(tpl.expected_evidence_types),
            content_pack=params.get("content_pack", {}),
            policy_profile={
                "allowed_actions": list(tpl.allowed_policy_actions),
                "default_style": tpl.default_delivery_style,
                "success_threshold": tpl.success_threshold,
                "failure_budget": tpl.failure_budget,
            },
            tool_profile={
                "allowed_tool_actions": list(tpl.allowed_tool_actions),
            },
            memory_writeback=dict(tpl.memory_writeback_spec),
            llm_supervisor_allowed=tpl.llm_supervisor_allowed,
        )

    @property
    def template_count(self) -> int:
        return len(self._templates)

    @property
    def available_types(self) -> list[str]:
        return list(self._index_by_type.keys())
