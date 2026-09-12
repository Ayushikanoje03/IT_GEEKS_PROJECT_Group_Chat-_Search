"""Cached multilingual embedding service for Hinglish chat text."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Final, Sequence

# This project uses PyTorch through sentence-transformers. Avoid optional, broken
# TensorFlow plugin imports in environments where TensorFlow is installed.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_TORCH", "1")

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL: Final = "intfloat/multilingual-e5-large"
QUERY_PREFIX: Final = "query: "
PASSAGE_PREFIX: Final = "passage: "
EMBEDDING_VALIDATION_PAIRS: Final = (
    ("When did we finalize the vacation?", "toh chalo fix karte hain yaar, 21 March Manali pakka"),
    ("What was the financial agreement?", "theek hai bhai, 5k each split kar dete hain, done"),
    ("Is the plan confirmed?", "haan bhai pakka confirmed samjho"),
)


@lru_cache(maxsize=None)
def get_model(model_name: str = EMBEDDING_MODEL) -> SentenceTransformer:
    """Load each configured SentenceTransformer model once per process."""
    return SentenceTransformer(model_name)


class Embedder:
    """Encode unmodified Hinglish or code-mixed text for cosine retrieval."""

    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        self._model = get_model(model_name)

    def encode_query(self, query: str) -> list[float]:
        """Encode raw search query with E5 query prefix and unit normalization."""
        return self._model.encode(
            f"{QUERY_PREFIX}{query}",
            normalize_embeddings=True,
        ).tolist()

    def encode_messages(self, messages: Sequence[str]) -> list[list[float]]:
        """Encode raw chat messages with E5 passage prefix and unit normalization."""
        passages = [f"{PASSAGE_PREFIX}{message}" for message in messages]
        return self._model.encode(passages, normalize_embeddings=True).tolist()

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Backward-compatible batch encoding for ingestion callers."""
        return self.encode_messages(texts)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Calculate cosine score for already normalized embedding vectors."""
    if len(left) != len(right):
        raise ValueError("Embedding vectors must have same dimensionality.")
    return float(sum(left_value * right_value for left_value, right_value in zip(left, right)))


def validate_embedding_pairs(embedder: Embedder | None = None) -> list[float]:
    """Return actual cosine scores for documented semantic-validation pairs."""
    service = embedder or Embedder()
    return [
        cosine_similarity(service.encode_query(query), service.encode_messages([message])[0])
        for query, message in EMBEDDING_VALIDATION_PAIRS
    ]
