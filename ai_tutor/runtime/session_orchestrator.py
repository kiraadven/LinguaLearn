"""
SessionOrchestrator - Main runtime loop for a live classroom session.

Lifecycle:
1. init_session()       Load lesson graph, init memory layers
2. on_student_input()   THE HOT PATH: assess -> mutate graph -> policy -> voice -> advance
3. auto_advance()       Timer-driven when student is silent
4. on_teacher_pause()   Graph needs student response, pause auto-advance
5. end_session()        Compress memory, cleanup

Key invariant: LLM is NEVER on the hot path.
Only called via supervisor escalation for exceptions.
"""

from __future__ import annotations
import logging
from typing import Optional

from ..graph.graph_engine import LessonGraph
from ..graph.graph_assembler import GraphAssembler
from ..graph.graph_mutator import GraphMutator
from ..graph.subgraph_factory import SubgraphFactory
from ..graph.edge_weights import EdgeWeightComputer
from ..graph.node_templates import NodeTemplateLibrary
from ..graph.content_connector import ContentConnector
from ..graph.ws_server import GraphWSServer
from .memory import MemoryManager
from .policy_runtime import PolicyRuntime
from .assessment import AssessmentEngine

logger = logging.getLogger(__name__)


class SessionOrchestrator:

    def __init__(
        self,
        template_library: NodeTemplateLibrary,
        content_connector: ContentConnector,
        memory_manager: MemoryManager,
        voice_dispatcher,  # VoiceDispatcher (from voice/ module)
        ws_server: GraphWSServer,
    ):
        self.templates = template_library
        self.content = content_connector
        self.memory = memory_manager
        self.voice = voice_dispatcher
        self.ws = ws_server

        self.assessment_engine = AssessmentEngine()
        self.policy = PolicyRuntime()

        # Per-session state
        self._graphs: dict[str, LessonGraph] = {}
        self._mutators: dict[str, GraphMutator] = {}

    # ------------------------------------------------------------------
    # 1. Session initialization
    # ------------------------------------------------------------------

    async def init_session(
        self,
        session_id: str,
        student_id: str,
        lesson_plan: list[dict],
        lesson_objectives: list[str],
        persona_id: str,
        persona_params: dict,
    ) -> dict:
        """Build initial graph and initialize all layers.

        Returns full graph snapshot for frontend.
        """
        # Build graph from offline lesson plan
        assembler = GraphAssembler(self.templates, self.content)
        graph = assembler.assemble(lesson_plan, lesson_objectives)
        self._graphs[session_id] = graph

        # Build mutator
        subgraph_factory = SubgraphFactory(self.templates)
        edge_weight_computer = EdgeWeightComputer()
        mutator = GraphMutator(graph, subgraph_factory, edge_weight_computer, self.content)
        self._mutators[session_id] = mutator

        # Init memory
        self.memory.init_session(session_id, student_id, persona_id, persona_params)

        # Update hot memory with initial state
        current = graph.get_current_node()
        self.memory.update_hot(
            session_id,
            current_node_id=current.node_id,
            allowed_actions=current.policy_profile.get("allowed_actions", []),
        )

        logger.info(f"Session {session_id} initialized: {graph.G.number_of_nodes()} nodes, "
                     f"start={graph.start_node_id}")

        return graph.to_snapshot()

    # ------------------------------------------------------------------
    # 2. THE HOT PATH: on_student_input
    # ------------------------------------------------------------------

    async def on_student_input(
        self,
        session_id: str,
        student_text: str,
        audio_features: Optional[dict] = None,
    ) -> dict:
        """Process a student utterance. Returns turn result dict.

        Steps:
        1. Assess student input
        2. Apply assessment to memory
        3. Get graph mutation signals from memory
        4. Apply mutations to graph
        5. Broadcast graph diff via WS
        6. Check supervisor escalation
        7. Select policy action
        8. Dispatch voice generation
        9. Resolve transition, advance graph
        10. Broadcast node_active + turn_result
        """
        graph = self._graphs[session_id]
        mutator = self._mutators[session_id]
        hot = self.memory.get_hot(session_id)

        # Step 1: Assessment
        current_node = graph.get_current_node()
        assessment = self.assessment_engine.evaluate(
            student_text=student_text,
            audio_features=audio_features or {},
            current_node=current_node,
            hot_memory=hot,
        )

        # Step 2: Apply to memory
        assessment["node_id"] = current_node.node_id
        assessment["turn_number"] = hot.turn_number + 1
        self.memory.apply_assessment(session_id, assessment)
        self.memory.update_hot(session_id, turn_number=hot.turn_number + 1)

        # Step 3: Get mutation signals
        signals = self.memory.get_graph_mutation_signals(session_id)

        # Step 4: Apply mutations
        version_before = graph.version
        mutations = mutator.apply_mutations(signals)

        # Step 5: Broadcast diff
        if mutations:
            await self.ws.broadcast_diff(session_id, mutations, graph.version)

        # Step 6: Check supervisor escalation
        fallback_text = None
        if self._should_escalate(current_node, assessment, signals):
            fallback_text = await self._escalate_to_supervisor(
                session_id, student_text, assessment, current_node,
            )

        # Step 7: Policy action
        policy_action, tool_action, delivery_style = self.policy.select_action(
            current_node, hot, assessment,
        )

        # Step 8: Voice dispatch
        voice_context = self.memory.get_voice_context(session_id)
        audio_url = None
        if self.voice:
            audio_url = await self.voice.dispatch(
                graph_state={
                    "node_type": current_node.node_type,
                    "phase": current_node.phase,
                    "visit_count": current_node.visit_count,
                    "is_repair_mode": hot.is_repair_mode,
                },
                policy_action=policy_action,
                delivery_style=delivery_style,
                assessment=assessment,
                memory_context=voice_context,
                fallback_text=fallback_text,
            )

        # Step 9: Resolve transition
        event = self.policy.determine_event(current_node, assessment, hot)
        next_node_id = graph.resolve_transition(current_node.node_id, event)

        if next_node_id and next_node_id != current_node.node_id:
            new_node = graph.advance_to(next_node_id)
            self.memory.record_node_visit(session_id, next_node_id)
            self.memory.update_hot(
                session_id,
                current_node_id=next_node_id,
                allowed_actions=new_node.policy_profile.get("allowed_actions", []),
                last_event=event,
                is_repair_mode=new_node.subgraph_origin is not None,
            )

            # Step 10: Broadcast
            await self.ws.broadcast_node_active(session_id, {
                "node_id": new_node.node_id,
                "node_type": new_node.node_type,
                "title": new_node.title,
                "teacher_goal": new_node.teacher_goal,
                "delivery_style": delivery_style,
            }, graph.version)
        else:
            # Update node failure/success counts
            if assessment.get("is_correct"):
                current_node.success_count += 1
            else:
                current_node.failure_count += 1

        # Broadcast turn result
        await self.ws.broadcast_turn_result(
            session_id, policy_action, tool_action, delivery_style,
            assessment, audio_url,
        )

        # Add to recent turns
        hot.recent_turns.append({
            "role": "student", "text": student_text,
        })
        hot.recent_turns.append({
            "role": "teacher", "action": policy_action,
            "style": delivery_style, "tool": tool_action,
        })
        if len(hot.recent_turns) > 10:
            hot.recent_turns = hot.recent_turns[-10:]

        return {
            "policy_action": policy_action,
            "tool_action": tool_action,
            "delivery_style": delivery_style,
            "assessment": assessment,
            "audio_url": audio_url,
            "next_node_id": next_node_id,
        }

    # ------------------------------------------------------------------
    # 3. Auto-advance (no student response)
    # ------------------------------------------------------------------

    async def auto_advance(self, session_id: str) -> Optional[dict]:
        """Called when timer expires with no student response.

        Non-interactive nodes (explain, transition, hook): auto-advance.
        Interactive nodes (practice, check): generate prompt/encouragement.
        """
        graph = self._graphs[session_id]
        current = graph.get_current_node()

        non_interactive = {"hook", "explain", "transition", "wrap_up", "worked_example"}

        if current.node_type in non_interactive:
            # Auto-advance to next node
            next_id = graph.resolve_transition(current.node_id, "auto_advance")
            if next_id:
                new_node = graph.advance_to(next_id)
                self.memory.record_node_visit(session_id, next_id)

                # Generate teacher speech for new node
                if self.voice:
                    voice_context = self.memory.get_voice_context(session_id)
                    await self.voice.dispatch(
                        graph_state={"node_type": new_node.node_type},
                        policy_action="advance",
                        delivery_style=new_node.policy_profile.get("default_style", "neutral_teach"),
                        assessment={},
                        memory_context=voice_context,
                    )

                await self.ws.broadcast_node_active(session_id, {
                    "node_id": new_node.node_id,
                    "node_type": new_node.node_type,
                    "title": new_node.title,
                    "teacher_goal": new_node.teacher_goal,
                }, graph.version)

                return {"advanced_to": next_id}
        else:
            # Interactive node: generate encouragement, wait more
            if self.voice:
                voice_context = self.memory.get_voice_context(session_id)
                await self.voice.dispatch(
                    graph_state={"node_type": current.node_type},
                    policy_action="encourage",
                    delivery_style="warm_encourage",
                    assessment={"is_silence": True},
                    memory_context=voice_context,
                )
            return {"waiting_for_student": True, "node_id": current.node_id}

        return None

    # ------------------------------------------------------------------
    # 4. End session
    # ------------------------------------------------------------------

    async def end_session(self, session_id: str) -> dict:
        graph = self._graphs.get(session_id)
        snapshot = graph.to_snapshot() if graph else {}

        self.memory.end_session(session_id)
        self._graphs.pop(session_id, None)
        self._mutators.pop(session_id, None)

        return snapshot

    # ------------------------------------------------------------------
    # Supervisor escalation
    # ------------------------------------------------------------------

    def _should_escalate(self, node: LiveNode, assessment: dict,
                         signals: dict) -> bool:
        """Check if LLM supervisor should be invoked."""
        if not node.llm_supervisor_allowed:
            return False

        # Repeated failure over budget
        budget = node.policy_profile.get("failure_budget", 2)
        if node.failure_count > budget + 1:
            return True

        # Off-topic
        if assessment.get("is_off_topic"):
            return True

        # Safety concern
        if assessment.get("safety_flag"):
            return True

        # High fatigue + low engagement
        if signals.get("fatigue", 0) > 0.8 and signals.get("engagement", 1.0) < 0.2:
            return True

        return False

    async def _escalate_to_supervisor(
        self, session_id: str, student_text: str,
        assessment: dict, current_node: LiveNode,
    ) -> Optional[str]:
        """Invoke LLM supervisor for exception handling.
        Returns fallback text for TTS, or None."""
        logger.warning(f"Supervisor escalation: session={session_id}, "
                       f"node={current_node.node_id}, "
                       f"reason={assessment}")
        # TODO: actual LLM call
        # For now return a generic response
        return None
