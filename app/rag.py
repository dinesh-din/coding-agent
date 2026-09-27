"""
This is the RAG piece of the project.

Every time the agent solves a problem, we embed a short summary of it
(title + topic + a one-line description of the approach used) and store it
in a local Chroma collection. Before picking today's problem, we embed the
candidate problems and retrieve the closest matches from what's already been
solved — that lets the agent:

  1. avoid repeating a problem/topic it solved recently,
  2. pull the actual text of a similar past solution into the prompt so the
     LLM can stay consistent with your established code style, and
  3. eventually answer questions like "what have I already practiced?"
     without re-reading every file in the repo.

Chroma + sentence-transformers both run fully locally, so this needs no
extra API key.
"""
from __future__ import annotations

from typing import List, Optional

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings
from app.problems import Problem

_COLLECTION_NAME = "solved_problems"


class PracticeMemory:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(path=settings.chroma_path)
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name=_COLLECTION_NAME, embedding_function=self.embed_fn
        )

    def already_solved_ids(self) -> set[str]:
        result = self.collection.get(include=[])  # ids only
        return set(result.get("ids", []))

    def similar_past_solutions(self, problem: Problem, n_results: int = 2) -> List[str]:
        """Return short summaries of past solutions closest to this problem,
        so the LLM can stay consistent with prior style/approach."""
        if self.collection.count() == 0:
            return []
        query = f"{problem.title} ({problem.topic}, {problem.difficulty})"
        n = min(n_results, self.collection.count())
        results = self.collection.query(query_texts=[query], n_results=n)
        docs = results.get("documents", [[]])[0]
        return docs

    def record_solution(
        self,
        problem: Problem,
        approach_summary: str,
        commit_sha: Optional[str] = None,
    ) -> None:
        self.collection.upsert(
            ids=[problem.id],
            documents=[f"{problem.title} [{problem.topic}/{problem.difficulty}]: {approach_summary}"],
            metadatas=[{
                "title": problem.title,
                "topic": problem.topic,
                "difficulty": problem.difficulty,
                "commit_sha": commit_sha or "",
            }],
        )
