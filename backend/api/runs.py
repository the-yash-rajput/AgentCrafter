import asyncio
from typing import List, AsyncGenerator
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from api.error_handling import translate_service_errors
from db.session import get_db
from schemas.schemas import AgentSessionCreate, AgentSessionResponse, RunCreate, RunResponse
from services.run_service import RunService

router = APIRouter(tags=["runs"])


@router.post("/agents/{agent_id}/run", response_model=RunResponse)
@translate_service_errors
def run_agent(agent_id: int, payload: RunCreate, db: Session = Depends(get_db)):
    return RunService(db).run_agent(agent_id, payload)


@router.get("/agents/{agent_id}/validate")
@translate_service_errors
def validate_agent(agent_id: int, version_id: int | None = None, db: Session = Depends(get_db)):
    return RunService(db).validate_agent(agent_id, agent_version_id=version_id)


@router.post(
    "/agents/{agent_id}/versions/{version_id}/sessions",
    response_model=AgentSessionResponse,
)
@translate_service_errors
def create_agent_session(
    agent_id: int,
    version_id: int,
    payload: AgentSessionCreate | None = None,
    db: Session = Depends(get_db),
):
    return RunService(db).create_session(agent_id, version_id, payload or AgentSessionCreate())


@router.get(
    "/agents/{agent_id}/versions/{version_id}/sessions/{session_id}",
    response_model=AgentSessionResponse,
)
@translate_service_errors
def get_agent_session(agent_id: int, version_id: int, session_id: int, db: Session = Depends(get_db)):
    return RunService(db).get_session(agent_id, version_id, session_id)


@router.post(
    "/agents/{agent_id}/versions/{version_id}/sessions/{session_id}/runs",
    response_model=RunResponse,
)
@translate_service_errors
def run_agent_session(
    agent_id: int,
    version_id: int,
    session_id: int,
    payload: RunCreate,
    db: Session = Depends(get_db),
):
    return RunService(db).run_agent_version(agent_id, version_id, session_id, payload)


@router.get("/runs/{run_id}", response_model=RunResponse)
@translate_service_errors
def get_run(run_id: int, db: Session = Depends(get_db)):
    return RunService(db).get_run(run_id)


@router.get("/agents/{agent_id}/runs", response_model=List[RunResponse])
@translate_service_errors
def list_runs(
    agent_id: int,
    version_id: int | None = None,
    session_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return RunService(db).list_runs(
        agent_id,
        agent_version_id=version_id,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}/stream")
@translate_service_errors
async def stream_run(run_id: int, db: Session = Depends(get_db)):
    """SSE endpoint to stream run state snapshots."""
    run = RunService(db).get_run(run_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        snapshots = run.state_snapshots or []
        for snapshot in snapshots:
            yield f"data: {json.dumps(snapshot)}\n\n"
            await asyncio.sleep(0.1)

        yield f"data: {json.dumps({'status': run.status.value, 'output': run.output_data})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
