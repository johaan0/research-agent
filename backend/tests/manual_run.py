"""
Manual smoke test — not pytest, just a quick way to run the full
pipeline from the command line and eyeball the output before you've
built the frontend.

Usage (from backend/ directory, with venv active and .env filled in):
    python -m tests.manual_run "What caused the 2008 financial crisis?"
"""

import sys
import json
from app.orchestrator import run_research


def main():
    question = " ".join(sys.argv[1:]) or "What is retrieval-augmented generation?"
    print(f"\nQuestion: {question}\n{'-' * 60}")

    result = run_research(question)

    print("\nSUB-QUESTIONS:")
    for sq in result.plan.sub_questions:
        print(f"  - {sq}")

    total_snippets = sum(len(e.snippets) for e in result.evidence)
    print(f"\nSOURCES FOUND: {total_snippets}")

    print(f"\nANSWER:\n{result.draft.answer}")

    print(f"\nCITED URLS ({len(result.draft.cited_urls)}):")
    for url in result.draft.cited_urls:
        print(f"  - {url}")

    # Dump full structured result too, useful for debugging
    with open("last_run_output.json", "w") as f:
        json.dump(result.model_dump(), f, indent=2)
    print("\nFull structured output written to last_run_output.json")


if __name__ == "__main__":
    main()
