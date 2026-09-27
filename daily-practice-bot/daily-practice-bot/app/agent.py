"""
The agent loop. Deliberately linear and readable rather than a generic
"tool-calling loop" — for this task the sequence of steps is fixed, so there's
nothing to gain from letting the LLM decide the plan itself. This is a good
lesson in its own right: not everything needs a full agentic loop with
free-form tool selection. Save that pattern for repo-maintenance-bot, where
the next action genuinely depends on what's found.

Flow:
  1. RAG: look at what's already been solved, pick an unsolved problem.
  2. RAG: retrieve summaries of similar past solutions for style context.
  3. LLM: generate solution + tests + explanation.
  4. Write files into the target repo.
  5. Record the new solution into the RAG store (before committing — see note
     below).
  6. Commit/push (or dry-run) with guardrails, in the SAME commit as the RAG
     store update.
  7. Log the run to SQLite.

Note on ordering: when this runs on a fresh checkout every time (e.g. a
GitHub Actions runner), the RAG store only survives between runs if it lives
inside the repo and gets committed+pushed. That means the "remember this
solution" step has to happen BEFORE commit_and_push, not after — otherwise
today's solve would never make it into the pushed state and tomorrow's run
would have amnesia. On a long-lived machine this ordering doesn't matter
(the RAG store persists on disk regardless of git), but it's harmless there
too, so we always do it this way.
"""
from __future__ import annotations

import random
from typing import Any

from app import db, git_ops, llm
from app.config import settings
from app.problems import Problem, load_problems
from app.rag import PracticeMemory


def pick_problem(memory: PracticeMemory) -> Problem | None:
    problems = load_problems()
    solved = memory.already_solved_ids()
    candidates = [p for p in problems if p.id not in solved]
    if not candidates:
        return None
    # Bias towards variety: prefer topics not seen in the last few solves.
    return random.choice(candidates)


def run_once() -> dict[str, Any]:
    memory = PracticeMemory()
    problem = pick_problem(memory)

    if problem is None:
        run_id = db.log_run("", "", "no_problems_left", True, None, None, {})
        return {"run_id": run_id, "status": "no_problems_left"}

    similar_past = memory.similar_past_solutions(problem)
    generated = llm.generate_solution(problem, similar_past)

    folder = git_ops.write_problem_files(
        problem.id, generated["solution"], generated["tests"], generated["explanation"]
    )

    # Record into the RAG store BEFORE committing (see module docstring) so
    # the state update ships in the same push as the solution files.
    if not settings.dry_run:
        memory.record_solution(problem, generated["explanation"])

    result = git_ops.commit_and_push(problem.id, folder)
    status = "committed" if result.committed else ("dry_run" if result.dry_run else "rejected")

    run_id = db.log_run(
        problem_id=problem.id,
        problem_title=problem.title,
        status=status,
        dry_run=result.dry_run,
        commit_sha=result.commit_sha,
        pr_url=result.pr_url,
        detail={
            "message": result.message,
            "diff_lines": result.diff_lines,
            "folder": str(folder),
            "explanation": generated["explanation"],
        },
    )

    return {
        "run_id": run_id,
        "problem": problem.title,
        "status": status,
        "message": result.message,
        "folder": str(folder),
        "commit_sha": result.commit_sha,
        "pr_url": result.pr_url,
    }


if __name__ == "__main__":
    # Entry point for `python -m app.agent` — this is what the GitHub Actions
    # workflow calls directly (no FastAPI/scheduler involved in that mode).
    import json
    import sys

    outcome = run_once()
    print(json.dumps(outcome, indent=2))
    if outcome["status"] == "rejected":
        # Non-zero exit makes the Actions run show as failed, so a rejected
        # (e.g. oversized) diff doesn't silently look like a normal day.
        sys.exit(1)
