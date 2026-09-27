"""
Central config, loaded from environment variables (see .env.example).
Keeping this in one place makes every other module trivially testable —
you can monkeypatch `settings` instead of reaching into os.environ everywhere.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    model_name: str = os.getenv("MODEL_NAME", "claude-sonnet-4-5")

    practice_repo_path: str = os.getenv("PRACTICE_REPO_PATH", "./practice_repo")
    practice_repo_branch: str = os.getenv("PRACTICE_REPO_BRANCH", "main")
    git_author_name: str = os.getenv("GIT_AUTHOR_NAME", "Daily Practice Bot")
    git_author_email: str = os.getenv("GIT_AUTHOR_EMAIL", "bot@example.com")

    dry_run: bool = _bool("DRY_RUN", True)
    use_pull_request: bool = _bool("USE_PULL_REQUEST", False)
    max_diff_lines: int = int(os.getenv("MAX_DIFF_LINES", "400"))

    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_repo: str = os.getenv("GITHUB_REPO", "")

    chroma_path: str = os.getenv("CHROMA_PATH", "./data/chroma")
    problems_path: str = os.getenv("PROBLEMS_PATH", "./data/problems.json")
    db_path: str = os.getenv("DB_PATH", "./data/history.db")


settings = Settings()
