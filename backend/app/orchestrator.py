"""
Orchestrator - Phase 3 version.

run_research_stream() is a generator: it yields (stage_name, payload)
after every pipeline step completes. This is the single source of
truth for pipeline sequencing.

- run_research() drains the generator and returns just the final
  result - used by the REST endpoint and manual_run.py, unchanged
  behavior from Phase 2.
- The WebSocket endpoint in main.py iterates the same generator
  directly, streaming and persisting each yield as it arrives.

Stages yielded, in order: "plan", "evidence", "revision_cycle" (one per
draft+critique pair, at least once), then always "done" last with the
final ResearchResult.
"""

import logging
from typing import Generator
from app.config import settings
from app.agents import planner, researcher, writer, critic
from app.models.schemas import ResearchResult, RevisionCycle, Plan, Evidence

logger = logging.getLogger(__name__)

StageEvent = tuple[str, object]


def run_research_stream(question: str) -> Generator[StageEvent, None, None]:
    logger.info("Planning for question: %s", question)
    plan: Plan = planner.plan(question)
    yield "plan", plan

    logger.info("Researching %d sub-questions", len(plan.sub_questions))
    evidence: list[Evidence] = researcher.research(plan.sub_questions)
    total_snippets = sum(len(e.snippets) for e in evidence)
    logger.info("Collected %d source snippets", total_snippets)
    yield "evidence", evidence

    logger.info("Drafting initial answer")
    draft = writer.write(question, evidence)

    logger.info("Critiquing initial draft")
    this_critique = critic.critique(draft, evidence, issue_threshold=settings.issue_tolerance)
    revision_history = [RevisionCycle(draft=draft, critique=this_critique)]
    yield "revision_cycle", revision_history[-1]

    cycle = 0
    while this_critique.needs_revision and cycle < settings.max_revision_cycles:
        cycle += 1
        logger.info(
            "Critique found %d issue(s), revising (cycle %d/%d)",
            this_critique.issue_count, cycle, settings.max_revision_cycles,
        )
        draft = writer.revise(question, evidence, draft, this_critique)

        logger.info("Critiquing revision %d", cycle)
        this_critique = critic.critique(draft, evidence, issue_threshold=settings.issue_tolerance)
        revision_history.append(RevisionCycle(draft=draft, critique=this_critique))
        yield "revision_cycle", revision_history[-1]

    if this_critique.needs_revision:
        logger.warning(
            "Hit max revision cycles (%d) - returning best-effort draft with %d known issue(s)",
            settings.max_revision_cycles, this_critique.issue_count,
        )
    else:
        logger.info("Draft passed critique after %d revision(s)", cycle)

    result = ResearchResult(
        question=question, plan=plan, evidence=evidence,
        draft=draft, revision_history=revision_history,
    )
    yield "done", result


def run_research(question: str) -> ResearchResult:
    """Drain the stream and return just the final result."""
    result: ResearchResult | None = None
    for stage, payload in run_research_stream(question):
        if stage == "done":
            result = payload
    if result is None:
        raise RuntimeError("Pipeline finished without producing a result")
    return result