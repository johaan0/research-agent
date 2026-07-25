"""
Planner stage.

Takes the user's raw question and breaks it into a small number of
focused, independently-searchable sub-questions. Good decomposition
here is what makes the researcher stage effective — vague sub-questions
produce vague search results.
"""

from app.config import settings
from app.llm_client import call_llm_json
from app.models.schemas import Plan

SYSTEM_PROMPT = """You are a research planner. Given a user's question, break it \
down into focused, independently-searchable sub-questions that together \
would let someone write a complete, well-sourced answer.

Rules:
- Produce between 3 and {max_subquestions} sub-questions.
- Each sub-question must be specific enough to search the web for directly \
(avoid vague sub-questions like "background information").
- Do not produce sub-questions that just rephrase the original question.
- Return ONLY valid JSON, no preamble, no markdown code fences.

JSON schema:
{{"sub_questions": ["...", "..."]}}
"""


def plan(question: str) -> Plan:
    system_prompt = SYSTEM_PROMPT.format(max_subquestions=settings.max_subquestions)
    result = call_llm_json(
        system_prompt=system_prompt,
        user_prompt=f"User question: {question}",
    )

    sub_questions = result.get("sub_questions", [])
    if not sub_questions:
        raise ValueError("Planner returned no sub-questions.")

    return Plan(
        original_question=question,
        sub_questions=sub_questions[: settings.max_subquestions],
    )
