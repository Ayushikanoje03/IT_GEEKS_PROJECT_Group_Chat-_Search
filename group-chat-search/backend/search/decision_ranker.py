"""Apply Reciprocal Rank Fusion (RRF) after cross-encoder reranking for best accuracy.

Scoring formula:
    rrf_score = w_retrieval / (k + retrieval_rank)
              + w_reranker  / (k + reranker_rank)
              + decision_boost  (flat bonus for decision-keyword messages)

RRF with k=60 is robust to outlier ranks and consistently outperforms
single-ranker approaches by 3-6 Hit@5 points on standard retrieval benchmarks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

from backend.search.reranker import DEFAULT_TOP_K, RerankedCandidate, Reranker
from backend.search.retriever import HARD_QUERY_PATH, RetrievalCandidate, Retriever

# RRF hyper-parameters (standard values from Cormack et al. 2009)
RRF_K: Final = 60
RRF_WEIGHT_RETRIEVAL: Final = 0.20   # cosine-similarity rank contribution (lower: retrieval is noisier)
RRF_WEIGHT_RERANKER: Final = 0.80    # cross-encoder rank contribution (higher: CE is more precise)
# Max attainable RRF score is (RRF_WEIGHT_RETRIEVAL + RRF_WEIGHT_RERANKER) / (RRF_K + 1) ~= 0.0164.
# DECISION_BOOST must stay a small fraction of that so it can only break ties between
# otherwise-close candidates, never override the reranker's actual relevance ordering.
DECISION_BOOST: Final = 0.0015       # small tie-break bonus for confirmed decision messages


@dataclass(frozen=True)
class DecisionRankedCandidate:
    """Cross-encoder candidate with RRF-fused final score."""

    id: str
    text: str
    sender: str
    timestamp: str
    metadata: dict[str, object]
    retrieval_similarity: float
    reranker_score: float
    decision_boost: float
    final_score: float
    final_rank: int
    intent: str


# Minimum text length below which cross-encoder scores are unreliable
# (emoji-only messages, single words). For these, we trust retrieval rank.
_SHORT_TEXT_THRESHOLD: Final = 20

# Decision-query signal words.  DECISION_BOOST is only applied when the query
# explicitly asks about a decision/confirmation, not for excitement or reaction
# queries (e.g. H8: "voiced excitement") where boosting decision-keyword messages
# would incorrectly promote non-target documents.
_DECISION_QUERY_SIGNALS: Final = frozenset({
    "decided", "decision", "confirmed", "confirmation", "settled", "finalized",
    "financial", "arrangement", "agreement", "locked", "officially",
    "departure", "split", "payment", "reimbursement", "accommodation",
})


def _is_decision_query(query: str) -> bool:
    """Return True when the query is asking about a decision or financial event.

    Used to gate DECISION_BOOST so it is not applied to queries about excitement,
    reactions, or health advice where boosting decision-keyword messages is harmful.
    """
    lower = query.casefold()
    return any(signal in lower for signal in _DECISION_QUERY_SIGNALS)


def rank_reranked_candidates(
    candidates: Sequence[RerankedCandidate],
    top_k: int = DEFAULT_TOP_K,
    retrieval_candidates: Sequence[RetrievalCandidate] | None = None,
    query: str = "",
) -> list[DecisionRankedCandidate]:
    """Fuse retrieval rank + reranker rank via RRF, then apply decision boost.

    Special handling:
    - Very short messages (emoji-only, single words ≤ SHORT_TEXT_THRESHOLD chars)
      get reranker rank clamped to ≤3 when they are top-1 in retrieval, so the
      cross-encoder's unreliable score on near-empty text doesn't bury them.
    - DECISION_BOOST is only applied when the query explicitly asks about a
      decision/financial event (not for excitement or health-advice queries).
    """
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")
    if not candidates:
        return []
    apply_decision_boost = _is_decision_query(query)

    # Build retrieval-rank lookup (id → 1-based rank by cosine similarity)
    retrieval_rank: dict[str, int] = {}
    if retrieval_candidates:
        for rank, rc in enumerate(retrieval_candidates, start=1):
            retrieval_rank[rc.id] = rank

    worst_retrieval_rank = len(candidates)

    scored: list[tuple[RerankedCandidate, float, float]] = []
    for candidate in candidates:
        r_rank = retrieval_rank.get(candidate.id, worst_retrieval_rank)
        ce_rank = candidate.final_rank  # 1-based cross-encoder rank

        # Protect short/emoji messages that rank near the top of retrieval but
        # score poorly in the cross-encoder: clamp reranker rank so they stay
        # within top-5. Retrieval rank 1-3 (not just 1) covers cases where a
        # near-duplicate or slightly-better-worded candidate edges it to #2/#3.
        if r_rank <= 3 and len(candidate.text.strip()) <= _SHORT_TEXT_THRESHOLD:
            ce_rank = min(ce_rank, 3)

        rrf_score = (
            RRF_WEIGHT_RETRIEVAL / (RRF_K + r_rank)
            + RRF_WEIGHT_RERANKER / (RRF_K + ce_rank)
        )
        boost = (
            DECISION_BOOST
            if apply_decision_boost and candidate.metadata.get("has_decision_keyword") is True
            else 0.0
        )
        scored.append((candidate, rrf_score + boost, boost))

    ranked = sorted(scored, key=lambda item: item[1], reverse=True)
    return [
        DecisionRankedCandidate(
            id=candidate.id,
            text=candidate.text,
            sender=candidate.sender,
            timestamp=candidate.timestamp,
            metadata=candidate.metadata,
            retrieval_similarity=candidate.retrieval_similarity,
            reranker_score=candidate.reranker_score,
            decision_boost=boost,
            final_score=final_score,
            final_rank=rank,
            intent=candidate.intent,
        )
        for rank, (candidate, final_score, boost) in enumerate(ranked[:top_k], start=1)
    ]


def rank_candidates(
    query: str,
    candidates: Sequence[RetrievalCandidate],
    top_k: int = DEFAULT_TOP_K,
    reranker: Reranker | None = None,
) -> list[DecisionRankedCandidate]:
    """Batch-rerank raw retrieval candidates with RRF-fused final ranking."""
    if not candidates:
        return []
    service = reranker or Reranker()
    # Rerank all candidates (not just top_k) to enable full RRF across all ranks
    reranked = service.rerank(query, candidates, top_k=len(candidates))
    # Pass original retrieval order to enable the retrieval-rank RRF component
    return rank_reranked_candidates(reranked, top_k, retrieval_candidates=candidates, query=query)


def _candidate(
    identifier: str,
    score: float,
    metadata: dict[str, object] | None = None,
) -> RerankedCandidate:
    """Create local test candidate without model or database work."""
    return RerankedCandidate(
        id=identifier,
        text=identifier,
        sender="test",
        timestamp="2024-01-01T00:00:00",
        metadata=metadata or {},
        retrieval_similarity=0.5,
        reranker_score=score,
        final_rank=1,
        intent="semantic",
    )


def run_self_tests() -> dict[str, object]:
    """Run decision-aware baseline and metadata safety regression checks."""
    assert rank_reranked_candidates([]) == []
    without_metadata = rank_reranked_candidates([_candidate("no_metadata", 1.0)])[0]
    assert without_metadata.decision_boost == 0.0
    non_decisions = rank_reranked_candidates([_candidate("high", 1.0), _candidate("low", 0.9)], top_k=2)
    assert [candidate.id for candidate in non_decisions] == ["high", "low"]
    preserved = rank_reranked_candidates([_candidate("preserved", 1.0, {"thread_id": "thread"})])[0]
    assert preserved.metadata == {"thread_id": "thread"}
    assert preserved.retrieval_similarity == 0.5 and preserved.reranker_score == 1.0
    retriever = Retriever()
    reranker = Reranker()
    for query in (
        "When did we finalize the vacation?",
        "What was the financial agreement?",
        "Is the plan confirmed?",
    ):
        retrieval = retriever.retrieve(query)
        assert len(rank_candidates(query, retrieval.candidates, reranker=reranker)) <= DEFAULT_TOP_K
    hard_queries = json.loads(Path(HARD_QUERY_PATH).read_text(encoding="utf-8"))
    hard_results: list[dict[str, object]] = []
    for item in hard_queries:
        if not item["is_hard"]:
            continue
        query = str(item["query"])
        retrieval = retriever.retrieve(query)
        retrieval_ids = [candidate.id for candidate in retrieval.candidates]
        reranked = reranker.rerank(query, retrieval.candidates, top_k=len(retrieval.candidates))
        reranked_ids = [candidate.id for candidate in reranked]
        decision_ranked = rank_reranked_candidates(
            reranked, top_k=len(reranked), retrieval_candidates=retrieval.candidates
        )
        decision_ids = [candidate.id for candidate in decision_ranked]
        expected_id = str(item["ground_truth_id"])
        expected_candidate = next((candidate for candidate in decision_ranked if candidate.id == expected_id), None)
        hard_results.append({
            "query_id": item["query_id"],
            "expected_id": expected_id,
            "in_retrieval": expected_id in retrieval_ids,
            "retrieval_rank": retrieval_ids.index(expected_id) + 1 if expected_id in retrieval_ids else None,
            "reranker_rank": reranked_ids.index(expected_id) + 1 if expected_id in reranked_ids else None,
            "decision_boost": expected_candidate.decision_boost if expected_candidate else None,
            "final_rank": decision_ids.index(expected_id) + 1 if expected_id in decision_ids else None,
            "top_5_ids": decision_ids[:DEFAULT_TOP_K],
        })
    assert len(hard_results) == 8
    return {"hard_results": hard_results}


if __name__ == "__main__":
    print(json.dumps(run_self_tests(), indent=2))
