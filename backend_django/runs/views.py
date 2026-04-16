"""
API views for the runs app.

Service imports are lazy (inside each method) to avoid pulling in LangGraph
at URL-load time.
"""
import json

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RunResponseSerializer


class AgentValidateView(APIView):
    """GET /api/agents/{agent_id}/validate — pre-execution validation."""

    def get(self, request, agent_id):
        from config.db import managed_db
        from services.run_service import RunService
        with managed_db() as db:
            result = RunService(db).validate_agent(agent_id)
        return Response(result)


class RunListView(APIView):
    """GET /api/agents/{agent_id}/runs"""

    def get(self, request, agent_id):
        from config.db import managed_db
        from services.run_service import RunService
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))
        with managed_db() as db:
            runs = RunService(db).list_runs(agent_id, limit=limit, offset=offset)
        return Response(RunResponseSerializer(runs, many=True).data)


class RunDetailView(APIView):
    """GET /api/runs/{run_id}"""

    def get(self, request, run_id):
        from config.db import managed_db
        from services.run_service import RunService
        with managed_db() as db:
            run = RunService(db).get_run(run_id)
        return Response(RunResponseSerializer(run).data)


class RunResumeView(APIView):
    """POST /api/runs/{run_id}/resume — resume an interrupted run from its last checkpoint."""

    def post(self, request, run_id):
        from config.db import managed_db
        from services.run_service import RunService
        with managed_db() as db:
            run = RunService(db).resume_run(run_id)
        return Response(RunResponseSerializer(run).data, status=status.HTTP_201_CREATED)


class RunStreamView(APIView):
    """
    GET /api/runs/{run_id}/stream — Server-Sent Events endpoint.

    Replays state_snapshots stored on the Run and emits a final summary frame.
    Uses Django's StreamingHttpResponse — no additional packages needed.
    """
    renderer_classes = []
    authentication_classes = []
    permission_classes = []

    def get(self, request, run_id):
        from config.db import managed_db
        from services.run_service import RunService
        with managed_db() as db:
            run = RunService(db).get_run(run_id)

        snapshots = list(run.state_snapshots or [])
        run_status = run.status.value if hasattr(run.status, "value") else run.status
        output_data = run.output_data or {}

        def event_stream():
            for snapshot in snapshots:
                yield f"data: {json.dumps(snapshot)}\n\n"
            yield f"data: {json.dumps({'status': run_status, 'output': output_data})}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
