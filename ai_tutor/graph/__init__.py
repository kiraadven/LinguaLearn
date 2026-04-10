"""
Dynamic Lesson Graph

Core modules:
- schema:            NodeTemplate, LiveNode, EdgeSpec, SubgraphSpec
- graph_engine:      LessonGraph (NetworkX MultiDiGraph wrapper)
- node_templates:    NodeTemplateLibrary (offline YAML loading + indexing)
- subgraph_factory:  SubgraphFactory (repair/backtrack/enrichment/assessment)
- graph_mutator:     GraphMutator (memory signals -> graph mutations)
- edge_weights:      EdgeWeightComputer (mastery+engagement+fatigue -> weights)
- content_connector: ContentConnector (content pack + web search -> node content)
- graph_assembler:   GraphAssembler (offline lesson plan -> initial graph)
- ws_protocol:       WebSocket message schema
- ws_server:         FastAPI WebSocket endpoint
"""

from .schema import NodeTemplate, LiveNode, EdgeSpec, SubgraphSpec
from .graph_engine import LessonGraph
