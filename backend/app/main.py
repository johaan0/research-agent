"""
FastAPI entrypoint - Phase 3.

Two ways to run research:
- POST /research    : synchronous, waits for the full pipeline, returns final JSON (unchanged from Phase 1/2)
- WS   /ws/research  : streams each stage as it completes, persists every stage to Postgres
"""

import asyncio
import logging
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app import db
from app.orchestrator import run_research, run_research_stream
from app.models.schemas import ResearchResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Research Agent API", version="0.3.0")


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()
    logger.info("Database tables ready")


class ResearchRequest(BaseModel):
    question: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/research", response_model=ResearchResult)
def research(request: ResearchRequest) -> ResearchResult:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")
    try:
        return run_research(request.question)
    except Exception as e:
        logger.exception("Research pipeline failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/sessions")
def list_sessions(limit: int = 20) -> list[dict]:
    sessions = db.list_recent_sessions(limit=limit)
    return [
        {
            "id": s.id,
            "question": s.question,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]


@app.websocket("/ws/research")
async def research_ws(websocket: WebSocket) -> None:
    """
    Client sends: {"question": "..."}
    Server streams a sequence of JSON messages:
      {"stage": "session_started", "data": {"session_id": "..."}}
      {"stage": "plan", "data": {...}}
      {"stage": "evidence", "data": [...]}
      {"stage": "revision_cycle", "data": {"cycle": 1, "draft": {...}, "critique": {...}}}
      {"stage": "done", "data": {"session_id": "...", "final_answer": "...", "cited_urls": [...]}}
    or, on failure: {"stage": "error", "data": {"message": "..."}}
    """
    await websocket.accept()
    session_id: str | None = None

    try:
        payload = await websocket.receive_json()
        question = (payload.get("question") or "").strip()
        if not question:
            await websocket.send_json({"stage": "error", "data": {"message": "question must not be empty"}})
            await websocket.close()
            return

        session_id = await asyncio.to_thread(db.create_session, question)
        await websocket.send_json({"stage": "session_started", "data": {"session_id": session_id}})

        cycle_number = 0
        gen = run_research_stream(question)

        while True:
            try:
                stage, data = await asyncio.to_thread(next, gen)
            except StopIteration:
                break

            if stage == "plan":
                plan_dict = data.model_dump()
                await asyncio.to_thread(db.save_plan, session_id, plan_dict)
                await websocket.send_json({"stage": "plan", "data": plan_dict})

            elif stage == "evidence":
                evidence_dicts = [e.model_dump() for e in data]
                await asyncio.to_thread(db.save_evidence, session_id, evidence_dicts)
                await websocket.send_json({"stage": "evidence", "data": evidence_dicts})

            elif stage == "revision_cycle":
                cycle_number += 1
                draft_dict = data.draft.model_dump()
                critique_dict = data.critique.model_dump()
                await asyncio.to_thread(
                    db.save_revision_cycle, session_id, cycle_number, draft_dict, critique_dict
                )
                await websocket.send_json({
                    "stage": "revision_cycle",
                    "data": {"cycle": cycle_number, "draft": draft_dict, "critique": critique_dict},
                })

            elif stage == "done":
                result: ResearchResult = data
                await asyncio.to_thread(db.mark_completed, session_id, result.draft.model_dump())
                await websocket.send_json({
                    "stage": "done",
                    "data": {
                        "session_id": session_id,
                        "final_answer": result.draft.answer,
                        "cited_urls": result.draft.cited_urls,
                    },
                })

        await websocket.close()

    except WebSocketDisconnect:
        logger.info("Client disconnected mid-stream (session_id=%s)", session_id)

    except Exception as e:
        logger.exception("WebSocket research stream failed")
        if session_id:
            await asyncio.to_thread(db.mark_failed, session_id, str(e))
        try:
            await websocket.send_json({"stage": "error", "data": {"message": str(e)}})
        except Exception:
            pass
        await websocket.close()