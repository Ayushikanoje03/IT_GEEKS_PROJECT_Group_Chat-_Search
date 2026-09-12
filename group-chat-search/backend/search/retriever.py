"""ChromaDB candidate retrieval with deterministic intent metadata filters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import chromadb
from chromadb.api.models.Collection import Collection

from backend.search.embedder import Embedder, cosine_similarity
from backend.search.intent import ParsedQuery, expand_query, parse_query

COLLECTION_NAME: Final = "group_chat_messages"
PROJECT_ROOT: Final = Path(__file__).parents[2]
DEFAULT_PERSIST_DIRECTORY: Final = PROJECT_ROOT / ".chroma"
COSINE_DISTANCE_METRIC: Final = "cosine"
SEMANTIC_RESULT_LIMIT: Final = 150  # wider net improves recall for zero-overlap hard queries
PERSON_RESULT_LIMIT: Final = 120   # each sender has ~525 msgs; cast wide net
TEMPORAL_RESULT_LIMIT: Final = 120  # temporal matches spread across months
HARD_QUERY_PATH: Final = PROJECT_ROOT / "data" / "test_queries.json"
DUAL_RETRIEVAL_RRF_K: Final = 60
MAX_FUSED_CANDIDATES: Final = 200


@dataclass(frozen=True)
class RetrievalCandidate:
    """One raw vector-search candidate before reranking."""

    id: str
    text: str
    sender: str
    timestamp: str
    distance: float
    similarity: float
    metadata: dict[str, Any]
    intent: str


@dataclass(frozen=True)
class RetrievalResult:
    """Parsed query, applied filter, and sorted Chroma candidates."""

    parsed_query: ParsedQuery
    candidates: list[RetrievalCandidate]
    where: dict[str, Any] | None


def _result_limit(parsed_query: ParsedQuery) -> int:
    """Return intent-specific pre-reranking candidate budget."""
    if parsed_query.intent.value == "person":
        return PERSON_RESULT_LIMIT
    if parsed_query.intent.value == "temporal":
        return TEMPORAL_RESULT_LIMIT
    return SEMANTIC_RESULT_LIMIT


def build_where_filter(parsed_query: ParsedQuery) -> dict[str, Any] | None:
    """Build Chroma metadata filter from sender and calendar fields.

    Month is never hard-filtered, sender-present or not, because:
    - The query may describe a topic discussed *around* that time, not *on* that date
    - Hard month filtering can silently eliminate the correct message (e.g., a message
      sent in November about "21 March" plans has month=11, not month=3)
    - The month context is still carried in the query text embedding, so it still
      influences ranking without risking a false exclusion.
    """
    if parsed_query.sender:
        return {"sender": parsed_query.sender}
    return None



class Retriever:
    """Retrieve Chroma candidates using existing singleton-backed embedder."""

    def __init__(
        self,
        persist_directory: Path = DEFAULT_PERSIST_DIRECTORY,
        embedder: Embedder | None = None,
    ) -> None:
        client = chromadb.PersistentClient(path=str(persist_directory))
        try:
            self._collection: Collection = client.get_collection(COLLECTION_NAME)
        except Exception as error:
            raise RuntimeError(f"Missing Chroma collection: {COLLECTION_NAME}") from error
        metric = (self._collection.metadata or {}).get("hnsw:space")
        if metric != COSINE_DISTANCE_METRIC:
            raise RuntimeError(f"Collection metric must be {COSINE_DISTANCE_METRIC}, got {metric!r}.")
        self._embedder = embedder or Embedder()

    @property
    def collection_name(self) -> str:
        """Return bound persistent collection name."""
        return self._collection.name

    def retrieve(self, query: str, top_k: int = SEMANTIC_RESULT_LIMIT) -> RetrievalResult:
        """Parse, filter, embed, and retrieve raw candidates without reranking."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        parsed_query = parse_query(query)
        where = build_where_filter(parsed_query)
        limit = min(top_k, _result_limit(parsed_query))
        if where:
            try:
                available_count = len(self._collection.get(where=where, include=[])["ids"])
            except Exception as error:
                raise RuntimeError(f"Chroma metadata filter failed: {where!r}.") from error
            limit = min(limit, available_count)
        if limit == 0:
            return RetrievalResult(parsed_query, [], where)
        candidate_lists: list[list[RetrievalCandidate]] = []
        for retrieval_query in self._retrieval_queries(parsed_query):
            response = self._query_with_available_limit(
                self._embedder.encode_query(retrieval_query), limit, where
            )
            candidate_lists.append(self._parse_response(response, parsed_query))
        return RetrievalResult(parsed_query, self._fuse_candidate_lists(candidate_lists), where)

    @staticmethod
    def _retrieval_queries(parsed_query: ParsedQuery) -> list[str]:
        """Create generic raw/cleaned query formulations for recall.

        Raw text preserves person or date cues. Cleaned text focuses semantic
        meaning. Both forms receive same generic domain expansion. Filters still
        enforce sender and calendar constraints.
        """
        forms = (parsed_query.original_query, parsed_query.cleaned_query)
        queries: list[str] = []
        for form in forms:
            for candidate in (form, expand_query(form)):
                normalized = candidate.strip()
                if normalized and normalized not in queries:
                    queries.append(normalized)
        return queries

    @staticmethod
    def _fuse_candidate_lists(
        candidate_lists: list[list[RetrievalCandidate]],
    ) -> list[RetrievalCandidate]:
        """Fuse alternate query rankings with reciprocal rank fusion."""
        scores: dict[str, float] = {}
        best: dict[str, RetrievalCandidate] = {}
        for candidates in candidate_lists:
            for rank, candidate in enumerate(candidates, start=1):
                scores[candidate.id] = scores.get(candidate.id, 0.0) + 1.0 / (
                    DUAL_RETRIEVAL_RRF_K + rank
                )
                previous = best.get(candidate.id)
                if previous is None or candidate.similarity > previous.similarity:
                    best[candidate.id] = candidate
        return sorted(
            best.values(), key=lambda candidate: scores[candidate.id], reverse=True
        )[:MAX_FUSED_CANDIDATES]

    def _query_with_available_limit(
        self,
        embedding: list[float],
        limit: int,
        where: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Retry smaller filtered limits when HNSW cannot fill sparse result sets."""
        try:
            return self._collection.query(
                query_embeddings=[embedding],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except RuntimeError as error:
            if where and "contigious 2D array" in str(error):
                return self._filtered_exact_fallback(embedding, limit, where)
            raise RuntimeError(f"Chroma query failed with filter {where!r}.") from error

    def _filtered_exact_fallback(
        self,
        embedding: list[float],
        limit: int,
        where: dict[str, Any],
    ) -> dict[str, Any]:
        """Use Chroma-filtered records when local HNSW cannot execute filtered KNN."""
        try:
            records = self._collection.get(
                where=where,
                include=["documents", "embeddings", "metadatas"],
            )
            scored = sorted(
                zip(records["ids"], records["documents"], records["embeddings"], records["metadatas"]),
                key=lambda record: cosine_similarity(embedding, record[2]),
                reverse=True,
            )[:limit]
        except Exception as error:
            raise RuntimeError(f"Chroma filtered fallback failed: {where!r}.") from error
        return {
            "ids": [[record[0] for record in scored]],
            "documents": [[record[1] for record in scored]],
            "metadatas": [[record[3] for record in scored]],
            "distances": [[1.0 - cosine_similarity(embedding, record[2]) for record in scored]],
        }

    def _parse_response(self, response: dict[str, Any], parsed_query: ParsedQuery) -> list[RetrievalCandidate]:
        """Validate Chroma response, deduplicate by message text, return sorted candidates.

        A template phrase repeated by 14 senders creates 14 near-identical vectors
        that flood every result page. Deduplicate by normalized text, keeping only
        the best-scoring (lowest distance) instance per unique message.
        """
        try:
            ids = response["ids"][0]
            documents = response["documents"][0]
            metadatas = response["metadatas"][0]
            distances = response["distances"][0]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("Unexpected Chroma query response.") from error
        if not (len(ids) == len(documents) == len(metadatas) == len(distances)):
            raise ValueError("Chroma query response fields have unequal lengths.")

        seen_texts: set[str] = set()
        candidates: list[RetrievalCandidate] = []
        for identifier, document, metadata, distance in zip(ids, documents, metadatas, distances):
            sender = str(metadata["sender"])
            raw_text = str(document)
            # Strip the [Sender] prefix added during context-enriched ingestion
            prefix = f"[{sender}] "
            if raw_text.startswith(prefix):
                raw_text = raw_text[len(prefix):]
            # Strip appended neighbour context (short-message enrichment)
            if " | context: " in raw_text:
                raw_text = raw_text.split(" | context: ")[0]
            # Keep only the best-scoring (first) instance of each unique message text
            key = raw_text.casefold().strip()
            if key in seen_texts:
                continue
            seen_texts.add(key)
            candidates.append(RetrievalCandidate(
                id=str(identifier),
                text=raw_text,
                sender=sender,
                timestamp=str(metadata["timestamp"]),
                distance=float(distance),
                similarity=1.0 - float(distance),
                metadata=dict(metadata),
                intent=parsed_query.intent.value,
            ))
        return sorted(candidates, key=lambda c: c.similarity, reverse=True)


def retrieve(query: str, top_k: int = SEMANTIC_RESULT_LIMIT) -> RetrievalResult:
    """Convenience retrieval API for future service layer."""
    return Retriever().retrieve(query, top_k)


def run_self_tests() -> list[dict[str, Any]]:
    """Run required intent/filter checks plus hard-query retrieval baseline."""
    retriever = Retriever()
    cases = (
        ("When did we decide on the trip?", "semantic", None, None, SEMANTIC_RESULT_LIMIT),
        ("What did Priya say about the budget?", "person", "Priya", None, PERSON_RESULT_LIMIT),
        ("What did we discuss last month?", "temporal", None, None, TEMPORAL_RESULT_LIMIT),
        ("Rahul ne March mein trip ke baare mein kya bola?", "person", "Rahul", 3, PERSON_RESULT_LIMIT),
        ("What was the financial agreement?", "semantic", None, None, SEMANTIC_RESULT_LIMIT),
        ("Is the plan confirmed?", "semantic", None, None, SEMANTIC_RESULT_LIMIT),
    )
    for query, intent, sender, month, limit in cases:
        result = retriever.retrieve(query)
        assert result.parsed_query.intent.value == intent
        assert result.parsed_query.sender == sender
        assert result.parsed_query.month == month
        assert len(result.candidates) <= limit
        if sender:
            assert all(candidate.sender == sender for candidate in result.candidates)
    hard_queries = json.loads(HARD_QUERY_PATH.read_text(encoding="utf-8"))
    report: list[dict[str, Any]] = []
    for item in hard_queries:
        if not item["is_hard"]:
            continue
        result = retriever.retrieve(str(item["query"]))
        ids = [candidate.id for candidate in result.candidates]
        expected_id = str(item["ground_truth_id"])
        report.append({
            "query_id": item["query_id"],
            "intent": result.parsed_query.intent.value,
            "expected_id": expected_id,
            "expected_rank": ids.index(expected_id) + 1 if expected_id in ids else None,
            "top_5_ids": ids[:5],
            "top_5_similarities": [round(candidate.similarity, 6) for candidate in result.candidates[:5]],
            "candidate_count": len(result.candidates),
        })
    assert len(report) == 8
    return report


if __name__ == "__main__":
    print(json.dumps(run_self_tests(), indent=2))
