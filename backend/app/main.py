"""
FastAPI entrypoint — Phase 1.

Exposes a single synchronous endpoint that runs the full
plan -> research -> write pipeline and returns the result as JSON.

Phase 3 will add a WebSocket endpoint that streams each stage as it
completes instead of waiting for the whole pipeline to finish.
"""

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.orchestrator import run_research
from app.models.schemas import ResearchResult

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Research Agent API", version="0.1.0")


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
        logging.exception("Research pipeline failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
