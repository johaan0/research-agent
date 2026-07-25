"""
Thin wrapper around Tavily's search API.

Tavily is used instead of a raw Google/Bing API because it's built
specifically for LLM agents: results come back as clean, short content
snippets rather than raw HTML you'd have to scrape and parse yourself.
"""

from tavily import TavilyClient
from app.config import settings
from app.models.schemas import SourceSnippet

_client = TavilyClient(api_key=settings.tavily_api_key)


def search(sub_question: str, max_results: int | None = None) -> list[SourceSnippet]:
    """
    Run a single web search for a sub-question and return normalized
    SourceSnippet objects.

    Raises the underlying Tavily exception on failure — the caller
    (researcher.py) decides how to handle a failed search rather than
    this function silently swallowing errors.
    """
    max_results = max_results or settings.results_per_subquestion

    response = _client.search(
        query=sub_question,
        max_results=max_results,
        search_depth="advanced",  # better snippet quality, still fast
        include_answer=False,
    )

    snippets: list[SourceSnippet] = []
    for result in response.get("results", []):
        snippets.append(
            SourceSnippet(
                sub_question=sub_question,
                title=result.get("title", "Untitled"),
                url=result["url"],
                content=result.get("content", "").strip(),
            )
        )
    return snippets
