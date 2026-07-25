# Research Agent — Phase 1

Multi-agent research assistant. Phase 1 implements the straight-line
pipeline: **Planner -> Researcher -> Writer**. No critique/revision
loop yet (that's Phase 2), no live trace UI (Phase 3).

## What Phase 1 proves

Given a question, the system:
1. Breaks it into focused sub-questions (Planner)
2. Searches the web for each one (Researcher)
3. Writes a cited answer using only the retrieved evidence (Writer)

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
- `GROQ_API_KEY` — from console.groq.com
- `TAVILY_API_KEY` — from tavily.com (free tier is enough for dev)

## Run it

**Option A — quick manual test from the command line:**
```bash
python -m tests.manual_run "What are the tradeoffs of RAG vs fine-tuning?"
```
This prints the sub-questions, sources found, final answer, and cited
URLs, and dumps the full structured result to `last_run_output.json`.

**Option B — as an API:**
```bash
uvicorn app.main:app --reload
```
Then:
```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the tradeoffs of RAG vs fine-tuning?"}'
```

## File guide

| File | Responsibility |
|---|---|
| `app/config.py` | Loads env vars into a typed `Settings` object |
| `app/llm_client.py` | Shared Anthropic client + JSON-mode helper |
| `app/models/schemas.py` | Pydantic contracts between stages (Plan, Evidence, Draft) |
| `app/tools/web_search.py` | Tavily search wrapper |
| `app/agents/planner.py` | Question -> sub-questions |
| `app/agents/researcher.py` | Sub-questions -> evidence (raw search results) |
| `app/agents/writer.py` | Evidence -> cited draft answer |
| `app/orchestrator.py` | Sequences the three stages |
| `app/main.py` | FastAPI endpoint wrapping the orchestrator |

## Known limitations (by design — this is Phase 1)

- No fact-checking: the Writer is instructed to only use provided
  sources, but nothing verifies it actually did. That's the Critic's
  job in Phase 2.
- Fully synchronous — a request blocks until the whole pipeline
  finishes. Phase 3 adds WebSocket streaming so you see each stage
  complete in real time.
- No persistence — nothing is saved to a database yet.

## Next: Phase 2

Add `app/agents/critic.py` that checks each sentence in the draft
against the evidence, and extend `orchestrator.py` into a proper loop:
`plan -> research -> write -> critique -> (revise -> critique)* -> final`.
