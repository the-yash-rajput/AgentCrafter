"""
API views for the sessions app.

Service imports are lazy (inside each method) to avoid pulling in LangGraph
at URL-load time.
"""
import threading

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
            run = RunService(db).start_run(agent_id, version_id, session_id, payload)

        # Capture everything the background thread needs before the DB session closes
        run_id = run.id
        checkpoint_thread_id = run.checkpoint_thread_id
        effective_input = run._runtime_effective_input
        conversation_history = run._runtime_conversation_history

        def _execute():
            from config.db import managed_db as bg_managed_db
            from services.run_service import RunService as BgRunService
            with bg_managed_db() as bg_db:
                BgRunService(bg_db).execute_run_background(
                    run_id=run_id,
                    agent_id=agent_id,
                    version_id=version_id,
                    session_id=session_id,
                    effective_input=effective_input,
                    conversation_history=conversation_history,
                    checkpoint_thread_id=checkpoint_thread_id,
                )

        threading.Thread(target=_execute, daemon=True).start()

        return Response(RunResponseSerializer(run).data, status=status.HTTP_201_CREATED)
