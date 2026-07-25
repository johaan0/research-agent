"""
Orchestrator — Phase 1 version.

This is intentionally a plain, linear function rather than a framework
(no LangGraph/CrewAI). Phase 2 will turn this into a proper state
machine that supports the Critic -> revision loop; for now it just
proves the plan -> research -> write pipeline works end to end.
"""

import logging
from app.agents import planner, researcher, writer
from app.models.schemas import ResearchResult

logger = logging.getLogger(__name__)


def run_research(question: str) -> ResearchResult:
    logger.info("Planning for question: %s", question)
    plan = planner.plan(question)

    logger.info("Researching %d sub-questions", len(plan.sub_questions))
    evidence = researcher.research(plan.sub_questions)

    total_snippets = sum(len(e.snippets) for e in evidence)
    logger.info("Collected %d source snippets", total_snippets)

    logger.info("Drafting answer")
    draft = writer.write(question, evidence)

    return ResearchResult(
        question=question,
        plan=plan,
        evidence=evidence,
        draft=draft,
    )
