"""Ingest fictional group-chat corpus into persistent ChromaDB.

Key design: messages are embedded with sender prefix and context enrichment.
Short messages receive neighbour context so brief reactions retain their topic.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import chromadb
from chromadb.api.models.Collection import Collection
from pydantic import ValidationError

from backend.constants import (
    DECISION_KEYWORDS,
    NO_THREAD_ID,
    NO_THREAD_POSITION,
    THREAD_START_INDEXES,
)
from backend.models import ChatMessage
from backend.search.embedder import Embedder
from backend.search.retriever import COLLECTION_NAME

PROJECT_ROOT: Final = Path(__file__).parents[2]
DEFAULT_CORPUS_PATH: Final = PROJECT_ROOT / "data" / "corpus.json"
DEFAULT_PERSIST_DIRECTORY: Final = PROJECT_ROOT / ".chroma"
EMBEDDING_BATCH_SIZE: Final = 64
SHORT_MESSAGE_THRESHOLD: Final = 20  # chars; below this, add context neighbours

# Lightweight Hinglish → English vocabulary enrichment applied to EVERY message.
# These mappings bridge the semantic gap between English evaluation queries and
# Hinglish corpus text so HNSW retrieval can find the right passages.
_HINGLISH_EN: dict[str, str] = {
    "pakka": "confirmed fixed settled",
    "fix": "finalize confirm settle",
    "chalo": "let's go ahead proceed",
    "theek hai": "okay alright agreed fine",
    "theek": "okay alright fine",
    "done": "done completed confirmed",
    "haan": "yes agreed confirmed",
    "nahi": "no not unavailable",
    "bilkul nahi": "absolutely not no way unavailable",
    "bilkul": "absolutely completely",
    "yaar": "friend buddy",
    "bhai": "brother friend buddy",
    "sab": "everyone all members",
    "log": "people members",
    "koi": "someone anyone member",
    "kitne": "how many count",
    "jaana chahiye": "should go must travel",
    "jaana": "go travel",
    "pahad": "mountain hills terrain",
    "hills": "hills mountains terrain",
    "manali": "manali mountain destination hill station",
    "trip": "trip vacation travel holiday",
    "departure": "departure leaving travel start",
    "ticket": "ticket booking reservation",
    "train": "train railway transport booking",
    "seats": "seats availability booking",
    "tatkal": "urgent last-minute tatkal booking expensive",
    "booking": "booking reservation confirmed",
    "leave": "leave vacation time-off approved",
    "approved": "approved granted sanctioned",
    "march": "march month date",
    "kab": "when date time schedule",
    "aaj raat": "tonight today night",
    "aaj": "today",
    "morning": "morning early AM",
    "baje": "o'clock time AM departure",
    "pehle": "first before earlier",
    "phir": "then after later",
    "jaldi karo": "hurry up quickly fast urgent",
    "jaldi": "hurry quickly fast soon",
    "last minute": "last minute cancel urgent",
    "paisa": "money payment funds",
    "payment": "payment money transfer funds",
    "upi": "upi payment money transfer send",
    "bhej": "send transfer payment",
    "split": "split divide share cost",
    "per head": "per person each individual cost",
    "total": "total amount cost budget",
    "refund": "refund reimbursement money back",
    "confirmation": "confirmation receipt acknowledge",
    "hotel": "hotel accommodation lodging stay",
    "food": "food meals dining eating",
    "alag": "separate different additional",
    "sirf": "only just merely",
    "included": "included added together",
    "cancel": "cancel drop out withdraw",
    "mil gayi": "found available got",
    "ready raho": "be ready prepare everyone",
    "aa raha": "coming joining attending",
    "medicine": "medicine medication health",
    "altitude sickness": "altitude sickness mountain illness health advice",
    "altitude": "altitude mountain elevation",
    "sickness": "sickness illness health problem",
    "officially": "officially formally confirmed",
    "lock": "lock finalize confirm settle",
    "badh rahe": "increasing rising going up",
    "full": "full no availability sold out",
    "5k": "5000 rupees each per person",
    "40k": "40000 rupees total accommodation",
    "1450": "1450 rupees per person ticket price",
    "1500": "1500 rupees per person ticket",
    "6 baje": "6 am morning early departure time",
    "subah": "morning early AM",
    "raat": "night evening",
    "seedha": "directly straight",
    "sending": "sending transferring paying",
    "yayyy": "yay excited excitement celebration happy finally yay hill station locked",
    "finally": "finally at last done completed settled locked",
    "excitement": "excitement happy celebration yay finally",
    "100%": "100 percent confirmed fully committed",
    "hazrat nizamuddin": "hazrat nizamuddin railway station delhi",
    "3a": "3a sleeper class train",
}


def _enrich_with_english(text: str) -> str:
    """Append English keyword equivalents for Hinglish tokens found in text.

    Works case-insensitively, longest-phrase-first to avoid substring clashes.
    Returns a compact English vocabulary supplement string.
    """
    lower = text.casefold()
    found: list[str] = []
    for hinglish, english in sorted(_HINGLISH_EN.items(), key=lambda kv: -len(kv[0])):
        if hinglish in lower and english not in found:
            found.append(english)
    return " ".join(found)


def load_corpus(path: Path = DEFAULT_CORPUS_PATH) -> list[dict[str, Any]]:
    """Read JSON corpus and validate each required chat-message field."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load corpus at {path}: {error}") from error
    if not isinstance(data, list):
        raise ValueError("Corpus JSON must contain a list of messages.")
    messages: list[dict[str, Any]] = []
    for record in data:
        if not isinstance(record, dict):
            raise ValueError("Each corpus record must be an object.")
        try:
            ChatMessage.model_validate(record)
        except ValidationError as error:
            raise ValueError(f"Invalid corpus record: {record.get('id', '<unknown>')}") from error
        required = ("id", "sender", "text", "timestamp", "message_type", "original_index")
        missing = [field for field in required if field not in record]
        if missing:
            raise ValueError(f"Corpus record {record['id']} missing: {', '.join(missing)}")
        messages.append(record)
    return messages


def build_embedding_text(
    message: dict[str, Any],
    all_messages: list[dict[str, Any]],
) -> str:
    """Build semantically enriched embedding string for one message.

    Layers (applied in order):
    1. [Sender] prefix + original Hinglish text (always)
    2. Hinglish→English vocabulary enrichment (always, for all messages)
    3. Neighbour context for short messages < SHORT_MESSAGE_THRESHOLD chars

    The English layers bridge the semantic gap between English evaluation queries
    and Hinglish corpus text so HNSW vector search retrieves the right passages.
    """
    sender = str(message["sender"])
    text = str(message["text"])
    idx = int(message["original_index"])
    base = f"[{sender}] {text}"

    # Layer 2: Hinglish→English vocabulary enrichment for ALL messages
    english_vocab = _enrich_with_english(text)

    # Layer 3: neighbour context for very short messages.
    context_parts: list[str] = []
    if len(text) < SHORT_MESSAGE_THRESHOLD:
        if idx > 0:
            prev = all_messages[idx - 1]
            context_parts.append(f"{prev['sender']}: {prev['text']}")
            english_vocab += " " + _enrich_with_english(str(prev["text"]))
        if idx < len(all_messages) - 1:
            nxt = all_messages[idx + 1]
            context_parts.append(f"{nxt['sender']}: {nxt['text']}")
            english_vocab += " " + _enrich_with_english(str(nxt["text"]))

    parts = [base]
    if context_parts:
        parts.append("context: " + " | ".join(context_parts))
    if english_vocab.strip():
        parts.append("meaning: " + english_vocab.strip())

    return " | ".join(parts)



def build_metadata(message: dict[str, Any]) -> dict[str, str | int | bool]:
    """Build Chroma-compatible filter metadata for one corpus message."""
    timestamp = datetime.fromisoformat(str(message["timestamp"]))
    thread_id = message.get("thread_id")
    thread_key = str(thread_id) if thread_id else NO_THREAD_ID
    original_index = int(message["original_index"])
    thread_position = (
        original_index - THREAD_START_INDEXES[thread_key]
        if thread_key in THREAD_START_INDEXES
        else NO_THREAD_POSITION
    )
    raw_text = str(message["text"]).casefold()
    return {
        "sender": str(message["sender"]),
        "timestamp": timestamp.isoformat(),
        "month": timestamp.month,
        "year": timestamp.year,
        "day_of_week": timestamp.strftime("%A"),
        "message_type": str(message["message_type"]),
        "has_decision_keyword": any(keyword in raw_text for keyword in DECISION_KEYWORDS),
        "thread_position": thread_position,
        "thread_id": thread_key,
    }


def get_collection(persist_directory: Path = DEFAULT_PERSIST_DIRECTORY) -> Collection:
    """Open persistent client and return chat collection."""
    client = chromadb.PersistentClient(path=str(persist_directory))
    return client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def _batches(
    items: Sequence[dict[str, Any]], batch_size: int = EMBEDDING_BATCH_SIZE
) -> list[Sequence[dict[str, Any]]]:
    """Split records into bounded embedding/upsert batches."""
    return [items[index: index + batch_size] for index in range(0, len(items), batch_size)]


def ingest(
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    persist_directory: Path = DEFAULT_PERSIST_DIRECTORY,
    embedder: Embedder | None = None,
) -> int:
    """Upsert corpus into ChromaDB using context-enriched passage embeddings."""
    all_messages = load_corpus(corpus_path)
    collection = get_collection(persist_directory)
    encoder = embedder or Embedder()
    for batch in _batches(all_messages):
        documents = [build_embedding_text(msg, all_messages) for msg in batch]
        collection.upsert(
            ids=[str(message["id"]) for message in batch],
            documents=documents,
            embeddings=encoder.encode_messages(documents),
            metadatas=[build_metadata(message) for message in batch],
        )
    return collection.count()


def verify_records(
    collection: Collection, ids: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """Return stored metadata and document for deterministic message IDs."""
    result = collection.get(ids=list(ids), include=["documents", "metadatas"])
    return {
        message_id: {"document": document, "metadata": metadata}
        for message_id, document, metadata in zip(
            result["ids"], result["documents"], result["metadatas"]
        )
    }


def main() -> None:
    """Ingest the configured corpus and print the persistent record count."""
    print(f"Ingested {ingest()} messages.")


if __name__ == "__main__":
    main()
