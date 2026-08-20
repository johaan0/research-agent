# Research Agent

A multi-agent research assistant that plans, searches, drafts, and **fact-checks its own answers** before returning them. Given a question, it breaks it into sub-questions, gathers web sources, writes a cited answer, and runs that answer through a self-correction loop — a Critic agent checks every citation against the source it points to, and the Writer revises anything that doesn't hold up. The full trace of that process (plan → sources → draft → critique → revision) is persisted and streamable live over WebSocket.

Built as a portfolio project to demonstrate agent orchestration, self-correction/evaluation loops, and real backend infrastructure (persistence, streaming) — not just a prompt-chaining demo.

---

## Architecture

```
Question
   │
   ▼
┌─────────┐     ┌────────────┐     ┌────────┐     ┌────────┐
│ Planner │ ──▶ │ Researcher │ ──▶ │ Writer │ ──▶ │ Critic │
└─────────┘     └────────────┘     └────────┘     └───┬────┘
                                        ▲              │
                                        │  needs_revision?
                                        └──────────────┘
                                     (up to N revision cycles)
```

- **Planner** — breaks the question into 3–5 focused, independently-searchable sub-questions
- **Researcher** — runs each sub-question through web search (Tavily), collects source snippets
- **Writer** — drafts a cited answer (`[1]`, `[2]`, ...) using only the retrieved evidence
- **Critic** — checks every citation against the actual source content; flags claims that are unsupported or missing a citation entirely
- **Revision loop** — if the Critic finds issues, the Writer revises specifically what was flagged (not a full rewrite), and the Critic checks again — capped at `MAX_REVISION_CYCLES` so a stubborn draft can't loop forever

The orchestrator (`orchestrator.py`) is a **generator** — it yields after every stage rather than running silently to the end. This is what allows the exact same pipeline logic to power both a simple synchronous REST call and a live-streaming WebSocket connection, with no duplicated code.

---

## Tech stack

| Piece | Choice | Why |
|---|---|---|
| LLM | [Groq](https://console.groq.com) — `openai/gpt-oss-120b` | Free tier, fast inference, no card required |
| Web search | [Tavily](https://tavily.com) | Built for LLM agents — clean snippets, not raw HTML |
| Backend | FastAPI | Async-native, easy WebSocket support |
| Database | Supabase Postgres via SQLAlchemy | Persists every run's plan/evidence/draft/critique history |
| Orchestration | Hand-rolled Python generator | No LangGraph/CrewAI — the state machine *is* the point of the project |

---

## What each phase built

### Phase 1 — Core pipeline
Straight-line `Planner → Researcher → Writer` pipeline. Given a question, produces one cited answer. No verification — the Writer is *instructed* to only cite real sources, but nothing checks that it did. Exposed via `POST /research` and a CLI test script (`tests/manual_run.py`).

### Phase 2 — Critic + self-correction loop
Added the `Critic` agent and a revision loop: `write → critique → (revise → critique)*`. The Critic re-checks each citation against the actual source content, flagging unsupported or uncited claims. The Writer's `revise()` fixes only what was flagged rather than rewriting from scratch. Caught and fixed a real bug during testing where the orchestrator could return a final draft that had been revised *after* the last critique — meaning it was never actually re-verified. Fixed so the loop always returns a draft that was checked.

### Phase 3 — Persistence + live streaming
- `db.py`: every research run is persisted to Postgres (`sessions` table) as it progresses, with one `revision_cycles` row per draft/critique pair — nothing is lost when the terminal closes.
- `orchestrator.py` refactored into a generator (`run_research_stream`) that yields after each stage. `run_research()` (used by the REST endpoint and CLI) simply drains it — unchanged behavior, single source of truth for pipeline sequencing.
- New `WS /ws/research` endpoint streams each stage to a connected client in real time and persists it simultaneously.
- `trace_test.html`: a dependency-free HTML/JS client to watch a run live in the browser without needing a full React build — proof the streaming works, ahead of a proper frontend.

---

## Project structure

```
research-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app: POST /research, WS /ws/research, GET /sessions
│   │   ├── orchestrator.py         # Generator-based pipeline sequencing (single source of truth)
│   │   ├── db.py                   # SQLAlchemy models + persistence helpers (Supabase Postgres)
│   │   ├── config.py               # Typed settings loaded from .env
│   │   ├── llm_client.py           # Shared Groq client, JSON-mode helper, rate-limit retry
│   │   ├── agents/
│   │   │   ├── planner.py          # Question -> sub-questions
│   │   │   ├── researcher.py       # Sub-questions -> evidence (via Tavily)
│   │   │   ├── writer.py           # Evidence -> cited draft; revise() fixes flagged issues
│   │   │   └── critic.py           # Draft -> list of unsupported/uncited claims
│   │   ├── tools/
│   │   │   ├── web_search.py       # Tavily wrapper
│   │   │   └── sources.py          # Shared source numbering (Writer and Critic must agree on [1], [2]...)
│   │   └── models/
│   │       └── schemas.py          # Pydantic contracts: Plan, Evidence, Draft, Critique, ResearchResult
│   ├── tests/
│   │   └── manual_run.py           # CLI: python -m tests.manual_run "question"
│   ├── trace_test.html             # Live-trace viewer, no build step
│   ├── requirements.txt
│   └── .env.example
└── README.md
```

---

## Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
python -m pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

```
GROQ_API_KEY=            # console.groq.com — free, no card
TAVILY_API_KEY=          # tavily.com — free tier, 1000 credits/month
DATABASE_URL=            # Supabase → Project Settings → Database → Connect →
                          # use the SESSION POOLER string, not the direct connection
                          # (direct connections are IPv6-only and fail on most networks)

GROQ_MODEL=openai/gpt-oss-120b
MAX_SUBQUESTIONS=5
RESULTS_PER_SUBQUESTION=3
MAX_REVISION_CYCLES=2
ISSUE_TOLERANCE=1         # 0 = strictest (any flagged issue triggers a revision);
                          # 1-2 tolerates minor nitpicks so the loop converges faster
```

**Run it:**

```bash
# Quick CLI test
python -m tests.manual_run "What are the tradeoffs of RAG vs fine-tuning?"

# As a server
uvicorn app.main:app --reload
```

Then either:
- `POST http://localhost:8000/research` with `{"question": "..."}` for a single synchronous JSON response, or
- Open `trace_test.html` directly in a browser and click **Run** to watch the pipeline live via WebSocket

---

## Lessons learned / engineering notes

A few real issues hit during development, kept here because they're as much a part of the story as the code:

- **Free-tier rate limits are a real constraint, not a footnote.** Groq's free tier caps `gpt-oss-120b` at 8,000 tokens/minute — a single research run fires several LLM calls back-to-back (plan, write, critique, possibly revise+critique again), and untruncated source snippets alone could blow past that. Fixed by (a) truncating snippet content before building prompts and (b) adding automatic retry-with-backoff on rate-limit responses in `llm_client.py`, rather than letting the pipeline crash.
- **Reasoning models need explicit token budgeting.** `gpt-oss-120b` spends tokens "thinking" before producing its final answer; without `reasoning_effort="low"` and enough headroom in `max_tokens`, a complex prompt could exhaust the budget on internal reasoning and return an empty completion.
- **Supabase's direct connection string is IPv6-only** — fails with "could not translate host name" on most networks that don't route IPv6 properly. The fix is the **Session Pooler** connection string instead, which is IPv4-compatible.
- **A generator-based orchestrator was worth the refactor.** Early on, the revision loop's `for` loop could return a draft that was revised *after* the last critique check — meaning the "final" answer shown to the user was never actually verified, silently defeating the point of the Critic. Rewriting the loop as `critique → while needs_revision: revise → critique` (instead of "revise blindly N times") guarantees the returned draft was always the one just checked.

---

## Roadmap

- **Phase 4** — guardrails (search/token budget caps already partially in place) + a small hand-built evaluation set (10–15 questions) to measure faithfulness/completeness across configs
- **Phase 5** — polish: deploy backend + a proper React `TraceView` (upgrading from `trace_test.html`), record a demo, write up design decisions
