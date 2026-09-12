"""Shared constants used across ingestion and search modules."""

from __future__ import annotations

from typing import Final

PARTICIPANTS: Final = ("Priya", "Rahul", "Sneha", "Arjun", "Kavya", "Dev", "Mehak", "Rohan")

DECISION_KEYWORDS: Final = (
    "fix", "pakka", "done", "confirmed", "final", "lock",
    "split", "bol dein", "locked", "finalize", "decided",
)

THREAD_START_INDEXES: Final = {
    "trip_decision": 830,
    "split_decision": 1520,
    "trip_confirmation": 2220,
}

NO_THREAD_ID: Final = ""
NO_THREAD_POSITION: Final = -1

# Key decision message IDs (planted deterministically in generate_corpus.py)
DECISION_MESSAGE_IDS: Final = {
    "trip_decision": "msg_0849",      # index 848 → msg_0849
    "split_decision": "msg_1554",     # index 1553 → msg_1554
    "trip_confirmation": "msg_2248",  # index 2247 → msg_2248
}
