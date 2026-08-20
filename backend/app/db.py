"""
Persistence layer — Supabase Postgres via SQLAlchemy.

Every research run creates one `sessions` row at the start, updated as
stages complete, plus one `revision_cycles` row per draft+critique pair.
Schema mirrors the Pydantic models in schemas.py directly — a session
holds the plan/evidence/final answer, revision_cycles holds the
draft/critique history.
"""

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, Integer, Boolean,
    ForeignKey, JSON,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from app.config import settings

Base = declarative_base()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class ResearchSession(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    question = Column(Text, nullable=False)
    status = Column(String, default="running")  # running | completed | failed
    plan = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    final_answer = Column(Text, nullable=True)
    final_cited_urls = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    revisions = relationship(
        "RevisionCycleRow", back_populates="session",
        order_by="RevisionCycleRow.cycle_number",
    )


class RevisionCycleRow(Base):
    __tablename__ = "revision_cycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    cycle_number = Column(Integer, nullable=False)
    draft_answer = Column(Text, nullable=False)
    cited_urls = Column(JSON, nullable=True)
    unsupported_claims = Column(JSON, nullable=True)
    uncited_claims = Column(JSON, nullable=True)
    needs_revision = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session = relationship("ResearchSession", back_populates="revisions")


def init_db() -> None:
    """Create tables if they don't exist yet. Called once at app startup."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# --- helpers used by the orchestrator / websocket layer ---

def create_session(question: str) -> str:
    session_id = str(uuid.uuid4())
    with get_db() as db:
        db.add(ResearchSession(id=session_id, question=question))
    return session_id


def save_plan(session_id: str, plan_dict: dict) -> None:
    with get_db() as db:
        db.query(ResearchSession).filter_by(id=session_id).update({"plan": plan_dict})


def save_evidence(session_id: str, evidence_list: list[dict]) -> None:
    with get_db() as db:
        db.query(ResearchSession).filter_by(id=session_id).update({"evidence": evidence_list})


def save_revision_cycle(
    session_id: str, cycle_number: int, draft_dict: dict, critique_dict: dict
) -> None:
    with get_db() as db:
        db.add(RevisionCycleRow(
            session_id=session_id,
            cycle_number=cycle_number,
            draft_answer=draft_dict["answer"],
            cited_urls=draft_dict["cited_urls"],
            unsupported_claims=critique_dict["unsupported_claims"],
            uncited_claims=critique_dict["uncited_claims"],
            needs_revision=critique_dict["needs_revision"],
        ))


def mark_completed(session_id: str, draft_dict: dict) -> None:
    with get_db() as db:
        db.query(ResearchSession).filter_by(id=session_id).update({
            "status": "completed",
            "final_answer": draft_dict["answer"],
            "final_cited_urls": draft_dict["cited_urls"],
            "completed_at": datetime.now(timezone.utc),
        })


def mark_failed(session_id: str, error: str) -> None:
    with get_db() as db:
        db.query(ResearchSession).filter_by(id=session_id).update({
            "status": "failed",
            "error": error,
            "completed_at": datetime.now(timezone.utc),
        })


def get_session(session_id: str) -> ResearchSession | None:
    with get_db() as db:
        return db.query(ResearchSession).filter_by(id=session_id).first()


def list_recent_sessions(limit: int = 20) -> list[ResearchSession]:
    with get_db() as db:
        return (
            db.query(ResearchSession)
            .order_by(ResearchSession.created_at.desc())
            .limit(limit)
            .all()
        )