"""
API views for the agents app.

Replaces the FastAPI routers in api/agents.py, api/nodes.py, api/edges.py,
and api/versions.py. Each view class is an APIView subclass that:

  1. Validates the request via a DRF serializer.
  2. Builds a Pydantic payload (same schemas the service layer already expects).
  3. Calls the service with a SQLAlchemy session via managed_db().
  4. Serializes the SQLAlchemy result and returns a DRF Response.

The service layer (AgentService, NodeService, etc.) is completely unchanged.

Service imports are deliberately lazy (inside each method) to avoid pulling in
the full LangGraph/LangChain dependency chain at URL-load time, which would
break `manage.py check` and slow startup significantly.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AgentCreateSerializer,
    AgentExportPayloadSerializer,
    AgentListResponseSerializer,
    AgentResponseSerializer,
    AgentUpdateSerializer,
    AgentVersionResponseSerializer,
    AgentVersionWithGraphSerializer,
    AgentWithGraphSerializer,
    EdgeCreateSerializer,
    EdgeResponseSerializer,
    EdgeUpdateSerializer,
    NodeCreateSerializer,
    NodeDefinitionResponseSerializer,
    NodeResponseSerializer,
    NodeUpdateSerializer,
    VersionPatchSerializer,
)


# ── Agent views ───────────────────────────────────────────────────────────────

class AgentListCreateView(APIView):
    """GET /api/agents  POST /api/agents"""

    def get(self, request):
        from config.db import managed_db
        from services.agent_service import AgentService
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))
        with managed_db() as db:
            agents = AgentService(db).list_agents(limit=limit, offset=offset)
        return Response(AgentListResponseSerializer(agents, many=True).data)

    def post(self, request):
        from config.db import managed_db
        from schemas.schemas import AgentCreate
        from services.agent_service import AgentService
        ser = AgentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        payload = AgentCreate(
            name=d["name"],
            description=d.get("description"),
        )
        with managed_db() as db:
            agent = AgentService(db).create_agent(payload)
        return Response(AgentResponseSerializer(agent).data, status=status.HTTP_201_CREATED)


class AgentImportView(APIView):
    """POST /api/agents/import — must be declared before AgentDetailView."""

    def post(self, request):
        from config.db import managed_db
        from services.agent_io import AgentConfigSerializer as AgentIO
        with managed_db() as db:
            agent = AgentIO.deserialize(request.data, db)
        return Response(AgentResponseSerializer(agent).data, status=status.HTTP_201_CREATED)


class AgentDetailView(APIView):
    """GET /api/agents/{id}  PUT /api/agents/{id}  DELETE /api/agents/{id}"""

    def get(self, request, agent_id):
        from config.db import managed_db
        from services.agent_service import AgentService
        with managed_db() as db:
            agent = AgentService(db).get_agent(agent_id, include_graph=True)
        return Response(AgentWithGraphSerializer(agent).data)

    def put(self, request, agent_id):
        from config.db import managed_db
        from schemas.schemas import AgentUpdate
        from services.agent_service import AgentService
        ser = AgentUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        payload = AgentUpdate(**{k: v for k, v in d.items() if k in request.data})
        with managed_db() as db:
            agent = AgentService(db).update_agent(agent_id, payload)
        return Response(AgentResponseSerializer(agent).data)

    def delete(self, request, agent_id):
        from config.db import managed_db
        from services.agent_service import AgentService
        with managed_db() as db:
            AgentService(db).delete_agent(agent_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentDuplicateView(APIView):
    """POST /api/agents/{id}/duplicate"""

    def post(self, request, agent_id):
        from config.db import managed_db
        from services.agent_service import AgentService
        with managed_db() as db:
            agent = AgentService(db).duplicate_agent(agent_id)
        return Response(AgentResponseSerializer(agent).data, status=status.HTTP_201_CREATED)


# ── Version views ─────────────────────────────────────────────────────────────

class VersionListView(APIView):
    """GET /api/agents/{agent_id}/versions"""

    def get(self, request, agent_id):
        from config.db import managed_db
        from services.agent_version_service import AgentVersionService
        with managed_db() as db:
            versions = AgentVersionService(db).list_versions(agent_id)
        return Response(AgentVersionResponseSerializer(versions, many=True).data)


class VersionDetailView(APIView):
    """GET/PATCH /api/agents/{agent_id}/versions/{version_id}"""

    def get(self, request, agent_id, version_id):
        from config.db import managed_db
        from services.agent_version_service import AgentVersionService
        with managed_db() as db:
            version = AgentVersionService(db).get_version(version_id, include_graph=True)
        return Response(AgentVersionWithGraphSerializer(version).data)

    def patch(self, request, agent_id, version_id):
        from config.db import managed_db
        from services.agent_version_service import AgentVersionService
        ser = VersionPatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = {k: v for k, v in ser.validated_data.items() if k in request.data}
        if not d:
            return Response({"detail": "At least one of state_schema, entry_node, or exit_nodes is required"}, status=status.HTTP_400_BAD_REQUEST)
        with managed_db() as db:
            version = AgentVersionService(db).patch_version(version_id, **d)
        return Response(AgentVersionWithGraphSerializer(version).data)


class VersionForkView(APIView):
    """POST /api/agents/{agent_id}/versions/{version_id}/fork"""

    def post(self, request, agent_id, version_id):
        from config.db import managed_db
        from services.agent_version_service import AgentVersionService
        with managed_db() as db:
            version = AgentVersionService(db).fork_version(version_id)
        return Response(AgentVersionResponseSerializer(version).data, status=status.HTTP_201_CREATED)


class VersionExportView(APIView):
    """GET /api/agents/{agent_id}/versions/{version_id}/export"""

    def get(self, request, agent_id, version_id):
        from config.db import managed_db
        from services.agent_io import AgentConfigSerializer as AgentIO
        from services.agent_service import AgentService
        from services.agent_version_service import AgentVersionService
        with managed_db() as db:
            agent = AgentService(db).get_agent(agent_id)
            version = AgentVersionService(db).get_version(version_id, include_graph=True)
            payload = AgentIO.serialize(agent, version)
        return Response(AgentExportPayloadSerializer(payload).data)


# ── Node views ────────────────────────────────────────────────────────────────

class NodeDefinitionsView(APIView):
    """GET /api/node-definitions — returns all available node type definitions."""

    def get(self, request):
        from services.node_service import NodeService
        definitions = NodeService.list_node_definitions()
        return Response(NodeDefinitionResponseSerializer(definitions, many=True).data)


class NodeListCreateView(APIView):
    """POST /api/agents/{agent_id}/nodes"""

    def post(self, request, agent_id):
        from config.db import managed_db
        from schemas.schemas import NodeCreate
        from services.node_service import NodeService
        ser = NodeCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = NodeCreate(**ser.validated_data)
        with managed_db() as db:
            node = NodeService(db).create_node(agent_id, payload)
        return Response(NodeResponseSerializer(node).data, status=status.HTTP_201_CREATED)


class VersionNodeCreateView(APIView):
    """POST /api/agents/{agent_id}/versions/{version_id}/nodes"""

    def post(self, request, agent_id, version_id):
        from config.db import managed_db
        from schemas.schemas import NodeCreate
        from services.node_service import NodeService
        ser = NodeCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = NodeCreate(**ser.validated_data)
        with managed_db() as db:
            node = NodeService(db).create_node(agent_id, payload, version_id=version_id)
        return Response(NodeResponseSerializer(node).data, status=status.HTTP_201_CREATED)


class NodeDetailView(APIView):
    """PUT /api/nodes/{node_id}  DELETE /api/nodes/{node_id}"""

    def put(self, request, node_id):
        from config.db import managed_db
        from schemas.schemas import NodeUpdate
        from services.node_service import NodeService
        ser = NodeUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = NodeUpdate(**{k: v for k, v in ser.validated_data.items() if v is not None})
        with managed_db() as db:
            node = NodeService(db).update_node(node_id, payload)
        return Response(NodeResponseSerializer(node).data)

    def delete(self, request, node_id):
        from config.db import managed_db
        from services.node_service import NodeService
        with managed_db() as db:
            NodeService(db).delete_node(node_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Edge views ────────────────────────────────────────────────────────────────

class EdgeListCreateView(APIView):
    """POST /api/agents/{agent_id}/edges"""

    def post(self, request, agent_id):
        from config.db import managed_db
        from schemas.schemas import EdgeCreate
        from services.edge_service import EdgeService
        ser = EdgeCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = EdgeCreate(**ser.validated_data)
        with managed_db() as db:
            edge = EdgeService(db).create_edge(agent_id, payload)
        return Response(EdgeResponseSerializer(edge).data, status=status.HTTP_201_CREATED)


class VersionEdgeCreateView(APIView):
    """POST /api/agents/{agent_id}/versions/{version_id}/edges"""

    def post(self, request, agent_id, version_id):
        from config.db import managed_db
        from schemas.schemas import EdgeCreate
        from services.edge_service import EdgeService
        ser = EdgeCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = EdgeCreate(**ser.validated_data)
        with managed_db() as db:
            edge = EdgeService(db).create_edge(agent_id, payload, version_id=version_id)
        return Response(EdgeResponseSerializer(edge).data, status=status.HTTP_201_CREATED)


class EdgeDetailView(APIView):
    """PUT /api/edges/{edge_id}  DELETE /api/edges/{edge_id}"""

    def put(self, request, edge_id):
        from config.db import managed_db
        from schemas.schemas import EdgeUpdate
        from services.edge_service import EdgeService
        ser = EdgeUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = EdgeUpdate(**{k: v for k, v in ser.validated_data.items() if v is not None})
        with managed_db() as db:
            edge = EdgeService(db).update_edge(edge_id, payload)
        return Response(EdgeResponseSerializer(edge).data)

    def delete(self, request, edge_id):
        from config.db import managed_db
        from services.edge_service import EdgeService
        with managed_db() as db:
            EdgeService(db).delete_edge(edge_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Langfuse views ────────────────────────────────────────────────────────────

class LangfusePromptsView(APIView):
    """GET /api/langfuse/prompts"""

    def get(self, request):
        from base.utilities.langfuse_client_utility import LangfuseClientWrapper
        from base.utilities.langfuse_prompt_catalog_utility import list_langfuse_prompt_names
        prompts, source, error = list_langfuse_prompt_names()
        return Response({
            "enabled": LangfuseClientWrapper.get_langfuse_client() is not None,
            "prompts": prompts,
            "source": source,
            "error": error,
        })
