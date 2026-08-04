"""
Writer stage.

`write()` drafts the first answer from evidence. `revise()` takes the
Critic's feedback about a previous draft and produces an improved one —
same rules, but now told specifically what to fix.
"""

import re
from app.llm_client import call_llm_text
from app.models.schemas import Evidence, Draft, Critique
from app.tools.sources import flatten_sources, build_source_block

SYSTEM_PROMPT = """You are a careful research writer. You will be given a \
question and a numbered list of source snippets gathered from the web.

Write a clear, well-organized answer to the question using ONLY \
information found in the provided sources.

Rules:
- Every factual claim must be followed by a citation marker like [1] or \
[2] referring to the source number it came from.
- If a claim is supported by multiple sources, cite all of them: [1][3].
- Do NOT include any information that isn't backed by a source, even if \
you know it from general knowledge.
- If the sources are insufficient to answer part of the question, say so \
explicitly rather than filling the gap yourself.
- Write in plain prose, no markdown headers needed.
"""

REVISION_SYSTEM_PROMPT = """You are a careful research writer revising a \
previous draft based on fact-checking feedback.

You will be given the question, the same numbered sources as before, your \
previous draft, and a list of specific problems a fact-checker found in it.

Rules:
- Fix every listed problem: either add a correct citation, remove the \
unsupported claim, or rephrase it as uncertain if the sources only \
partially support it.
- Do NOT introduce new claims that aren't in the sources.
- Keep everything from the previous draft that the fact-checker did NOT \
flag as a problem — only change what's broken.
- Write in plain prose, no markdown headers needed.
"""


def _extract_cited_urls(answer_text: str, sources) -> list[str]:
    cited_indices = {int(n) for n in re.findall(r"\[(\d+)\]", answer_text)}
    return [sources[i - 1].url for i in sorted(cited_indices) if 0 < i <= len(sources)]


def write(question: str, evidence_list: list[Evidence]) -> Draft:
    sources = flatten_sources(evidence_list)

    if not sources:
        return Draft(
            answer="I wasn't able to find any sources to answer this question. "
                   "Try rephrasing it or check that the search API is configured correctly.",
            cited_urls=[],
        )

    source_block = build_source_block(sources)
    user_prompt = f"Question: {question}\n\nSources:\n{source_block}"

    answer_text = call_llm_text(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    return Draft(answer=answer_text, cited_urls=_extract_cited_urls(answer_text, sources))


def revise(
    question: str,
    evidence_list: list[Evidence],
    previous_draft: Draft,
    critique: Critique,
) -> Draft:
    sources = flatten_sources(evidence_list)
    source_block = build_source_block(sources)

    problems = []
    for issue in critique.unsupported_claims:
        problems.append(f'- Unsupported claim: "{issue.sentence}" — {issue.issue}')
    for issue in critique.uncited_claims:
        problems.append(f'- Missing citation: "{issue.sentence}" — {issue.issue}')
    problems_block = "\n".join(problems)

    user_prompt = (
        f"Question: {question}\n\n"
        f"Sources:\n{source_block}\n\n"
        f"Previous draft:\n{previous_draft.answer}\n\n"
        f"Problems found by fact-checker:\n{problems_block}"
    )

    answer_text = call_llm_text(system_prompt=REVISION_SYSTEM_PROMPT, user_prompt=user_prompt)
    return Draft(answer=answer_text, cited_urls=_extract_cited_urls(answer_text, sources))