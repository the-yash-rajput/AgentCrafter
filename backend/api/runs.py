import asyncio
from typing import List, AsyncGenerator
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from api.error_handling import translate_service_errors
from db.session import get_db
from schemas.schemas import RunResponse
from services.run_service import RunService

router = APIRouter(tags=["runs"])


@router.get("/agents/{agent_id}/validate")
@translate_service_errors
def validate_agent(agent_id: int, db: Session = Depends(get_db)):
    return RunService(db).validate_agent(agent_id)


@router.get("/runs/{run_id}", response_model=RunResponse)
@translate_service_errors
def get_run(run_id: int, db: Session = Depends(get_db)):
    return RunService(db).get_run(run_id)


@router.get("/agents/{agent_id}/runs", response_model=List[RunResponse])
@translate_service_errors
def list_runs(agent_id: int, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    return RunService(db).list_runs(agent_id, limit=limit, offset=offset)


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
