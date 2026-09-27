"""
All the git/GitHub side-effects live here, isolated from the "thinking" code
in agent.py. This is the part that should scare you a little as a beginner —
an autonomous agent writing to your git history — so it's built with three
guardrails baked in:

  1. DRY_RUN (default true): writes files and computes a diff, never commits.
  2. MAX_DIFF_LINES: refuses to commit a suspiciously large change.
  3. USE_PULL_REQUEST: pushes to a fresh branch and opens a PR instead of
     touching main directly, so a human still reviews before merge.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import git
from git import Repo

from app.config import settings


@dataclass
class CommitResult:
    dry_run: bool
    committed: bool
    branch: str
    commit_sha: str | None
    diff_lines: int
    pr_url: str | None
    message: str


def _repo() -> Repo:
    return Repo(settings.practice_repo_path)


def write_problem_files(problem_id: str, solution: str, tests: str, explanation: str) -> Path:
    """Write the generated files into <repo>/problems/<date>-<problem_id>/."""
    folder = Path(settings.practice_repo_path) / "problems" / f"{date.today().isoformat()}-{problem_id}"
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "solution.py").write_text(solution, encoding="utf-8")
    (folder / "test_solution.py").write_text(tests, encoding="utf-8")
    (folder / "README.md").write_text(f"# {problem_id}\n\n{explanation}\n", encoding="utf-8")
    return folder


def _state_dir_rel_path() -> str | None:
    """If the RAG/history state lives inside the target repo (as it does when
    running in a stateless environment like a GitHub Actions runner, where
    every run starts from a fresh checkout), return its path relative to the
    repo so it can be staged in the same commit as the solution files. Returns
    None if the state lives outside the repo (e.g. a long-lived local machine
    where the on-disk state persists on its own and doesn't need to be
    committed at all)."""
    repo_root = Path(settings.practice_repo_path).resolve()
    state_dir = Path(settings.chroma_path).resolve().parent
    try:
        return str(state_dir.relative_to(repo_root))
    except ValueError:
        return None


def commit_and_push(problem_id: str, folder: Path) -> CommitResult:
    repo = _repo()
    rel_path = str(folder.relative_to(settings.practice_repo_path))
    paths_to_add = [rel_path]

    state_rel_path = _state_dir_rel_path()
    if state_rel_path and Path(settings.practice_repo_path, state_rel_path).exists():
        paths_to_add.append(state_rel_path)

    repo.git.add(*paths_to_add)
    diff_lines = len(repo.git.diff("--cached", "--stat").splitlines())

    if settings.dry_run:
        repo.git.reset()  # unstage, leave the files on disk for you to inspect
        return CommitResult(
            dry_run=True, committed=False, branch=settings.practice_repo_branch,
            commit_sha=None, diff_lines=diff_lines, pr_url=None,
            message=f"DRY RUN: would commit {rel_path} ({diff_lines} lines changed).",
        )

    if diff_lines > settings.max_diff_lines:
        repo.git.reset()
        return CommitResult(
            dry_run=False, committed=False, branch=settings.practice_repo_branch,
            commit_sha=None, diff_lines=diff_lines, pr_url=None,
            message=f"Refused: diff of {diff_lines} lines exceeds MAX_DIFF_LINES={settings.max_diff_lines}.",
        )

    with repo.config_writer() as cw:
        cw.set_value("user", "name", settings.git_author_name)
        cw.set_value("user", "email", settings.git_author_email)

    commit_message = f"Daily practice: {problem_id} ({date.today().isoformat()})"

    if settings.use_pull_request:
        branch_name = f"daily-practice/{problem_id}-{date.today().isoformat()}"
        repo.git.checkout("-b", branch_name)
        commit = repo.index.commit(commit_message)
        repo.git.push("origin", branch_name)
        pr_url = _open_pull_request(branch_name, commit_message)
        repo.git.checkout(settings.practice_repo_branch)
        return CommitResult(
            dry_run=False, committed=True, branch=branch_name,
            commit_sha=commit.hexsha, diff_lines=diff_lines, pr_url=pr_url,
            message=f"Pushed branch {branch_name} and opened PR.",
        )

    commit = repo.index.commit(commit_message)
    repo.git.push("origin", settings.practice_repo_branch)
    return CommitResult(
        dry_run=False, committed=True, branch=settings.practice_repo_branch,
        commit_sha=commit.hexsha, diff_lines=diff_lines, pr_url=None,
        message="Committed and pushed directly to branch.",
    )


def _open_pull_request(branch_name: str, title: str) -> str | None:
    if not settings.github_token or not settings.github_repo:
        return None
    from github import Github

    gh = Github(settings.github_token)
    repo = gh.get_repo(settings.github_repo)
    pr = repo.create_pull(
        title=title,
        body="Automated daily practice submission. Review before merging.",
        head=branch_name,
        base=settings.practice_repo_branch,
    )
    return pr.html_url
