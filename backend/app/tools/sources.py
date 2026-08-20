"""
Shared source numbering logic.

Both the Writer (drafting citations) and the Critic (checking citations)
need to reference sources by the same [1], [2], ... numbering - pulled
out here so both agents stay in sync by construction, not by convention.

build_source_block() also truncates each snippet's content. Full scraped
page snippets can run 300-500+ tokens each; with 3-4 sources per
sub-question across 3 sub-questions, untruncated content alone can blow
past free-tier per-minute token limits (Groq's free tier caps GPT-OSS
120B at 8,000 TPM). A few hundred characters is plenty for both drafting
and fact-checking.
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


def build_source_block(sources: list[SourceSnippet], max_content_chars: int = 500) -> str:
    """Render sources as a numbered block for prompts: [1] Title (url)\ncontent"""
    lines = []
    for i, source in enumerate(sources, start=1):
        content = source.content[:max_content_chars]
        if len(source.content) > max_content_chars:
            content += "..."
        lines.append(f"[{i}] {source.title} ({source.url})\n{content}\n")
    return "\n".join(lines)