"""Shared API and search data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Intent(str, Enum):
    """Supported search query intent."""

    SEMANTIC = "semantic"
    PERSON = "person"
    TEMPORAL = "temporal"


class ChatMessage(BaseModel):
    """Validated corpus message used by ingestion."""

    id: str
    sender: str
    timestamp: datetime
    text: str
    is_forwarded: bool = False


class SearchRequest(BaseModel):
    """Validated request payload for search endpoint."""

    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=50)


class ParsedQueryResponse(BaseModel):
    """User-visible query understanding details."""

    cleaned_query: str
    sender: str | None
    time_expression: str | None
    month: int | None
    day: int | None


class SearchResultResponse(BaseModel):
    """Search response returned to frontend."""

    id: str
    text: str
    sender: str
    timestamp: str
    retrieval_similarity: float
    reranker_score: float
    decision_boost: float
    final_score: float
    rank: int
    metadata: dict[str, Any]
    context: dict[str, Any]


class SearchResponse(BaseModel):
    """Structured full search response."""

    query: str
    intent: Intent
    parsed_query: ParsedQueryResponse
    results: list[SearchResultResponse]
