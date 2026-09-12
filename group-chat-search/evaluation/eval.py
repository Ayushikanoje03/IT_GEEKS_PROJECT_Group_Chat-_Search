"""Run corpus-grounded evaluation through final search ranking pipeline.

Metrics reported:
- Hit@1  — correct answer is rank-1 result
- Hit@5  — correct answer is in top-5 results
- Overall, Hard-8, Easy-32 breakdowns
- Gap: easy_accuracy - hard_accuracy (the headline number)
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, TypedDict

PROJECT_ROOT = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.search.decision_ranker import rank_candidates
from backend.search.embedder import cosine_similarity
from backend.search.intent import parse_query
from backend.search.retriever import RetrievalCandidate, Retriever, _result_limit, build_where_filter

TEST_QUERY_PATH = PROJECT_ROOT / "data" / "test_queries.json"
CORPUS_PATH = PROJECT_ROOT / "data" / "corpus.json"
TOP_K = 5
MAX_RETRIEVAL_CANDIDATES = 75
TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


class HardQueryCheck(TypedDict):
    """Validation outcome for one hard evaluation query."""

    query_id: str
    ground_truth_id: str
    overlap: list[str]
    has_zero_overlap: bool


class EvaluationRow(TypedDict):
    """One actual final-pipeline evaluation result."""

    query_id: str
    query: str
    intent: str
    expected_id: str
    top_5_ids: list[str]
    hit_at_1: int
    hit_at_5: int
    is_hard: bool


def load_test_queries() -> list[dict[str, object]]:
    """Read generated evaluation queries from JSON — called once, stored by caller."""
    if not TEST_QUERY_PATH.exists():
        raise FileNotFoundError(TEST_QUERY_PATH)
    data = json.loads(TEST_QUERY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Test query JSON must contain a list.")
    return [dict(item) for item in data]


def normalize_and_tokenize(text: str) -> set[str]:
    """Casefold Unicode text and extract alphanumeric word tokens."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return set(TOKEN_PATTERN.findall(normalized))


def validate_test_queries() -> dict[str, object]:
    """Validate query count, IDs, and hard-query zero lexical overlap."""
    queries = load_test_queries()
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    messages = {item["id"]: item for item in corpus}
    hard_checks: list[HardQueryCheck] = []
    missing_ids: list[str] = []
    for item in queries:
        message_id = str(item["ground_truth_id"])
        if message_id not in messages:
            missing_ids.append(message_id)
            continue
        if item["is_hard"]:
            overlap = sorted(
                normalize_and_tokenize(str(item["query"]))
                & normalize_and_tokenize(str(messages[message_id]["text"]))
            )
            hard_checks.append({
                "query_id": str(item["query_id"]),
                "ground_truth_id": message_id,
                "overlap": overlap,
                "has_zero_overlap": not overlap,
            })
    report = {
        "query_count": len(queries),
        "hard_query_count": len(hard_checks),
        "missing_ground_truth_ids": missing_ids,
        "hard_checks": hard_checks,
    }
    if (
        len(queries) != 40
        or len(hard_checks) != 8
        or missing_ids
        or not all(check["has_zero_overlap"] for check in hard_checks)
    ):
        raise ValueError(report)
    return report


def _validate_queries(queries: list[dict[str, object]]) -> dict[str, object]:
    """Validate a pre-loaded list of queries — avoids re-reading file."""
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    messages = {item["id"]: item for item in corpus}
    hard_checks: list[HardQueryCheck] = []
    missing_ids: list[str] = []
    for item in queries:
        message_id = str(item["ground_truth_id"])
        if message_id not in messages:
            missing_ids.append(message_id)
            continue
        if item["is_hard"]:
            overlap = sorted(
                normalize_and_tokenize(str(item["query"]))
                & normalize_and_tokenize(str(messages[message_id]["text"]))
            )
            hard_checks.append({
                "query_id": str(item["query_id"]),
                "ground_truth_id": message_id,
                "overlap": overlap,
                "has_zero_overlap": not overlap,
            })
    report = {
        "query_count": len(queries),
        "hard_query_count": len(hard_checks),
        "missing_ground_truth_ids": missing_ids,
        "hard_checks": hard_checks,
    }
    if (
        len(queries) != 40
        or len(hard_checks) != 8
        or missing_ids
        or not all(check["has_zero_overlap"] for check in hard_checks)
    ):
        raise ValueError(report)
    return report

def evaluate_queries() -> dict[str, Any]:
    """Evaluate every fixture query using retriever, reranker, and decision ranker."""
    # Single file read — passed into validator too, no double load
    all_queries = load_test_queries()
    validation = _validate_queries(all_queries)
    if validation["query_count"] != 40 or validation["hard_query_count"] != 8:
        raise ValueError("Evaluation fixture validation failed.")

    retriever = Retriever()
    rows: list[EvaluationRow] = []

    for item in all_queries:
        query = str(item["query"])
        expected_id = str(item["ground_truth_id"])
        retrieval = _retrieve_with_available_limit(retriever, query)
        ranked = rank_candidates(query, retrieval.candidates, top_k=TOP_K)
        top_ids = [candidate.id for candidate in ranked]
        rows.append({
            "query_id": str(item["query_id"]),
            "query": query,
            "intent": retrieval.parsed_query.intent.value,
            "expected_id": expected_id,
            "top_5_ids": top_ids,
            "hit_at_1": int(bool(top_ids) and top_ids[0] == expected_id),
            "hit_at_5": int(expected_id in top_ids),
            "is_hard": bool(item["is_hard"]),
        })

    hard_rows = [row for row in rows if row["is_hard"]]
    easy_rows = [row for row in rows if not row["is_hard"]]

    def _acc(row_list: list[EvaluationRow], key: str) -> float:
        return sum(row[key] for row in row_list) / len(row_list) if row_list else 0.0

    report = {
        "total_queries": len(rows),
        "overall_hits_at_5": sum(r["hit_at_5"] for r in rows),
        "overall_hits_at_1": sum(r["hit_at_1"] for r in rows),
        "overall_accuracy_at_5": _acc(rows, "hit_at_5"),
        "overall_accuracy_at_1": _acc(rows, "hit_at_1"),
        "hard_queries": len(hard_rows),
        "hard_hits_at_5": sum(r["hit_at_5"] for r in hard_rows),
        "hard_hits_at_1": sum(r["hit_at_1"] for r in hard_rows),
        "hard_accuracy_at_5": _acc(hard_rows, "hit_at_5"),
        "hard_accuracy_at_1": _acc(hard_rows, "hit_at_1"),
        "easy_queries": len(easy_rows),
        "easy_hits_at_5": sum(r["hit_at_5"] for r in easy_rows),
        "easy_hits_at_1": sum(r["hit_at_1"] for r in easy_rows),
        "easy_accuracy_at_5": _acc(easy_rows, "hit_at_5"),
        "easy_accuracy_at_1": _acc(easy_rows, "hit_at_1"),
        "gap_at_5": _acc(easy_rows, "hit_at_5") - _acc(hard_rows, "hit_at_5"),
        "gap_at_1": _acc(easy_rows, "hit_at_1") - _acc(hard_rows, "hit_at_1"),
        "results": rows,
    }
    return report


def get_collection(retriever: Retriever) -> Any:
    """Public accessor for the underlying Chroma collection."""
    return retriever._collection  # kept here to isolate the single private access


def _retrieve_with_available_limit(retriever: Retriever, query: str) -> Any:
    """Handle local Chroma HNSW candidate-limit failures gracefully."""
    last_error: RuntimeError | None = None
    for limit in range(MAX_RETRIEVAL_CANDIDATES, TOP_K - 1, -1):
        try:
            return retriever.retrieve(query, top_k=limit)
        except RuntimeError as error:
            cause_text = str(error.__cause__) if error.__cause__ else ""
            if "contigious 2D array" not in cause_text:
                raise
            last_error = error
    if last_error is None:
        raise RuntimeError("Chroma retrieval failed.")
    return _exact_chroma_fallback(retriever, query)


def _exact_chroma_fallback(retriever: Retriever, query: str) -> Any:
    """Evaluate Chroma records exactly when local HNSW cannot return results."""
    parsed = parse_query(query)
    where = build_where_filter(parsed)
    collection = get_collection(retriever)
    records = collection.get(where=where, include=["documents", "embeddings", "metadatas"])
    embedding = retriever._embedder.encode_query(parsed.cleaned_query)
    candidates = sorted(
        (
            RetrievalCandidate(
                id=str(identifier),
                text=str(document),
                sender=str(metadata["sender"]),
                timestamp=str(metadata["timestamp"]),
                distance=1.0 - cosine_similarity(embedding, vector),
                similarity=cosine_similarity(embedding, vector),
                metadata=dict(metadata),
                intent=parsed.intent.value,
            )
            for identifier, document, vector, metadata in zip(
                records["ids"], records["documents"], records["embeddings"], records["metadatas"]
            )
        ),
        key=lambda c: c.similarity,
        reverse=True,
    )[: _result_limit(parsed)]
    return type("FallbackResult", (), {"parsed_query": parsed, "candidates": candidates})()


def main() -> None:
    """Print complete metrics and per-query final-ranking results as JSON."""
    report = evaluate_queries()
    print("## EVALUATION RESULTS")
    print(f"Total queries      : {report['total_queries']}")
    print(f"Overall  Hit@5     : {report['overall_hits_at_5']}/{report['total_queries']}  ({report['overall_accuracy_at_5']:.1%})")
    print(f"Overall  Hit@1     : {report['overall_hits_at_1']}/{report['total_queries']}  ({report['overall_accuracy_at_1']:.1%})")
    print(f"Hard-8   Hit@5     : {report['hard_hits_at_5']}/8  ({report['hard_accuracy_at_5']:.1%})")
    print(f"Hard-8   Hit@1     : {report['hard_hits_at_1']}/8  ({report['hard_accuracy_at_1']:.1%})")
    print(f"Easy-32  Hit@5     : {report['easy_hits_at_5']}/32  ({report['easy_accuracy_at_5']:.1%})")
    print(f"Easy-32  Hit@1     : {report['easy_hits_at_1']}/32  ({report['easy_accuracy_at_1']:.1%})")
    print(f"Gap (easy-hard)@5  : {report['gap_at_5']:.1%}")
    print(f"Gap (easy-hard)@1  : {report['gap_at_1']:.1%}")
    print()
    print(json.dumps(report["results"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
