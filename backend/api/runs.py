import asyncio
from typing import List, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from api.error_handling import translate_service_errors
from db.session import get_db
from models import Run, Agent
from schemas.schemas import RunCreate, RunResponse
from services.runtime.graph_runner import GraphRunner

router = APIRouter(tags=["runs"])


@router.post("/agents/{agent_id}/run", response_model=RunResponse)
@translate_service_errors
def run_agent(agent_id: int, payload: RunCreate, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    runner = GraphRunner(db)
    
    # Validate first
    validation = runner.validate_graph(agent_id)
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail={"errors": validation["errors"]})

    try:
        result = runner.compile_and_run(agent_id, payload.input_data)
        run = db.query(Run).filter(Run.id == result["run_id"]).first()
        return run
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}/validate")
@translate_service_errors
def validate_agent(agent_id: int, db: Session = Depends(get_db)):
    runner = GraphRunner(db)
    return runner.validate_graph(agent_id)


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/agents/{agent_id}/runs", response_model=List[RunResponse])
def list_runs(agent_id: int, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    return (
        db.query(Run)
        .filter(Run.agent_id == agent_id)
        .order_by(Run.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: int, db: Session = Depends(get_db)):
    """SSE endpoint to stream run state snapshots."""
    async def event_generator() -> AsyncGenerator[str, None]:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            yield f"data: {json.dumps({'error': 'Run not found'})}\n\n"
            return

        snapshots = run.state_snapshots or []
        for snapshot in snapshots:
            yield f"data: {json.dumps(snapshot)}\n\n"
            await asyncio.sleep(0.1)

        yield f"data: {json.dumps({'status': run.status.value, 'output': run.output_data})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
