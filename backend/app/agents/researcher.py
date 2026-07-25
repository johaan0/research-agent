"""
Researcher stage.

For each sub-question from the Planner, run a web search and collect
the results as structured evidence. This stage does NOT summarize or
interpret — it just gathers raw material for the Writer to work with.
Keeping search and writing separate makes each stage easier to test
and debug independently.
"""

import logging
from app.models.schemas import Evidence
from app.tools import web_search

logger = logging.getLogger(__name__)


def research(sub_questions: list[str]) -> list[Evidence]:
    """
    Run a search for every sub-question. If an individual search fails,
    log it and continue with an empty evidence set for that sub-question
    rather than failing the whole pipeline — partial results are still
    useful to the Writer stage.
    """
    evidence_list: list[Evidence] = []

    for sub_question in sub_questions:
        try:
            snippets = web_search.search(sub_question)
        except Exception:
            logger.exception("Search failed for sub-question: %s", sub_question)
            snippets = []

        evidence_list.append(
            Evidence(sub_question=sub_question, snippets=snippets)
        )

    return evidence_list
