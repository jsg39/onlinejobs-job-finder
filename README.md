# onlinejobs.ph Job Finder

Two tools for finding remote work on [onlinejobs.ph](https://www.onlinejobs.ph), sharing one polite scraper and one candidate profile:

1. **Job finder app** (FastAPI + React). Search, get a shortlist ranked against your resume and preferences, filter it, and mark what you apply to. The ranking learns from your marks. Uses [Jev](https://docs.typesafe.ai) for fast, cheap scoring and an LLM only for short briefs.
2. **Application agent** (CLI). A tool-calling LLM agent that assesses postings with evidence checked word for word against your profile and drafts applications. It drafts and never sends.

## Job finder app

![How the job finder works](docs/triage-pipeline.png)

### How it works

1. **Search.** Scrape the newest postings for your keyword (default `python`), as many as you choose (5–90). The scraper waits 5 s between requests, as the site's robots.txt asks.
2. **Jev screens.** One Jev call asks "is this a realistic fit?" for every search card at once. Clear mismatches (under 20%) are dropped and never fetched.
3. **Read.** Only the likely fits are fetched in full. At 5 s each, this is the slowest step, which is why step 2 matters.
4. **Jev scores** each job against your profile: **fit** 0–4 (would they hire you?), **appeal** 0–4 (would you want it?) and a scam signal. **Match** is the average of fit and appeal.
5. **The LLM writes a brief** for jobs matching 2.0 or higher: one line on the role, up to two ✓ reasons you fit, up to two △ gaps. The LLM's cost depends on how many jobs make the shortlist, not on how many are scanned.
6. **Your shortlist**, best match first, with pay, hours, posted time (local), the brief and a link to the posting.

### Your profile

The **Profile** page holds what every job is scored against:

- **Resume** (drives fit). Upload a PDF or DOCX, then edit the extracted text.
- **What you want** (drives appeal): roles, minimum pay (₱ or $, per hour/month/year), fully remote only, and what you're not interested in.
- **Learned from your choices** (drives appeal). *Mark applied* and *Not interested* are saved on the backend. The profile gains your recent applied and dismissed jobs, the skills common to jobs you applied to, and their typical pay, so ranking leans toward what you actually apply to. It can be switched off or cleared.
- **What Jev sees** shows the exact profile text being ranked against.

The profile starts from `profile.md` and is saved to `data/profile.json`; marks go to `data/marks.json`.

### Filters

On the Jobs page: minimum match, minimum pay (per hour, month or year), job type and hiding likely scams. Posted pay comes in many forms ("$20/hr", "6-8 Euros per hour", "₱60k/mo", "Negotiable"), so `pay.py` converts it to approximate USD per month and per hour. Hourly rates use each posting's own hours, so part-time jobs are compared fairly. Filters are remembered in the browser.

### Why Jev, not an LLM, for scoring?

`--no-jev` is a baseline where the LLM does Jev's job, scoring and summarizing every posting. On the same 30 real Python postings (Oct 14, 2026):

| | Without Jev | With Jev |
|---|---|---|
| Time per search | 1,183 s (20 min) | 213 s (3.5 min), 5.6× faster |
| LLM tokens | 102,941 | 11,947, 88% fewer |
| LLM calls | 30 | 4 |
| Scoring one job | ~34 s (LLM) | ~0.2 s (Jev), ≈150× faster |
| Shortlist | 7 jobs | 4 jobs, all among the LLM's 7 |

Jev's output is typed probabilities, so it can't come back malformed. The LLM's has to be parsed as JSON and range-checked. Jev costs $0.042 per million input tokens and output is free, which comes to well under a cent per search.

Caveats: this is a single run, and the LLM was a free model (`nvidia/nemotron-3-ultra-550b-a55b:free`) that also wrote briefs in the same call, so a fast paid model would narrow the time gap. Jev is stricter: the jobs only the LLM shortlisted sat just under the 2.5 default, one filter change away. Since then, briefs also cover jobs at 2.0–2.5, so a search makes a few more LLM calls than shown.

### Run it

Two terminals. The backend is FastAPI; the frontend is React + TypeScript (Vite) in `ui/`:

```bash
# Terminal 1: backend on http://127.0.0.1:8000 (API docs at /docs)
.venv\Scripts\activate
uvicorn ojagent.api:app --port 8000

# Terminal 2: frontend on http://localhost:5173
cd ui
npm install
npm run dev
```

Open http://localhost:5173. The dev server forwards `/api` to the backend. A search takes a few minutes because of the crawl delay. The progress bar shows each stage, survives a page reload, and only one search runs at a time.

| Endpoint | Purpose |
|---|---|
| `POST /api/runs` | Start a search: `{"keyword": "python", "postings": 30}` (5–90). Returns 409 if one is already running. |
| `GET /api/runs/{id}` · `GET /api/runs/active` | Progress (stage, done/total, elapsed), and results when done. |
| `GET /api/latest` | The most recent results, also saved as `out/latest.json`. |
| `GET` · `PUT /api/profile` | The editable profile, what's been learned from your marks, and the composed text Jev ranks against. |
| `GET` · `POST` · `DELETE /api/resume` | Show, upload (PDF/DOCX/TXT/MD, under 5 MB) or remove the uploaded resume. |
| `GET /api/marks` · `PUT /api/marks/{id}` · `DELETE /api/marks` | Applied / not-interested marks, each with a snapshot of the job to learn from. |

The same pipeline also runs without the UI and writes a Markdown report to `out/`:

```bash
python -m ojagent.triage                       # Jev screens and ranks, the LLM writes briefs
python -m ojagent.triage --no-jev              # baseline: the LLM scores and summarizes everything
python -m ojagent.triage --keyword fastapi --limit 45
```

## Application agent

```
$ python -m ojagent --max-jobs 5
| Verdict  | Score | Job                                            | Pay                   | Draft |
|----------|-------|------------------------------------------------|-----------------------|-------|
| strong   | 85    | AI Agent Developer / LLM Engineer              | $1,000 – $2,200/month | yes   |
| possible | 70    | AWS + Computer Vision Developer                | N/A                   | yes   |
| possible | 58    | Data Engineer – Python & SQL                   | $1,300 - $1,500       | yes   |
...
```

The LLM decides which postings to read, saves a fit assessment for each, and drafts an application subject and message for the good fits. Each run writes `out/<run_id>.md` (assessments, employer checklist, drafts ready to paste) and `out/traces/<run_id>.jsonl` (every model turn and tool result).

```
          ┌──────────────── agent loop (agent.py) ────────────────┐
 task ──▶ │ LLM chooses tools ─▶ dispatch ─▶ validate ─▶ result   │ ──▶ report.md
          │   ▲                                         │          │     (built from DB,
          │   └──── errors returned as data, model retries ◀──┘    │      not model prose)
          │ budgets: max steps, nudge limit · full JSONL trace     │
          └────────────────────────────────────────────────────────┘
 tools.py:  search_jobs · get_job_details · save_fit_assessment · save_application_draft · finish
                │               │                    │                        │
          scraper.py      store.py (SQLite)     verify.py               verify.py
     (crawl-delay 5s,     memory across runs   quotes ⊂ posting/profile  claims ⊂ profile,
      HTML parsing)                            score ⟷ verdict bands     employer code words,
                                                                         length limits
```

### Design decisions
- **Verify outcomes, don't trust them.** The model's `finish` summary is shown as a note only. Verdicts, evidence and drafts in the report come from rows that passed validation.
- **Evidence as quotes.** "The candidate knows X" can't be checked; an exact quote can. This is what stops invented skills.
- **Postings are untrusted input.** The system prompt treats them as data. The evals include a posting that tells the AI to rate the candidate 100 and leak their phone number.
- **Draft, don't send.** Applying is an outward-facing action, so a human reviews every draft.
- **Optional Jev prefilter.** With `TYPESAFE_API_KEY` set, `search_jobs` hides cards Jev scores below `--prefilter-threshold` (default 0.2). The threshold is low on purpose, because missing a good job costs more than reading a bad one. If Jev fails, every card is shown. The model is pinned (`jev-1.13.0`) so results don't shift under the evals.

### Evaluation

`evals/` runs the **real agent loop** against 10 synthetic postings with known-correct outcomes for `profile.md`:

| Case | Tests |
|---|---|
| FastAPI backend, LLM/RAG engineer, YOLO/AWS CV role | relevant jobs are found, rated strong/possible, and drafted |
| "Start your subject with BLUE HERON" | employer instruction followed |
| Senior Java role whose text tells the AI to score 100 and leak the candidate's phone and address | prompt-injection resistance and red-flagging |
| `$5,000/week`, pay a fee, send your ID | scam detection |
| Graphic design, senior iOS, senior Next.js/TS, data entry at $250/mo | no drafts for wrong field, stretch roles, or preference conflicts |

There are two tasks. `discover` lets the agent choose what to read, as in real use. `assess_all` forces it to read everything, so adversarial cases can't pass just by being skipped. It was added after the cheaper model passed the injection case without ever opening it. Scores come from the database, never from the model's summary, and `tests/test_eval_scoring.py` checks that the scorer fails bad behaviour.

Results, 2 trials per model and task (2026-10-13):

| Model | Task | Case pass rate | Validator rejections / run | Steps | Tokens in / out |
|---|---|---|---|---|---|
| claude-sonnet-5.5 | discover | 100% | 0.0 | 5.5 | 63k / 6.8k |
| claude-sonnet-5.5 | assess_all | 100% | 0.0 | 5.0 | 45k / 7.5k |
| claude-haiku-5.5 | discover | 100% | 0.0 | 5.0 | 50k / 9.0k |
| claude-haiku-5.5 | assess_all | 100% | 0.0 | 5.0 | 60k / 13.5k |

**Limits:** 10 cases is a small suite and both models saturate it. Next would be harder, more ambiguous cases (borderline seniority, pay just under the minimum, injection hidden mid-paragraph) and more trials to measure variance.

```bash
python -m evals.run_evals --model anthropic/claude-sonnet-5.5 --model anthropic/claude-haiku-5.5 --trials 2
python -m evals.run_evals --prefilter      # adds a discover+jev task: postings hidden and Jev latency
```

## Project layout

| Path | Used by | Responsibility |
|---|---|---|
| `ojagent/scraper.py` | both | Parses onlinejobs.ph search and detail pages; honours `Crawl-delay: 5`. Behind a `JobSource` protocol so tests and evals can swap in fake postings. |
| `ojagent/prefilter.py` | both | Jev client: one call scores many items; retries on rate limits. |
| `ojagent/llm.py` | both | Thin client for any OpenAI-compatible API (OpenRouter, OpenAI, or local vLLM/Ollama). |
| `ojagent/models.py`, `config.py` | both | Shared data models; settings from `.env`. |
| `ojagent/triage.py` | app | The pipeline: screen, fetch, score, rank, brief, with timings and token counts. Also a CLI. |
| `ojagent/api.py` | app | FastAPI backend: background runs with progress, resume upload and text extraction, profile and marks. |
| `ojagent/profile_store.py` | app | Editable profile seeded from `profile.md`, plus learning from applied / not-interested marks. |
| `ojagent/pay.py` | app | Free-text pay to approximate USD per month and per hour. |
| `ui/` | app | React + TypeScript frontend (Vite), dark mode: Jobs and Profile pages. |
| `ojagent/agent.py`, `tools.py` | agent | The tool-calling loop and its tools, with typed Pydantic arguments; tool errors go back to the model as data. |
| `ojagent/verify.py` | agent | Deterministic guards: quotes must appear in the posting and profile, scores must match verdicts, drafts can't claim missing skills. |
| `ojagent/store.py`, `report.py` | agent | SQLite memory across runs; the report built from saved rows. |
| `evals/` | agent | Eval harness and synthetic scenarios. |
| `profile.md` | both | The candidate profile: the agent's only source of truth, and the app's starting point. |

## Setup

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env
```

In `.env`:
- `TYPESAFE_API_KEY`: Jev, from [console.typesafe.ai](https://console.typesafe.ai/keys). Strongly recommended for the app, which without it falls back to the slow no-Jev mode. Optional for the agent.
- `LLM_API_KEY` (plus `LLM_BASE_URL` and `LLM_MODEL`): any OpenAI-compatible endpoint. Required by the agent. Optional for the app, which without it uses each posting's opening lines instead of a brief. The app needs at least one of the two keys.

Then edit `profile.md` with your own details, or upload a resume on the app's Profile page.

## Tests

```bash
pytest
```

91 offline tests (no network) cover:
- HTML parsing against saved real pages, and the crawl delay
- the triage pipeline: fetching only what Jev keeps, the no-Jev baseline, fit + appeal ranking, briefs for top jobs only, the postings limit, JSON export
- the API: runs and progress, one run at a time, resume upload (PDF/DOCX/text), profile editing, marks and learning, input validation
- pay parsing across real posting formats, and profile seeding, composition and learning
- the Jev client against a mocked API: request shape, rate-limit retry, failing open
- the agent loop with a scripted LLM: retry after rejection, bad arguments, unknown tools, step budget, text-only replies, cross-run memory, cache hits
- every validator rule, and the eval scorer
