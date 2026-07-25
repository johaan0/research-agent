"""
Shared data contracts between agent stages.

Keeping these as explicit Pydantic models (rather than passing raw
dicts/strings between agents) is what makes the orchestrator testable —
each stage has a typed input and output.
"""

from __future__ import annotations
from pydantic import BaseModel, Field


class Plan(BaseModel):
    """Output of the Planner stage."""
    original_question: str
    sub_questions: list[str] = Field(
        description="3-5 focused sub-questions that together cover the original question"
    )


class SourceSnippet(BaseModel):
    """A single piece of evidence pulled from a search result."""
    sub_question: str
    title: str
    url: str
    content: str  # short extracted snippet, not the full page


class Evidence(BaseModel):
    """Output of the Researcher stage."""
    sub_question: str
    snippets: list[SourceSnippet]


class Draft(BaseModel):
    """Output of the Writer stage."""
    answer: str
    # Which source URLs were actually cited in the answer text.
    cited_urls: list[str]


class ResearchResult(BaseModel):
    """Final payload returned to the client for one research run."""
    question: str
    plan: Plan
    evidence: list[Evidence]
    draft: Draft
