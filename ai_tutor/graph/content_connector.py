"""
ContentConnector - Resolves content for graph nodes from multiple sources.

Priority order:
1. Offline content packs (md/json from website generation) - always preferred
2. Cached web search results
3. Live web search (async, with timeout fallback)

Also connects to policy documents for handling special situations
(emotional distress, safety, etc.).
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional


class ContentConnector:

    def __init__(
        self,
        content_packs_dir: Optional[Path] = None,
        policy_packs_dir: Optional[Path] = None,
        web_search_client=None,
    ):
        self._packs_dir = content_packs_dir
        self._policy_dir = policy_packs_dir
        self._web_search = web_search_client
        self._cache: dict[str, dict] = {}

    def resolve(
        self,
        skill: str,
        node_type: str,
        lang_level: str = "B1",
    ) -> dict:
        """Find and assemble content for a node.

        Returns:
            {
                "script_outline": [...],
                "examples": [...],
                "common_mistakes": [...],
                "media_anchors": [...],
                "supplementary_links": [...],
            }
        """
        cache_key = f"{skill}:{node_type}:{lang_level}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Priority 1: offline content pack
        content = self._resolve_from_pack(skill, node_type, lang_level)
        if content:
            self._cache[cache_key] = content
            return content

        # Priority 2: cached web search (already in self._cache, checked above)

        # Priority 3: live web search
        if self._web_search:
            content = self._resolve_from_web(skill, node_type, lang_level)
            if content:
                self._cache[cache_key] = content
                return content

        # Fallback: minimal content
        content = {
            "script_outline": [f"Teach {skill} at {lang_level} level"],
            "examples": [],
            "common_mistakes": [],
            "media_anchors": [],
            "supplementary_links": [],
        }
        self._cache[cache_key] = content
        return content

    def resolve_policy(self, situation: str) -> dict:
        """Retrieve teaching policy for a specific situation.

        Situations: emotional_distress, safety_concern, off_topic_persistent,
                    technical_failure, age_sensitive, etc.
        """
        if self._policy_dir is None:
            return {"action": "escalate_to_supervisor", "notes": "No policy pack available"}

        policy_file = self._policy_dir / f"{situation}.json"
        if policy_file.exists():
            with open(policy_file, "r", encoding="utf-8") as f:
                return json.load(f)

        policy_file_yaml = self._policy_dir / f"{situation}.yaml"
        if policy_file_yaml.exists():
            import yaml
            with open(policy_file_yaml, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)

        return {"action": "escalate_to_supervisor", "notes": f"No policy for: {situation}"}

    def bind_to_node(self, node, content: dict):
        """Attach resolved content to a LiveNode content_pack field."""
        node.content_pack = content
        return node

    # ------------------------------------------------------------------
    # Private resolvers
    # ------------------------------------------------------------------

    def _resolve_from_pack(self, skill: str, node_type: str,
                           lang_level: str) -> Optional[dict]:
        if self._packs_dir is None:
            return None

        # Try skill-specific file
        for ext in ("json", "md", "yaml"):
            pack_file = self._packs_dir / f"{skill}.{ext}"
            if pack_file.exists():
                return self._parse_pack_file(pack_file, node_type, lang_level)

        # Try directory-based organization
        skill_dir = self._packs_dir / skill
        if skill_dir.is_dir():
            for ext in ("json", "md", "yaml"):
                pack_file = skill_dir / f"{node_type}.{ext}"
                if pack_file.exists():
                    return self._parse_pack_file(pack_file, node_type, lang_level)

        return None

    def _parse_pack_file(self, path: Path, node_type: str,
                         lang_level: str) -> Optional[dict]:
        suffix = path.suffix.lower()
        try:
            if suffix == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return self._normalize_content(data, node_type, lang_level)
            elif suffix == ".yaml":
                import yaml
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                return self._normalize_content(data, node_type, lang_level)
            elif suffix == ".md":
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                return {
                    "script_outline": [text],
                    "examples": [],
                    "common_mistakes": [],
                    "media_anchors": [],
                    "supplementary_links": [],
                }
        except Exception:
            return None
        return None

    @staticmethod
    def _normalize_content(data: dict, node_type: str, lang_level: str) -> dict:
        return {
            "script_outline": data.get("script_outline", []),
            "examples": data.get("examples", []),
            "common_mistakes": data.get("common_mistakes", []),
            "media_anchors": data.get("media_anchors", []),
            "supplementary_links": data.get("supplementary_links", []),
        }

    def _resolve_from_web(self, skill: str, node_type: str,
                          lang_level: str) -> Optional[dict]:
        """Search web for supplementary teaching material.
        Requires web_search_client to be configured."""
        if self._web_search is None:
            return None
        # Delegate to web search client (implementation depends on search API)
        # Returns normalized content dict or None
        try:
            query = f"{skill} {node_type} teaching material {lang_level}"
            results = self._web_search.search(query, max_results=3)
            if results:
                return {
                    "script_outline": [],
                    "examples": [],
                    "common_mistakes": [],
                    "media_anchors": [],
                    "supplementary_links": [
                        {"title": r.get("title", ""), "url": r.get("url", "")}
                        for r in results
                    ],
                }
        except Exception:
            pass
        return None
