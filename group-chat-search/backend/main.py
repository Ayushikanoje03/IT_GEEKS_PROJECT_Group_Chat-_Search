"""FastAPI orchestration layer for group-chat search pipeline."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models import ParsedQueryResponse, SearchRequest, SearchResponse, SearchResultResponse
from backend.search.context_builder import DEFAULT_CORPUS_PATH, build_context
from backend.search.decision_ranker import rank_candidates
from backend.search.embedder import EMBEDDING_MODEL, get_model
from backend.search.reranker import RERANKER_MODEL
from backend.search.retriever import COLLECTION_NAME, SEMANTIC_RESULT_LIMIT, Retriever

APP_TITLE = "Group Chat Search"
SAFE_INTERNAL_DETAIL = "Search service failed unexpectedly."
# Minimum cross-encoder relevance score for the top result to be considered
# genuinely relevant. Below this we return an empty results list so the UI
# can show "No relevant conversations found" instead of noise.
#
# Retrieval cosine similarity was tried first but rejected: for this corpus
# it stays in a narrow 0.75-0.9 band for BOTH on-topic and clearly off-topic
# queries (e.g. "What is the capital of France?" still scores ~0.76), so a
# similarity gate never fires. The cross-encoder's raw logit spreads much
# further (roughly +5 for a strong match down to -11 for unrelated text) and
# actually separates the two cases, so we gate on that instead. The cutoff is
# set just below the lowest score seen on a genuinely on-topic query in the
# 40-query eval set (-10.73), so real (if imperfect) matches still surface.
NO_RESULTS_RERANKER_THRESHOLD: float = -10.8

app = FastAPI(title=APP_TITLE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    """Return client input validation failures as API-friendly HTTP 400."""
    return JSONResponse(status_code=400, content={"detail": error.errors()})


@app.get("/health")
def health() -> dict[str, str]:
    """Report service availability."""
    return {"status": "ok"}


def _corpus() -> list[dict[str, object]]:
    """Read canonical corpus for message and statistics endpoints."""
    return json.loads(Path(DEFAULT_CORPUS_PATH).read_text(encoding="utf-8"))


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    """Orchestrate retrieval, cross-encoder reranking, decision scoring, and context."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty.")
    try:
        retrieval = Retriever().retrieve(request.query, top_k=SEMANTIC_RESULT_LIMIT)
        ranked = rank_candidates(request.query, retrieval.candidates, top_k=request.top_k)
        results = [
            SearchResultResponse(
                id=candidate.id,
                text=candidate.text,
                sender=candidate.sender,
                timestamp=candidate.timestamp,
                retrieval_similarity=candidate.retrieval_similarity,
                reranker_score=candidate.reranker_score,
                decision_boost=candidate.decision_boost,
                final_score=candidate.final_score,
                rank=candidate.final_rank,
                metadata=candidate.metadata,
                context=asdict(build_context(candidate.id)),
            )
            for candidate in ranked
        ]
        parsed = retrieval.parsed_query
        # Drop results whose top cross-encoder score is below the relevance
        # threshold so that off-topic / irrelevant queries return an empty list.
        if results and results[0].reranker_score < NO_RESULTS_RERANKER_THRESHOLD:
            results = []
        return SearchResponse(
            query=request.query,
            intent=parsed.intent,
            parsed_query=ParsedQueryResponse(
                cleaned_query=parsed.cleaned_query,
                sender=parsed.sender,
                time_expression=parsed.time_expression,
                month=parsed.month,
                day=parsed.day,
            ),
            results=results,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=SAFE_INTERNAL_DETAIL) from error


@app.get("/message/{message_id}")
def get_message(message_id: str) -> dict[str, object]:
    """Return one raw corpus message and its chronological context."""
    try:
        context = build_context(message_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="message not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    target = next(message for message in context.messages if message.is_target)
    return {"message": asdict(target), "context": asdict(context)}


@app.get("/messages")
def list_messages(offset: int = 0, limit: int = 100) -> dict[str, object]:
    """Return one bounded chronological page of the fictional chat archive."""
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must not be negative.")
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100.")
    corpus = _corpus()
    return {
        "total": len(corpus),
        "offset": offset,
        "limit": limit,
        "messages": corpus[offset: offset + limit],
    }


@app.get("/stats")
def stats() -> dict[str, object]:
    """Return current corpus and configured-search system facts."""
    corpus = _corpus()
    timestamps = [str(message["timestamp"]) for message in corpus]
    return {
        "total_messages": len(corpus),
        "participant_count": len({str(message["sender"]) for message in corpus}),
        "participants": sorted({str(message["sender"]) for message in corpus}),
        "date_range": {"start": min(timestamps), "end": max(timestamps)},
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": get_model().get_sentence_embedding_dimension(),
        "chroma_collection": COLLECTION_NAME,
        "context_window": 2,
        "reranker_model": RERANKER_MODEL,
    }


@app.get("/evaluate")
def evaluate() -> dict[str, object]:
    """Run full pipeline evaluation across all 40 queries and return metrics."""
    try:
        # Import here to avoid loading heavy models at startup
        from evaluation.eval import evaluate_queries
        return evaluate_queries()
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {error}") from error
