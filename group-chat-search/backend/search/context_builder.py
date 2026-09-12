"""Build chronological local chat context from corpus JSON records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from backend.constants import (
    DECISION_KEYWORDS,
    NO_THREAD_ID,
    NO_THREAD_POSITION,
    THREAD_START_INDEXES,
)

PROJECT_ROOT: Final = Path(__file__).parents[2]
DEFAULT_CORPUS_PATH: Final = PROJECT_ROOT / "data" / "corpus.json"
CONTEXT_WINDOW: Final = 2


@dataclass(frozen=True)
class ContextMessage:
    """One chronological corpus record enriched for result display."""

    id: str
    sender: str
    timestamp: str
    text: str
    message_type: str
    thread_id: str
    thread_position: int
    has_decision_keyword: bool
    is_target: bool


@dataclass(frozen=True)
class ContextResult:
    """Target position and surrounding chronological chat window."""

    target_id: str
    messages: list[ContextMessage]
    target_index: int
    context_start: int
    context_end: int


@lru_cache(maxsize=1)
def _load_corpus_cached(corpus_path: Path) -> list[dict[str, Any]]:
    """Load and cache corpus JSON — avoids re-reading 880 KB on every search result."""
    try:
        data = json.loads(corpus_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load corpus at {corpus_path}: {error}") from error
    if not isinstance(data, list):
        raise ValueError("Corpus JSON must contain a list of messages.")
    return data


def _to_context_message(message: dict[str, Any], is_target: bool) -> ContextMessage:
    """Preserve corpus message fields and derive display metadata consistently."""
    thread_id = str(message.get("thread_id") or NO_THREAD_ID)
    original_index = int(message["original_index"])
    thread_position = (
        original_index - THREAD_START_INDEXES[thread_id]
        if thread_id in THREAD_START_INDEXES
        else NO_THREAD_POSITION
    )
    text = str(message["text"])
    return ContextMessage(
        id=str(message["id"]),
        sender=str(message["sender"]),
        timestamp=str(message["timestamp"]),
        text=text,
        message_type=str(message["message_type"]),
        thread_id=thread_id,
        thread_position=thread_position,
        has_decision_keyword=any(keyword in text.casefold() for keyword in DECISION_KEYWORDS),
        is_target=is_target,
    )


def build_context(
    message_id: str,
    window: int = CONTEXT_WINDOW,
    corpus_path: Path = DEFAULT_CORPUS_PATH,
) -> ContextResult:
    """Return target plus up to `window` actual chronological neighbours each side."""
    if not isinstance(message_id, str) or not message_id.strip():
        raise ValueError("message_id must be a non-empty string.")
    if not isinstance(window, int) or isinstance(window, bool) or window < 0:
        raise ValueError("window must be a non-negative integer.")
    corpus = _load_corpus_cached(corpus_path)
    target_index = next(
        (index for index, item in enumerate(corpus) if item.get("id") == message_id),
        None,
    )
    if target_index is None:
        raise KeyError(f"Message ID not found: {message_id}")
    context_start = max(0, target_index - window)
    context_end = min(len(corpus) - 1, target_index + window)
    messages = [
        _to_context_message(message, is_target=index == target_index)
        for index, message in enumerate(
            corpus[context_start: context_end + 1], start=context_start
        )
    ]
    return ContextResult(message_id, messages, target_index, context_start, context_end)


def run_self_tests() -> None:
    """Validate planted targets and beginning/end corpus boundary behaviour."""
    for message_id in ("msg_0864", "msg_1554", "msg_2253"):
        context = build_context(message_id)
        target_positions = [
            index for index, message in enumerate(context.messages) if message.is_target
        ]
        assert target_positions == [2], message_id
        assert context.messages[2].id == message_id
        assert len(context.messages) == 5
        assert [message.id for message in context.messages] == sorted(
            message.id for message in context.messages
        )
    first = build_context("msg_0001")
    assert first.context_start == 0 and first.target_index == 0
    last = build_context("msg_4200")
    assert last.context_end == 4199 and last.target_index == 4199
    for invalid in ("", "  ", None):
        try:
            build_context(invalid)  # type: ignore[arg-type]
        except ValueError:
            continue
        raise AssertionError("Invalid message ID must raise ValueError.")
    for invalid_window in (-1, True):
        try:
            build_context("msg_0001", invalid_window)
        except ValueError:
            continue
        raise AssertionError("Invalid window must raise ValueError.")
    try:
        build_context("msg_9999")
    except KeyError:
        return
    raise AssertionError("Unknown message ID must raise KeyError.")


if __name__ == "__main__":
    run_self_tests()
    print("context builder self-tests passed")
