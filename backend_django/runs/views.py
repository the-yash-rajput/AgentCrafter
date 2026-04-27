"""
API views for the runs app.

Service imports are lazy (inside each method) to avoid pulling in LangGraph
at URL-load time.
"""
import json
import threading

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
    """POST /api/runs/{run_id}/resume — resume an interrupted run from its last checkpoint.

    For confidence-check HITL interruptions, the request body may include:
      { "human_response": "..." }
    If omitted, the original LLM response (stored in interrupt_metadata) is used.
    """

    def post(self, request, run_id):
        from config.db import managed_db
        from services.run_service import RunService

        human_response = (request.data or {}).get("human_response") or None
        human_notes = (request.data or {}).get("human_notes") or None

        with managed_db() as db:
            new_run = RunService(db).resume_run(run_id, human_response=human_response, human_notes=human_notes)

        new_run_id = new_run.id
        agent_id = new_run.agent_id
        version_id = new_run.version_id
        session_id = new_run.session_id
        checkpoint_thread_id = new_run.checkpoint_thread_id
        effective_input = new_run._runtime_effective_input
        resumed_from_run_id = new_run._runtime_resumed_from_run_id
        resume_command = getattr(new_run, "_runtime_resume_command", None)

        def _execute():
            from config.db import managed_db as bg_managed_db
            from services.run_service import RunService as BgRunService
            with bg_managed_db() as bg_db:
                BgRunService(bg_db).execute_run_background(
                    run_id=new_run_id,
                    agent_id=agent_id,
                    version_id=version_id,
                    session_id=session_id,
                    effective_input=effective_input,
                    conversation_history=[],
                    checkpoint_thread_id=checkpoint_thread_id,
                    resumed_from_run_id=resumed_from_run_id,
                    resume_command=resume_command,
                )

        threading.Thread(target=_execute, daemon=True).start()

        return Response(RunResponseSerializer(new_run).data, status=status.HTTP_201_CREATED)


class RunPauseView(APIView):
    """POST /api/runs/{run_id}/pause — signal a running run to stop between nodes."""

    def post(self, request, run_id):
        from config.db import managed_db
        from services.run_service import RunService
        with managed_db() as db:
            run = RunService(db).pause_run(run_id)
        return Response(RunResponseSerializer(run).data)


class RunExpireView(APIView):
    """POST /api/runs/{run_id}/expire — enforce SLA timeout on an interrupted run.

    Called by the frontend countdown timer when the SLA deadline is reached, or
    externally to trigger auto-resolution without waiting for the cron job.
    The timeout_action stored in interrupt_metadata determines whether the run is
    auto-approved (graph resumes with the original LLM response) or auto-failed.
    """

    def post(self, request, run_id):
        from config.db import managed_db
        from services.run_service import RunService

        with managed_db() as db:
            service = RunService(db)
            run = service.get_run(run_id)
            new_run = service._auto_resolve_timeout(run)

        if new_run is None:
            # auto_fail path: run is now failed, return its updated state
            with managed_db() as db:
                updated_run = RunService(db).get_run(run_id)
            return Response(RunResponseSerializer(updated_run).data)

        # auto_approve path: spawn background execution for the new run
        new_run_id = new_run.id
        agent_id = new_run.agent_id
        version_id = new_run.version_id
        session_id = new_run.session_id
        checkpoint_thread_id = new_run.checkpoint_thread_id
        effective_input = new_run._runtime_effective_input
        resumed_from_run_id = new_run._runtime_resumed_from_run_id
        resume_command = getattr(new_run, "_runtime_resume_command", None)

        def _execute():
            from config.db import managed_db as bg_managed_db
            from services.run_service import RunService as BgRunService
            with bg_managed_db() as bg_db:
                BgRunService(bg_db).execute_run_background(
                    run_id=new_run_id,
                    agent_id=agent_id,
                    version_id=version_id,
                    session_id=session_id,
                    effective_input=effective_input,
                    conversation_history=[],
                    checkpoint_thread_id=checkpoint_thread_id,
                    resumed_from_run_id=resumed_from_run_id,
                    resume_command=resume_command,
                )

        threading.Thread(target=_execute, daemon=True).start()
        return Response(RunResponseSerializer(new_run).data, status=status.HTTP_201_CREATED)


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
        final_output = (snapshots[-1].get("state_after") or {}) if snapshots else {}

        def event_stream():
            for snapshot in snapshots:
                yield f"data: {json.dumps(snapshot)}\n\n"
            yield f"data: {json.dumps({'status': run_status, 'output': final_output})}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
