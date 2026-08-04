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


class ClaimIssue(BaseModel):
    """A single problem the Critic found in a draft."""
    sentence: str
    issue: str  # e.g. "not supported by cited source" or "no citation given"


class Critique(BaseModel):
    """Output of the Critic stage for one draft."""
    unsupported_claims: list[ClaimIssue] = Field(default_factory=list)
    uncited_claims: list[ClaimIssue] = Field(default_factory=list)
    needs_revision: bool

    @property
    def issue_count(self) -> int:
        return len(self.unsupported_claims) + len(self.uncited_claims)


class RevisionCycle(BaseModel):
    """One draft + the critique that was run against it."""
    draft: Draft
    critique: Critique


class ResearchResult(BaseModel):
    question: str
    plan: Plan
    evidence: list[Evidence]
    draft: Draft                          # final, accepted draft
    revision_history: list[RevisionCycle] # every draft+critique pair, in order
