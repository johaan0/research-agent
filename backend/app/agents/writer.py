"""
Writer stage.

Takes all collected evidence and drafts an answer that cites sources
inline as [1], [2], etc. The Writer is explicitly instructed to only
use information present in the evidence — this constraint is what the
Critic stage (Phase 2) will later verify.
"""

import re
from app.llm_client import call_llm_text
from app.models.schemas import Evidence, Draft, SourceSnippet

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


def _flatten_sources(evidence_list: list[Evidence]) -> list[SourceSnippet]:
    """Dedupe snippets by URL and flatten into one numbered list."""
    seen_urls: set[str] = set()
    flat: list[SourceSnippet] = []
    for evidence in evidence_list:
        for snippet in evidence.snippets:
            if snippet.url not in seen_urls:
                seen_urls.add(snippet.url)
                flat.append(snippet)
    return flat


def _build_source_block(sources: list[SourceSnippet]) -> str:
    lines = []
    for i, source in enumerate(sources, start=1):
        lines.append(f"[{i}] {source.title} ({source.url})\n{source.content}\n")
    return "\n".join(lines)


def write(question: str, evidence_list: list[Evidence]) -> Draft:
    sources = _flatten_sources(evidence_list)

    if not sources:
        return Draft(
            answer="I wasn't able to find any sources to answer this question. "
                   "Try rephrasing it or check that the search API is configured correctly.",
            cited_urls=[],
        )

    source_block = _build_source_block(sources)
    user_prompt = f"Question: {question}\n\nSources:\n{source_block}"

    answer_text = call_llm_text(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)

    # Figure out which source numbers were actually cited so we can
    # return the corresponding URLs alongside the draft.
    cited_indices = {int(n) for n in re.findall(r"\[(\d+)\]", answer_text)}
    cited_urls = [
        sources[i - 1].url for i in sorted(cited_indices) if 0 < i <= len(sources)
    ]

    return Draft(answer=answer_text, cited_urls=cited_urls)
