"""
Orchestrator — Phase 2 version (fixed).

Sequence: plan -> research -> write -> critique -> (revise -> critique)*
The critical invariant: whatever draft is returned has ALWAYS been
critiqued, even if it still has issues when max_revision_cycles is hit.
We never hand back a draft that skipped the check.
"""

import logging
from app.config import settings
from app.agents import planner, researcher, writer, critic
from app.models.schemas import ResearchResult, RevisionCycle

logger = logging.getLogger(__name__)


def run_research(question: str) -> ResearchResult:
    logger.info("Planning for question: %s", question)
    plan = planner.plan(question)

    logger.info("Researching %d sub-questions", len(plan.sub_questions))
    evidence = researcher.research(plan.sub_questions)

    total_snippets = sum(len(e.snippets) for e in evidence)
    logger.info("Collected %d source snippets", total_snippets)

    logger.info("Drafting initial answer")
    draft = writer.write(question, evidence)

    logger.info("Critiquing initial draft")
    this_critique = critic.critique(draft, evidence, issue_threshold=settings.issue_tolerance)
    revision_history = [RevisionCycle(draft=draft, critique=this_critique)]

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

    if this_critique.needs_revision:
        logger.warning(
            "Hit max revision cycles (%d) — returning best-effort draft with %d known issue(s)",
            settings.max_revision_cycles, this_critique.issue_count,
        )
    else:
        logger.info("Draft passed critique after %d revision(s)", cycle)

    return ResearchResult(
        question=question,
        plan=plan,
        evidence=evidence,
        draft=draft,
        revision_history=revision_history,
    )