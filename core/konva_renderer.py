"""
Konva Renderer — Python wrapper for Node.js konva-node rendering sidecar.

Calls core/konva_render_worker.js via subprocess, feeding it Timeline JSON
+ sentence data on stdin, and receiving per-element PNG paths + positions.

This provides same-source rendering: the browser (vue-konva) and this Node.js
worker use the identical shared/ rendering engine.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


# Resolve paths
_CORE_DIR = Path(__file__).parent
_PROJECT_ROOT = _CORE_DIR.parent
_WORKER_SCRIPT = _CORE_DIR / "konva_render_worker.mjs"
_NODE_BIN = "node"


class KonvaRenderer:
    """
    Renders Timeline JSON elements to PNG files using konva-node.

    Usage:
        renderer = KonvaRenderer()
        results = renderer.render_all_sentences(timeline_json, sentences_data, output_dir)
        # results (new): {
        #   0: {
        #     'p_1': { 'subtitle_1': ('/path/to/s0000_p00_...png', 96, 820), ... },
        #     'p_2': { ... },
        #   },
        #   1: { ... },
        # }
        # results (legacy): { 0: { 'subtitle_1': (...) } }
    """

    def __init__(self):
        if not _WORKER_SCRIPT.exists():
            raise FileNotFoundError(f"Konva render worker not found: {_WORKER_SCRIPT}")

    def render_all_sentences(
        self,
        timeline: dict,
        sentences_data: List[Dict],
        output_dir: str,
        resolution: Optional[Dict] = None,
    ) -> Dict[int, Union[Dict[str, Tuple[str, int, int]], Dict[str, Dict[str, Tuple[str, int, int]]]]]:
        """
        Render all elements for all sentences in a single Node.js subprocess call.

        Args:
            timeline: Complete Timeline JSON
            sentences_data: List of sentence dicts with original_text, key_words, etc.
            output_dir: Directory for output PNG files
            resolution: Override resolution, e.g. {"width": 1920, "height": 1080}

        Returns:
            Dict mapping sentence_index ->
              new format: { part_id: { element_id: (png_path, x_px, y_px) } }
              legacy format: { element_id: (png_path, x_px, y_px) }
        """
        os.makedirs(output_dir, exist_ok=True)

        # Build input JSON for the worker
        input_data = {
            "timeline": timeline,
            "sentences": sentences_data,
            "resolution": resolution or timeline.get("resolution", {"width": 1920, "height": 1080}),
        }

        input_json = json.dumps(input_data, ensure_ascii=False)

        try:
            result = subprocess.run(
                [_NODE_BIN, str(_WORKER_SCRIPT), output_dir],
                input=input_json,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes max
                cwd=str(_PROJECT_ROOT),
            )
        except subprocess.TimeoutExpired:
            print("[KonvaRenderer] Node.js worker timed out after 5 minutes")
            return {}
        except FileNotFoundError:
            print(f"[KonvaRenderer] Node.js not found. Ensure 'node' is in PATH.")
            return {}

        if result.returncode != 0:
            stderr = result.stderr[-2000:] if result.stderr else "(no stderr)"
            print(f"[KonvaRenderer] Worker failed (exit={result.returncode}):\n{stderr}")
            return {}
        elif result.stderr and result.stderr.strip():
            # Keep non-fatal worker warnings (e.g. missing fonts) visible for debugging.
            print(f"[KonvaRenderer] Worker warnings:\n{result.stderr[-2000:]}")

        # Parse stdout for results JSON
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            # Try to find JSON in stdout (worker may have logged warnings to stderr)
            print(f"[KonvaRenderer] Failed to parse worker output")
            if result.stderr:
                print(f"[KonvaRenderer] stderr: {result.stderr[-1000:]}")
            return {}

        # Convert worker output to tuple format used by VideoProcessor.
        parsed = {}
        raw_results = output.get("results", {})
        for si_str, elements_or_parts in raw_results.items():
            si = int(si_str)
            parsed[si] = {}

            # Legacy format: { elem_id: {path,x,y,...} }
            if isinstance(elements_or_parts, dict) and all(
                isinstance(v, dict) and "path" in v for v in elements_or_parts.values()
            ):
                for elem_id, info in elements_or_parts.items():
                    parsed[si][elem_id] = (info["path"], info["x"], info["y"])
                continue

            # New format: { part_id: { elem_id: {path,x,y,...} } }
            if isinstance(elements_or_parts, dict):
                for part_id, part_elements in elements_or_parts.items():
                    parsed[si][part_id] = {}
                    if not isinstance(part_elements, dict):
                        continue
                    for elem_id, info in part_elements.items():
                        if not isinstance(info, dict) or "path" not in info:
                            continue
                        parsed[si][part_id][elem_id] = (info["path"], info["x"], info["y"])

        # Count PNGs across both formats
        n_total = 0
        for by_sentence in parsed.values():
            if by_sentence and all(isinstance(v, tuple) for v in by_sentence.values()):
                n_total += len(by_sentence)
            else:
                n_total += sum(len(v) for v in by_sentence.values() if isinstance(v, dict))
        print(f"[KonvaRenderer] Rendered {n_total} PNGs for {len(parsed)} sentences")
        return parsed

    def get_element_visibility(self, timeline: dict, part_idx: int) -> Dict[str, bool]:
        """
        Get element visibility map for a specific part index.

        Returns: { element_id: bool }
        """
        parts = timeline.get("parts", [])
        if part_idx >= len(parts):
            return {}
        return parts[part_idx].get("elementVisibility", {})
