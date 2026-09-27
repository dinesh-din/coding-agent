# Daily Practice Bot

An agent that picks a coding problem it hasn't solved before, writes a
solution + tests, and commits it to a git repo — once a day, on autopilot.
Built as a learning project for FastAPI, retrieval-augmented generation
(RAG), and agentic tool use, without hiding any of it behind a heavyweight
framework.

## Why this design

- **RAG, used for something real.** Every solved problem is embedded and
  stored in a local Chroma collection (`app/rag.py`). Before solving a new
  problem, the agent retrieves summaries of similar past solutions so the
  new one stays stylistically consistent, and it uses the same store to
  avoid ever repeating a problem.
- **No LangChain, on purpose (for now).** The "agent loop" in `app/agent.py`
  is a fixed, readable sequence: pick problem → retrieve context → generate
  → write → commit. Hand-rolling this first teaches you what a framework
  like LangChain is actually abstracting away, before you reach for it.
- **Guardrails around the scary part.** An agent that pushes to git
  unattended is worth being paranoid about. See `app/git_ops.py`:
  - `DRY_RUN=true` by default — writes files and computes a diff, but never
    commits or pushes. Turn it off only once you trust the output.
  - `MAX_DIFF_LINES` refuses to commit a suspiciously large change.
  - `USE_PULL_REQUEST=true` pushes to a fresh branch and opens a PR instead
    of touching `main` directly, so a human still reviews before merge.
- **Everything is logged.** Every run is recorded in SQLite (`app/db.py`)
  and readable via `GET /history` — an audit trail, not a black box.

## Architecture

```
agent.run_once() (app/agent.py) — the shared core, used by both run modes
  1. rag.PracticeMemory.already_solved_ids()   ─┐
  2. problems.load_problems()                   ├─ pick an unsolved problem
  3. rag.PracticeMemory.similar_past_solutions() → retrieve style context
  4. llm.generate_solution()                     → Claude writes solution+tests
  5. git_ops.write_problem_files()               → write to target repo
  6. rag.PracticeMemory.record_solution()        → embed + store (before commit,
                                                    so state ships in the same push)
  7. git_ops.commit_and_push()                   → guarded commit/PR
  8. db.log_run()                                → audit log

Option A — GitHub Actions:
  .github/workflows/daily-practice.yml runs `python -m app.agent` on a cron
  schedule. The repo checkout IS the target repo (PRACTICE_REPO_PATH="."),
  and .bot-state/ (RAG store + SQLite log) is committed into the repo so it
  survives across runs even though each run starts from a clean checkout.

Option B — FastAPI + local/server:
  FastAPI (app/main.py)
    ├─ POST /run        → background job → agent.run_once()
    └─ GET  /history     → reads SQLite log
  scheduler.py: APScheduler cron job calls run_once() once a day.
  State lives on that machine's disk and never needs to be committed.
```

## Setup — Option A: GitHub Actions (recommended)

This is the easiest way to get real daily commits with nothing to host or
keep running yourself. The workflow at `.github/workflows/daily-practice.yml`
uses GitHub's own scheduler and its automatically-provided `GITHUB_TOKEN` to
push — you never hand out a personal access token or SSH key at all, and
there's no server for you to keep alive.

1. **Create a new (or reuse an empty) GitHub repo**, e.g.
   `github.com/dinesh-din/daily-practice`, and push this entire project into
   it as-is (the workflow file, `app/`, `requirements-actions.txt`, etc. all
   go in):

   ```bash
   cd daily-practice-bot
   git init
   git add .
   git commit -m "Initial commit: daily practice bot"
   git branch -M main
   git remote add origin git@github.com:dinesh-din/daily-practice.git
   git push -u origin main
   ```

2. **Add one repo secret**: in the repo on GitHub, go to Settings → Secrets
   and variables → Actions → New repository secret, and add
   `ANTHROPIC_API_KEY` with your Anthropic API key. That's the only secret
   needed — git push access comes for free from the workflow's own
   `permissions: contents: write`.

3. **Test it manually first**: go to the Actions tab → "Daily Practice Bot" →
   "Run workflow", tick `dry_run` the first time, and check the run's logs
   to see what it would have written. Run it again with `dry_run` unticked
   once it looks right — this makes a real commit.

4. **Let it run**: the schedule in the workflow (`cron: "0 13 * * *"`, i.e.
   ~8am Central) fires automatically from then on. Adjust the cron
   expression to whatever time you want.

State (which problems have been solved, and the run log) lives in
`.bot-state/` inside the repo itself and is committed alongside each
solution — that's what lets a bot with zero persistent server remember what
it already did yesterday.

## Setup — Option B: run it yourself (local machine or a server)

Use this if you want the FastAPI control layer, a live `/history` API, or
just prefer running it somewhere you control instead of GitHub's runners.

1. **Clone the repo the bot will commit into**, somewhere on disk, with push
   credentials already working (SSH key or a git credential helper) — this
   project does not manage your git auth for you:

   ```bash
   git clone git@github.com:dinesh-din/daily-practice.git
   ```

2. **Install dependencies:**

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure:**

   ```bash
   cp .env.example .env
   # edit .env: ANTHROPIC_API_KEY, PRACTICE_REPO_PATH, GIT_AUTHOR_*
   # leave DRY_RUN=true for your first several runs
   ```

4. **Run the API:**

   ```bash
   uvicorn app.main:app --reload
   ```

5. **Trigger a run and inspect it before trusting it:**

   ```bash
   curl -X POST http://localhost:8000/run/sync
   curl http://localhost:8000/history
   ```

   With `DRY_RUN=true`, check the files it wrote inside your practice repo
   folder under `problems/<date>-<problem-id>/` before flipping `DRY_RUN`
   to `false`.

6. **Go live:** set `DRY_RUN=false` (and `USE_PULL_REQUEST=true` if you'd
   rather review a PR than let it push straight to `main`), restart the
   app, and leave it running — the built-in scheduler fires once a day at
   09:00 server time (edit `start_scheduler()` in `app/main.py` to change
   that). Here `data/chroma/` and `data/history.db` just live on that
   machine's disk permanently — they don't need to be committed to git the
   way they do under Option A.

## Ideas to extend it

- Swap the local `data/problems.json` bank for a real source (LeetCode's
  public GraphQL API, or your own backlog in Notion/Airtable).
- Add a `run_tests` tool that actually executes the generated pytest file
  in a sandboxed subprocess before committing, and feeds failures back to
  the LLM for a self-correction pass.
- Track topic coverage over time (e.g. weight problem selection towards
  topics you've solved least) using the metadata already stored in Chroma.
- Add a `/history` view as a tiny static HTML page so you can see your
  practice streak without hitting the API by hand.
- Move from local Chroma to a hosted vector DB (Qdrant, pgvector) once you
  want this reachable from more than one machine.
- Add LangSmith or a simple custom tracer around `llm.generate_solution`
  to log prompts/responses for later inspection.
