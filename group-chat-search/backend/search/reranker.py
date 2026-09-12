"""Lazy, batch cross-encoder reranking for retrieved chat candidates.

Model priority:
  1. cross-encoder/mmarco-mMiniLMv2-L12-H384-v1  — multilingual (Hinglish-aware)
  2. cross-encoder/ms-marco-MiniLM-L-6-v2          — English-only fallback (cached)

The multilingual model is preferred. If it is not cached and HuggingFace is
unreachable, we fall back to the English model automatically so the app
remains usable offline.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Final, Sequence

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_TORCH", "1")

from sentence_transformers import CrossEncoder

from backend.search.retriever import HARD_QUERY_PATH, RetrievalCandidate, Retriever

# Preferred multilingual model (handles Hinglish properly)
RERANKER_MODEL_MULTILINGUAL: Final = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
# English-only fallback — always cached after first ingestion run
RERANKER_MODEL_FALLBACK: Final = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_TOP_K: Final = 5
_model_load_seconds: float | None = None


def _resolve_reranker_model() -> str:
    """Return the best available cross-encoder model name.

    Checks whether the multilingual model exists in the HuggingFace local
    cache. If it does, returns it. Otherwise returns the English fallback
    which is guaranteed to be cached from the ingestion step.
    """
    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    model_dir = "models--" + RERANKER_MODEL_MULTILINGUAL.replace("/", "--")
    if (cache_root / model_dir).exists():
        return RERANKER_MODEL_MULTILINGUAL
    return RERANKER_MODEL_FALLBACK


RERANKER_MODEL: Final = _resolve_reranker_model()


@lru_cache(maxsize=None)
def get_cross_encoder(model_name: str = RERANKER_MODEL) -> CrossEncoder:
    """Load each cross-encoder once per process, on first rerank request."""
    global _model_load_seconds
    started_at = perf_counter()
    model = CrossEncoder(model_name)
    _model_load_seconds = perf_counter() - started_at
    return model


@dataclass(frozen=True)
class RerankedCandidate:
    """Retrieved candidate plus raw cross-encoder relevance score and rank."""

    id: str
    text: str
    sender: str
    timestamp: str
    metadata: dict[str, object]
    retrieval_similarity: float
    reranker_score: float
    final_rank: int
    intent: str


class Reranker:
    """Batch-score retriever candidates with original, uncleaned user query."""

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        self._model_name = model_name

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        top_k: int = DEFAULT_TOP_K,
    ) -> list[RerankedCandidate]:
        """Return top candidates sorted by raw descending cross-encoder logits."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        if not candidates:
            return []
        model = get_cross_encoder(self._model_name)
        scores = model.predict([(query, candidate.text) for candidate in candidates])
        ranked = sorted(
            zip(candidates, (float(score) for score in scores)),
            key=lambda item: item[1],
            reverse=True,
        )
        return [
            RerankedCandidate(
                id=candidate.id,
                text=candidate.text,
                sender=candidate.sender,
                timestamp=candidate.timestamp,
                metadata=candidate.metadata,
                retrieval_similarity=candidate.similarity,
                reranker_score=score,
                final_rank=rank,
                intent=candidate.intent,
            )
            for rank, (candidate, score) in enumerate(ranked[:top_k], start=1)
        ]


def rerank(
    query: str,
    candidates: Sequence[RetrievalCandidate],
    top_k: int = DEFAULT_TOP_K,
) -> list[RerankedCandidate]:
    """Convenience API for reranking retrieved candidates."""
    return Reranker().rerank(query, candidates, top_k)


def run_self_tests() -> dict[str, object]:
    """Run retrieval-plus-reranking baseline without API, UI, or LLM layers."""
    retriever = Retriever()
    reranker = Reranker()
    sanity_query = "When did we finalize the vacation?"
    sanity_retrieval = retriever.retrieve(sanity_query)
    sanity_reranked = reranker.rerank(
        sanity_query, sanity_retrieval.candidates, top_k=len(sanity_retrieval.candidates)
    )
    assert get_cross_encoder() is get_cross_encoder()
    assert reranker.rerank(sanity_query, []) == []
    assert all(candidate.final_rank == index for index, candidate in enumerate(sanity_reranked, start=1))
    for query in (
        "What was the financial agreement?",
        "Is the plan confirmed?",
        "When did we decide on the trip?",
    ):
        candidates = retriever.retrieve(query).candidates
        assert len(reranker.rerank(query, candidates)) <= DEFAULT_TOP_K
    hard_queries = json.loads(Path(HARD_QUERY_PATH).read_text(encoding="utf-8"))
    hard_results: list[dict[str, object]] = []
    for item in hard_queries:
        if not item["is_hard"]:
            continue
        query = str(item["query"])
        retrieval = retriever.retrieve(query)
        retrieval_ids = [candidate.id for candidate in retrieval.candidates]
        expected_id = str(item["ground_truth_id"])
        reranked = reranker.rerank(query, retrieval.candidates, top_k=len(retrieval.candidates))
        reranked_ids = [candidate.id for candidate in reranked]
        hard_results.append({
            "query_id": item["query_id"],
            "intent": retrieval.parsed_query.intent.value,
            "expected_id": expected_id,
            "in_retrieval": expected_id in retrieval_ids,
            "retrieval_rank": retrieval_ids.index(expected_id) + 1 if expected_id in retrieval_ids else None,
            "reranker_rank": reranked_ids.index(expected_id) + 1 if expected_id in reranked_ids else None,
            "top_5_ids": reranked_ids[:DEFAULT_TOP_K],
            "top_5_scores": [round(candidate.reranker_score, 6) for candidate in reranked[:DEFAULT_TOP_K]],
        })
    assert len(hard_results) == 8
    return {
        "model_load_seconds": _model_load_seconds,
        "sanity_retrieval_top_10": [
            {"id": candidate.id, "retrieval_similarity": round(candidate.similarity, 6)}
            for candidate in sanity_retrieval.candidates[:10]
        ],
        "sanity_reranked_top_10": [
            {
                "id": candidate.id,
                "reranker_score": round(candidate.reranker_score, 6),
                "retrieval_similarity": round(candidate.retrieval_similarity, 6),
            }
            for candidate in sanity_reranked[:10]
        ],
        "hard_results": hard_results,
    }


if __name__ == "__main__":
    print(json.dumps(run_self_tests(), indent=2))
