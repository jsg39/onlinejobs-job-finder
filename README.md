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

28 offline tests (`pytest`, no network) cover:
- HTML parsing against saved real pages, and the crawl delay
- every validator rule
- the agent loop with a scripted LLM: retry after rejection, bad arguments, unknown tools, step budget, text-only replies, cross-run memory, cache hits
- the eval scorer
