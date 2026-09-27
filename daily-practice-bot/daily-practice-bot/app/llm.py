"""
Thin wrapper around the Anthropic SDK. Deliberately NOT using LangChain here —
this hand-rolled call is ~30 lines and makes it obvious what an "agent step"
actually is: build a prompt, call the model, get text back. Once this feels
limiting (e.g. you want multi-tool routing, retries, streaming callbacks),
swapping in LangChain's AgentExecutor will make a lot more sense because
you'll have felt the problem it solves.
"""
from __future__ import annotations

from typing import List

import anthropic

from app.config import settings
from app.problems import Problem

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are a careful senior engineer writing a solution for a daily \
coding-practice repository. You will be given one problem and, optionally, \
short summaries of previously solved problems for style consistency.

Respond with THREE clearly delimited sections, in this exact format:

===SOLUTION===
<a single, complete, well-commented Python file that solves the problem, \
including a `if __name__ == "__main__":` block with 2-3 example calls>

===TESTS===
<a pytest file, `test_solution.py`, with at least 3 test cases including an \
edge case, importing from the solution file>

===EXPLANATION===
<a 3-6 sentence explanation of the approach and its time/space complexity, \
written for a README entry>
"""


def generate_solution(problem: Problem, similar_past: List[str]) -> dict:
    context = ""
    if similar_past:
        context = (
            "\n\nFor style consistency, here is a summary of similar problems "
            "you solved before:\n- " + "\n- ".join(similar_past)
        )

    user_prompt = (
        f"Problem: {problem.title} (difficulty: {problem.difficulty}, "
        f"topic: {problem.topic})\n\n{problem.prompt}{context}"
    )

    response = _client.messages.create(
        model=settings.model_name,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = response.content[0].text
    return _parse_sections(text)


def _parse_sections(text: str) -> dict:
    def extract(tag: str, next_tag: str | None) -> str:
        start = text.index(f"==={tag}===") + len(f"==={tag}===")
        end = text.index(f"==={next_tag}===") if next_tag else len(text)
        return text[start:end].strip()

    return {
        "solution": extract("SOLUTION", "TESTS"),
        "tests": extract("TESTS", "EXPLANATION"),
        "explanation": extract("EXPLANATION", None),
    }
