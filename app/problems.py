"""
The problem bank. Starts as a small local JSON file so the whole project
runs with zero external dependencies on day one. Swap `load_problems()`
for a call to a real API (LeetCode's GraphQL endpoint, a Notion database,
whatever) once the local list feels small.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from app.config import settings


@dataclass
class Problem:
    id: str
    title: str
    difficulty: str
    topic: str
    prompt: str


def load_problems() -> List[Problem]:
    with open(settings.problems_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Problem(**item) for item in raw]
