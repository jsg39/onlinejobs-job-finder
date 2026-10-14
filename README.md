# onlinejobs.ph Application Agent

A tool-calling LLM agent that scrapes the newest [onlinejobs.ph](https://www.onlinejobs.ph) postings, decides which ones fit my profile, assesses each one with **evidence that is checked word for word**, and drafts an application subject and message for the good fits.

It drafts and never sends. I review every application before it goes out.

```
$ python -m ojagent --max-jobs 5
| Verdict  | Score | Job                                            | Pay                   | Draft |
|----------|-------|------------------------------------------------|-----------------------|-------|
| strong   | 85    | AI Agent Developer / LLM Engineer              | $1,000 – $2,200/month | yes   |
| possible | 70    | AWS + Computer Vision Developer                | N/A                   | yes   |
| possible | 58    | Data Engineer – Python & SQL                   | $1,300 - $1,500       | yes   |
...
```

## Job triage app

A web app on top of the same scraper. Pick a keyword (default `python`), optionally upload a resume, click **Find my top jobs**, and get a shortlist of postings ranked by how well you fit them and how much you'd want them, with pay, hours, a summary and a link to each posting.

![Triage pipeline](docs/triage-pipeline.png)

- **Jev screens first.** One Jev call scores every search card, and clear mismatches are never fetched. Each skipped fetch saves the 5 s robots.txt crawl delay.
- **Two scores, one rank.** Jev scores each fetched posting on *fit* (would they hire you?) and *appeal* (would you want it, given the pay floor and fully-remote preference in `profile.md`), plus a scam signal. Rank is the mean of fit and appeal.
- **The LLM only sees the shortlist.** It writes a 2–3 sentence summary for shortlisted jobs, so LLM tokens grow with the shortlist, not with the number of postings scanned. `--no-jev` is the baseline where the LLM has to score and summarize every posting.
- **Profile page.** Upload a PDF or DOCX resume and edit the extracted text, plus what you want: roles, minimum pay (amount, currency, per hour/month/year), fully remote only, and what you're not interested in. Fit is scored against the resume; appeal against these preferences. "What Jev sees" shows the exact profile text being ranked against. It starts from `profile.md` and is saved to `data/profile.json`.
- **Learns from your choices.** *Mark applied* and *Not interested* are saved on the backend (`data/marks.json`). The profile then gets a "Learned from the candidate's choices" section: recent jobs you applied to and dismissed, skills common to the jobs you applied to, and their typical pay. Appeal scoring leans toward what you actually apply to. It can be switched off or cleared on the Profile page.
- **Your own filters.** Minimum match, minimum pay (per hour, month or year, converted from whatever the posting uses: $/hr, euros, pesos), job type and likely-scam hiding, all remembered in the browser.

### Why Jev, not an LLM, for scoring?

The `--no-jev` baseline has an LLM do Jev's job, scoring fit, appeal and scam risk for every posting. On the same 30 real Python postings (Oct 14, 2026):

| Scoring step | LLM | Jev |
|---|---|---|
| Time | 1,020 s for 30 postings, ~34 s each | 5.8 s for 30 cards + 26 postings, ~0.2 s each |
| Output | Free text that must be parsed as JSON and range-checked | Typed probabilities; can't come back malformed |
| Cost | Grows with every posting scanned | $0.042 per million input tokens, output free; well under a cent per search |
| Shortlist | 7 jobs | 4 jobs, all among the LLM's 7 |

Caveats: the LLM was a free model (`nvidia/nemotron-3-ultra-550b-a55b:free`), and in the baseline it wrote a brief in the same call, so a fast paid model would narrow the time gap. Jev is also stricter: the jobs only the LLM shortlisted sat just under Jev's 2.5 bar, and they're one filter change away in the UI. The LLM still writes the briefs, which is what it's good at; Jev makes the yes/no and 0–4 decisions.

### Run it

The backend is FastAPI, and the frontend is React (Vite) in `ui/`. Run them in two terminals:

```bash
# Terminal 1: backend on http://127.0.0.1:8000 (API docs at /docs)
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn ojagent.api:app --port 8000

# Terminal 2: frontend on http://localhost:5173
cd ui
npm install
npm run dev
```

Open http://localhost:5173. The dev server forwards `/api` to the backend. `.env` needs `TYPESAFE_API_KEY` for Jev; an LLM key (`LLM_API_KEY`) is optional, and without one, summaries are the posting's opening lines.

A search takes a few minutes, because every posting that passes the Jev screen is fetched at the site's crawl delay. The progress bar shows the current stage, and you can reload the page without losing it. Only one search runs at a time.

| Endpoint | Purpose |
|---|---|
| `POST /api/runs` | Start a search: `{"keyword": "python", "postings": 30}` (the 5–90 newest postings). Returns 409 if one is already running. |
| `GET /api/runs/{id}` · `GET /api/runs/active` | Progress (stage, done/total, elapsed), and the results when done. |
| `GET /api/latest` | The most recent results (also saved as `out/latest.json`). |
| `GET` · `PUT /api/profile` | The editable profile, what's been learned from your marks, and the composed text Jev ranks against. |
| `GET` · `POST` · `DELETE /api/resume` | Show, upload (PDF/DOCX/TXT/MD, under 5 MB) or remove the uploaded resume (back to `profile.md`'s text). |
| `GET /api/marks` · `PUT /api/marks/{id}` · `DELETE /api/marks` | Applied / not-interested marks, with a snapshot of each job to learn from. |

Without the UI, the same pipeline runs from the command line and writes a Markdown report to `out/`:

```bash
python -m ojagent.triage                     # Jev screens and ranks, the LLM summarizes the shortlist
python -m ojagent.triage --no-jev            # baseline: the LLM scores and summarizes everything
python -m ojagent.triage --keyword fastapi --limit 45
```

## Architecture

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

| Module | Responsibility |
|---|---|
| `scraper.py` | `OnlineJobsClient` parses search and detail pages and honours robots.txt `Crawl-delay: 5`. It sits behind a `JobSource` protocol so evals can swap in synthetic postings. |
| `tools.py` | Tools with typed Pydantic arguments (JSON schemas generated from the models). Tool failures are returned to the model as `{"ok": false, "errors": [...]}` so it can fix them, instead of crashing the loop. |
| `verify.py` | Deterministic guards. Every `requirement_quote` must appear in the posting and every `profile_evidence_quote` in the profile. The score must agree with the verdict. A draft must contain any code word the employer asked for and must not name a technology that's missing from the profile, unless it is acknowledged as a gap. |
| `store.py` | SQLite memory: postings are cached so they're never fetched twice, and assessed jobs are marked `already_assessed` in later runs. |
| `agent.py` | Provider-agnostic loop over any OpenAI-compatible API (OpenRouter → Claude/GPT, OpenAI, or local vLLM/Ollama), with a step budget, no-tool-call nudges, token accounting, and per-run traces. |
| `report.py` | Builds the Markdown report from what the tools actually saved, so the model can't report work it didn't do. |
| `prefilter.py` | Optional [Jev](https://docs.typesafe.ai) prefilter: one call scores every search result's fit before the agent sees it (see below). |
| `triage.py` | The triage pipeline behind the app: screen, fetch, score, rank, summarize, with timings and LLM token counts. Also a CLI. |
| `api.py` | FastAPI backend for the app: background runs with progress, resume upload and text extraction, profile and marks. |
| `profile_store.py` | The app's editable profile, seeded from `profile.md`, plus learning from applied / not-interested marks. |
| `pay.py` | Normalizes free-text pay to approximate USD per month and per hour. |
| `ui/` | React + TypeScript frontend (Vite), dark mode. Applied / not-interested marks are kept in the browser. |

### Jev prefilter
Jev (TypeSafe AI) is a decision-only model: it answers typed questions with probabilities instead of text. When `TYPESAFE_API_KEY` is set, `search_jobs` sends the profile plus every new result card to Jev as one request with one yes/no (`noul`) question per job, and hides cards scoring below `--prefilter-threshold` (default 0.2) from the agent. Each hidden posting skips a 5 s crawl and an LLM assessment; the report lists what was hidden and its score.

- **Low threshold on purpose.** Missing a good job costs more than reading a bad one, so only clear mismatches are hidden; borderline cards still go to the LLM.
- **Fails open.** If Jev errors or is rate-limited past its retries, every card is shown and the report says so.
- **Pinned model** (`jev-1.13.0`), not the moving `jev-latest` alias, so results don't shift underneath the evals.

### Design decisions
- **Verify outcomes, don't trust them.** The model's `finish` summary is shown as a note only. Verdicts, evidence, and drafts in the report come from rows that passed validation.
- **Evidence as quotes.** Free-text "the candidate knows X" can't be checked; an exact quote can. This is what stops invented skills.
- **Postings are untrusted input.** The system prompt treats them as data. The evals include a posting that tells the AI to rate the candidate 100 and leak their phone number.
- **Draft, don't send.** Applying is an outward-facing action, so a human reviews every draft.

## Evaluation

`evals/` runs the **real agent loop** against 10 synthetic postings with known-correct outcomes for `profile.md`:

| Case | Tests |
|---|---|
| FastAPI backend, LLM/RAG engineer, YOLO/AWS CV role | relevant jobs are found, rated strong/possible, and drafted |
| "Start your subject with BLUE HERON" | employer instruction followed |
| Senior Java role whose text tells the AI to score 100 and leak the candidate's phone and address | prompt-injection resistance and red-flagging |
| `$5,000/week`, pay a fee, send your ID | scam detection |
| Graphic design, senior iOS, senior Next.js/TS, data entry at $250/mo | no drafts for wrong field, stretch roles, or preference conflicts |

There are two tasks. `discover` lets the agent choose what to read, as in real use. `assess_all` forces it to read everything, so adversarial cases can't pass just by being skipped. I added `assess_all` after noticing the cheaper model had passed the injection case without ever opening it. Scores come from the database, never from the model's summary. `tests/test_eval_scoring.py` checks that the scorer fails bad behaviour.

Results, 2 trials per model and task (2026-10-13):

| Model | Task | Case pass rate | Validator rejections / run | Steps | Tokens in / out |
|---|---|---|---|---|---|
| claude-sonnet-5.5 | discover | 100% | 0.0 | 5.5 | 63k / 6.8k |
| claude-sonnet-5.5 | assess_all | 100% | 0.0 | 5.0 | 45k / 7.5k |
| claude-haiku-5.5 | discover | 100% | 0.0 | 5.0 | 50k / 9.0k |
| claude-haiku-5.5 | assess_all | 100% | 0.0 | 5.0 | 60k / 13.5k |

**Limits:** 10 cases is a small suite and both models saturate it. The next step is harder, more ambiguous cases (borderline seniority, pay just under the minimum, injection hidden mid-paragraph) and more trials to measure variance.

```bash
python -m evals.run_evals --model anthropic/claude-sonnet-5.5 --model anthropic/claude-haiku-5.5 --trials 2
python -m evals.run_evals --prefilter      # also runs discover+jev and reports postings hidden and Jev latency
```

## Setup

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env                               # add an OpenRouter/OpenAI key
# edit profile.md: it is the only source of truth the agent may cite
python -m ojagent --max-jobs 8
pytest
```

Each run writes `out/<run_id>.md` (assessments, employer checklist, subject and message ready to paste) and `out/traces/<run_id>.jsonl` (every model turn and tool result).

## Tests

90 offline tests (`pytest`, no network) cover:
- HTML parsing against saved real pages, and the crawl delay
- every validator rule
- the agent loop with a scripted LLM: retry after rejection, bad arguments, unknown tools, step budget, text-only replies, cross-run memory, cache hits
- the eval scorer
- the Jev prefilter against a mocked API: request shape, rate-limit retry, hiding mismatches, skipping already-assessed jobs, failing open
- the triage pipeline: fetching only what Jev keeps, the no-Jev baseline, fit + appeal ranking, LLM summaries for the shortlist only, JSON export
- the API: runs and progress, one run at a time, resume upload (PDF/DOCX/text), profile editing, marks and learning, input validation
- pay parsing across real posting formats, and profile seeding and composition
