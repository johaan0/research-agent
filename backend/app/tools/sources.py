"""
Shared source numbering logic.

Both the Writer (drafting citations) and the Critic (checking citations)
need to reference sources by the same [1], [2], ... numbering. Previously
this lived only inside writer.py — pulled out here so both agents stay
in sync by construction, not by convention.
"""

from app.models.schemas import Evidence, SourceSnippet


def flatten_sources(evidence_list: list[Evidence]) -> list[SourceSnippet]:
    """Dedupe snippets by URL and flatten into one ordered list."""
    seen_urls: set[str] = set()
    flat: list[SourceSnippet] = []
    for evidence in evidence_list:
        for snippet in evidence.snippets:
            if snippet.url not in seen_urls:
                seen_urls.add(snippet.url)
                flat.append(snippet)
    return flat


def build_source_block(sources: list[SourceSnippet]) -> str:
    """Render sources as a numbered block for prompts: [1] Title (url)\ncontent"""
    lines = []
    for i, source in enumerate(sources, start=1):
        lines.append(f"[{i}] {source.title} ({source.url})\n{source.content}\n")
    return "\n".join(lines)