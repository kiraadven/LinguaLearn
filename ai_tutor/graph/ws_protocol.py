"""
WebSocket Protocol - Message schema for graph state broadcasting.

Server -> Client:
- graph_full_state:  Full graph snapshot (on connect / reconnect)
- graph_diff:        Incremental mutations (after each turn)
- node_active:       Current node details (on cursor move)
- turn_result:       Turn outcome (action, tool, style, audio_url)

Client -> Server:
- student_input:     ASR text + audio features
- request_full_state: Request full graph resync
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Server -> Client messages
# ---------------------------------------------------------------------------

@dataclass
class GraphFullStateMsg:
    """Sent on initial connection or explicit resync request."""
    type: str = "graph_full_state"
    version: int = 0
    data: dict = field(default_factory=dict)
    # data contains: graph_id, current_node_id, nodes[], edges[],
    #                lesson_objectives, progress{}


@dataclass
class GraphDiffMsg:
    """Incremental graph mutations since last broadcast."""
    type: str = "graph_diff"
    version: int = 0
    since_version: int = 0
    mutations: list[dict] = field(default_factory=list)
    # Each mutation: {"op": str, "data": dict}
    # ops: add_node, remove_node, update_node_status,
    #      add_edge, remove_edge, update_edge_weight,
    #      move_cursor, insert_subgraph, remove_subgraph


@dataclass
class NodeActiveMsg:
    """Sent when cursor moves to a new node."""
    type: str = "node_active"
    version: int = 0
    data: dict = field(default_factory=dict)
    # data contains: node_id, node_type, title, teacher_goal,
    #                expected_evidence, delivery_style, allowed_actions


@dataclass
class TurnResultMsg:
    """Sent after each turn is processed."""
    type: str = "turn_result"
    data: dict = field(default_factory=dict)
    # data contains: teacher_action, tool_action (nullable),
    #                delivery_style, assessment_summary,
    #                audio_url (nullable, for streamed audio)


# ---------------------------------------------------------------------------
# Client -> Server messages
# ---------------------------------------------------------------------------

@dataclass
class StudentInputMsg:
    """Student speech input (from ASR)."""
    type: str = "student_input"
    data: dict = field(default_factory=dict)
    # data contains: text (str), audio_features (dict)
    #   audio_features: duration_ms, latency_ms, self_correction_count, etc.


@dataclass
class RequestFullStateMsg:
    """Client requests full graph resync."""
    type: str = "request_full_state"


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------

def build_full_state_msg(graph_snapshot: dict, version: int) -> dict:
    return {
        "type": "graph_full_state",
        "version": version,
        "data": graph_snapshot,
    }


def build_diff_msg(mutations: list[dict], version: int,
                   since_version: int) -> dict:
    return {
        "type": "graph_diff",
        "version": version,
        "since_version": since_version,
        "mutations": mutations,
    }


def build_node_active_msg(node_data: dict, version: int) -> dict:
    return {
        "type": "node_active",
        "version": version,
        "data": node_data,
    }


def build_turn_result_msg(
    teacher_action: str,
    tool_action: Optional[str],
    delivery_style: str,
    assessment_summary: dict,
    audio_url: Optional[str] = None,
) -> dict:
    return {
        "type": "turn_result",
        "data": {
            "teacher_action": teacher_action,
            "tool_action": tool_action,
            "delivery_style": delivery_style,
            "assessment_summary": assessment_summary,
            "audio_url": audio_url,
        },
    }
