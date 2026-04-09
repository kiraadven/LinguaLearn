"""
GraphWSServer - FastAPI WebSocket endpoint for real-time graph state broadcasting.

Manages per-session WebSocket connections. Broadcasts graph diffs, node
activations, and turn results to all connected clients for a session.
"""

from __future__ import annotations
import json
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from . import ws_protocol

logger = logging.getLogger(__name__)


class GraphWSServer:

    def __init__(self):
        # session_id -> list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}
        # session_id -> last version sent to each connection
        self._last_sent_version: dict[str, int] = {}

    async def connect(self, ws: WebSocket, session_id: str,
                      graph_snapshot: dict, graph_version: int) -> None:
        """Accept a new WebSocket connection and send full graph state."""
        await ws.accept()
        if session_id not in self._connections:
            self._connections[session_id] = []
        self._connections[session_id].append(ws)
        self._last_sent_version[session_id] = graph_version

        msg = ws_protocol.build_full_state_msg(graph_snapshot, graph_version)
        await ws.send_json(msg)
        logger.info(f"WS connected: session={session_id}, version={graph_version}")

    async def disconnect(self, ws: WebSocket, session_id: str) -> None:
        """Remove a disconnected WebSocket."""
        if session_id in self._connections:
            self._connections[session_id] = [
                c for c in self._connections[session_id] if c != ws
            ]
            if not self._connections[session_id]:
                del self._connections[session_id]
        logger.info(f"WS disconnected: session={session_id}")

    async def broadcast_diff(self, session_id: str, mutations: list[dict],
                             graph_version: int) -> None:
        """Send graph_diff to all connected clients for this session."""
        if not mutations:
            return
        conns = self._connections.get(session_id, [])
        if not conns:
            return

        since = self._last_sent_version.get(session_id, 0)
        msg = ws_protocol.build_diff_msg(mutations, graph_version, since)
        self._last_sent_version[session_id] = graph_version

        await self._broadcast(conns, session_id, msg)

    async def broadcast_node_active(self, session_id: str,
                                    node_data: dict, graph_version: int) -> None:
        """Broadcast current active node details."""
        conns = self._connections.get(session_id, [])
        if not conns:
            return
        msg = ws_protocol.build_node_active_msg(node_data, graph_version)
        await self._broadcast(conns, session_id, msg)

    async def broadcast_turn_result(
        self,
        session_id: str,
        teacher_action: str,
        tool_action: Optional[str],
        delivery_style: str,
        assessment_summary: dict,
        audio_url: Optional[str] = None,
    ) -> None:
        """Broadcast turn result to all connected clients."""
        conns = self._connections.get(session_id, [])
        if not conns:
            return
        msg = ws_protocol.build_turn_result_msg(
            teacher_action, tool_action, delivery_style,
            assessment_summary, audio_url,
        )
        await self._broadcast(conns, session_id, msg)

    async def handle_client_message(self, ws: WebSocket, session_id: str,
                                    message: dict) -> Optional[dict]:
        """Handle incoming client messages.
        Returns a response dict if needed, or None."""
        msg_type = message.get("type", "")

        if msg_type == "request_full_state":
            # Caller should provide graph snapshot
            return {"action": "send_full_state"}

        elif msg_type == "student_input":
            return {
                "action": "process_student_input",
                "text": message.get("data", {}).get("text", ""),
                "audio_features": message.get("data", {}).get("audio_features", {}),
            }

        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _broadcast(self, conns: list[WebSocket], session_id: str,
                         msg: dict) -> None:
        disconnected = []
        for ws in conns:
            try:
                await ws.send_json(msg)
            except (WebSocketDisconnect, RuntimeError):
                disconnected.append(ws)

        for ws in disconnected:
            await self.disconnect(ws, session_id)
