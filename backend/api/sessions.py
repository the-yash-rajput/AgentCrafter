from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.error_handling import translate_service_errors
from db.session import get_db
from schemas.schemas import SessionResponse, SessionRunCreate, RunResponse
from services.session_service import SessionService
from services.run_service import RunService

router = APIRouter(tags=["sessions"])


@router.post("/agents/{agent_id}/versions/{version_id}/sessions", response_model=SessionResponse)
@translate_service_errors
def create_session(agent_id: int, version_id: int, db: Session = Depends(get_db)):
    return SessionService(db).create_session(agent_id, version_id)


@router.get("/agents/{agent_id}/versions/{version_id}/sessions", response_model=List[SessionResponse])
@translate_service_errors
def list_sessions(agent_id: int, version_id: int, db: Session = Depends(get_db)):
    return SessionService(db).list_sessions(agent_id, version_id)


@router.get("/agents/{agent_id}/versions/{version_id}/sessions/{session_id}", response_model=SessionResponse)
@translate_service_errors
def get_session(agent_id: int, version_id: int, session_id: int, db: Session = Depends(get_db)):
    return SessionService(db).get_session(session_id)


@router.post("/agents/{agent_id}/versions/{version_id}/sessions/{session_id}/run", response_model=RunResponse)
@translate_service_errors
def run_in_session(
    agent_id: int,
    version_id: int,
    session_id: int,
    payload: SessionRunCreate,
    db: Session = Depends(get_db),
):
    return RunService(db).run_in_session(agent_id, version_id, session_id, payload)
