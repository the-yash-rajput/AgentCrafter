"""
API views for the sessions app.

Service imports are lazy (inside each method) to avoid pulling in LangGraph
at URL-load time.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from runs.serializers import RunResponseSerializer
from .serializers import SessionResponseSerializer, SessionRunCreateSerializer


class SessionListCreateView(APIView):
    """
    GET  /api/agents/{agent_id}/versions/{version_id}/sessions
    POST /api/agents/{agent_id}/versions/{version_id}/sessions
    """

    def get(self, request, agent_id, version_id):
        from config.db import managed_db
        from services.session_service import SessionService
        with managed_db() as db:
            sessions = SessionService(db).list_sessions(agent_id, version_id)
        return Response(SessionResponseSerializer(sessions, many=True).data)

    def post(self, request, agent_id, version_id):
        from config.db import managed_db
        from services.session_service import SessionService
        with managed_db() as db:
            session = SessionService(db).create_session(agent_id, version_id)
        return Response(SessionResponseSerializer(session).data, status=status.HTTP_201_CREATED)


class SessionDetailView(APIView):
    """GET /api/agents/{agent_id}/versions/{version_id}/sessions/{session_id}"""

    def get(self, request, agent_id, version_id, session_id):
        from config.db import managed_db
        from services.session_service import SessionService
        with managed_db() as db:
            session = SessionService(db).get_session(session_id)
        return Response(SessionResponseSerializer(session).data)


class SessionRunView(APIView):
    """POST /api/agents/{agent_id}/versions/{version_id}/sessions/{session_id}/run"""

    def post(self, request, agent_id, version_id, session_id):
        from config.db import managed_db
        from schemas.schemas import SessionRunCreate
        from services.run_service import RunService
        ser = SessionRunCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = SessionRunCreate(**ser.validated_data)
        with managed_db() as db:
            run = RunService(db).run_in_session(agent_id, version_id, session_id, payload)
        return Response(RunResponseSerializer(run).data, status=status.HTTP_201_CREATED)
