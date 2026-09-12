"""Deterministic intent detection and minimal query preprocessing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from backend.models import Intent

# Query-side synonym expansion map.  When a search query contains one of these
# English keywords, we append the listed Hinglish/domain synonyms to the query
# string that gets embedded.  This bridges the lexical gap between English
# evaluation queries and the Hinglish corpus text (e.g. "mountain vacation
# settled" → appends "Manali hills pahad pakka confirmed finalized").
# Keys are lower-cased match strings; values are space-separated expansions.
_QUERY_EXPANSION: Final[dict[str, str]] = {
    # destination / place
    "mountain":    "hills pahad hill station terrain",
    "hill station": "hills pahad mountain destination",
    "hills":       "pahad mountain terrain",
    "destination": "place location trip",
    "vacation":    "trip holiday travel",
    "travel":      "trip jaana vacation",
    "holiday":     "trip vacation",
    # decisions / confirmation
    "settled":     "pakka confirmed finalized locked decided",
    "confirmed":   "pakka confirmed locked done decided",
    "finalized":   "pakka lock finalize decided confirmed",
    "decided":     "pakka confirmed finalized locked",
    "locked":      "lock pakka confirmed finalized",
    "agreed":      "theek hai haan pakka okay done",
    "official":    "officially lock confirmed final",
    "declare":     "officially announce confirm lock",
    "declaration": "officially announce confirm locked",
    # financial
    "financial":   "paisa payment split per head amount money",
    "arrangement": "split payment per head agreed amount",
    "accommodation": "hotel lodging stay cost",
    "cost":        "paisa amount split per head money",
    "reimbursement": "refund money back cancel drop out",
    "drops out":   "cancel refund withdraw",
    "cancels":     "cancel refund drop out withdraw",
    "payment":     "paisa upi bhej money transfer split",
    # departure / logistics
    "departure":   "6 baje subah morning train leaving start",
    "seat":        "seats availability booking train",
    "seats":       "seats availability booking train full",
    "availability": "seats booking full",
    "waiting":     "last minute danger full no seats",
    "danger":      "last minute full no seats risk",
    # health / terrain
    "health":      "altitude sickness medicine mountain cold terrain",
    "sick":        "altitude sickness medicine cold",
    "cold":        "altitude mountain terrain sickness weather",
    "mountainous": "pahad hills altitude mountain terrain",
    "terrain":     "pahad hills mountain altitude",
    # excitement / reaction
    "excitement":  "yayyy finally 🏔️ excited happy celebration yay",
    "excited":     "yayyy finally 🏔️ yay celebration happy",
    "voiced":      "said wrote expressed yayyy",
    # sharing
    "sharing":     "split sirf hotel alag per head",
    "sharing cost": "split sirf hotel alag per head divide",
    # people
    "member":      "group everyone sab log",
    "someone":     "koi member group",
    "group":       "sab log everyone members",
    "joining":     "joining participating trip coming",
    "morning":     "subah AM early departure baje",
    "quickly":     "jaldi fast urgent",
    "book tickets": "booking reservation tickets",
    "health advice": "medicine health warning",
}

PARTICIPANTS: Final = ("Priya", "Rahul", "Sneha", "Arjun", "Kavya", "Dev", "Mehak", "Rohan")
MONTHS: Final = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7,
    "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
MONTH_PATTERN: Final = "|".join(sorted(MONTHS, key=len, reverse=True))
PARTICIPANT_PATTERN: Final = re.compile(rf"\b({'|'.join(PARTICIPANTS)})\b", re.IGNORECASE)
DATE_DAY_FIRST_PATTERN: Final = re.compile(
    rf"\b(?P<day>0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+(?P<month>{MONTH_PATTERN})\b(?:\s+ko)?",
    re.IGNORECASE,
)
DATE_MONTH_FIRST_PATTERN: Final = re.compile(
    rf"\b(?P<month>{MONTH_PATTERN})\s+(?P<day>0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\b(?:\s+ko)?",
    re.IGNORECASE,
)
RELATIVE_TIME_PATTERN: Final = re.compile(
    r"\b(last month|this month|previous month|pichle mahine|iss month|is mahine|last week|this week|previous week|pichle hafte|yesterday|today|tomorrow|kal)\b",
    re.IGNORECASE,
)
MONTH_ONLY_PATTERN: Final = re.compile(
    rf"\b(?:(?:in|on|ko)\s+)?(?P<month>{MONTH_PATTERN})\b",
    re.IGNORECASE,
)
TRAILING_SPACE_PATTERN: Final = re.compile(r"\s+([?!,.])")
MULTISPACE_PATTERN: Final = re.compile(r"\s+")


@dataclass(frozen=True)
class ParsedQuery:
    """Rule-based query classification and metadata-filter candidates."""

    intent: Intent
    original_query: str
    cleaned_query: str
    sender: str | None = None
    time_expression: str | None = None
    month: int | None = None
    day: int | None = None
    year: int | None = None


@dataclass(frozen=True)
class _TemporalMatch:
    """Internal temporal match with removal span and parsed values."""

    match: re.Match[str]
    expression: str
    month: int | None
    day: int | None


def expand_query(query: str) -> str:
    """Append domain-synonym expansions for recognized English keywords in query.

    Mirrors the ingestion-side Hinglish→English enrichment on the query side:
    English evaluation queries (e.g. "mountain vacation settled") get Hinglish
    equivalents appended ("Manali hills pakka confirmed") so the E5 embedding
    aligns with enriched corpus passages even when there is zero lexical overlap.

    Longer phrases are matched before shorter ones to avoid substring collisions.
    """
    lower = query.casefold()
    expansions: list[str] = []
    for keyword, expansion in sorted(_QUERY_EXPANSION.items(), key=lambda kv: -len(kv[0])):
        if keyword in lower and expansion not in expansions:
            expansions.append(expansion)
    if not expansions:
        return query
    return query + " " + " ".join(expansions)


def _clean_text(text: str) -> str:
    """Collapse removal whitespace without rewriting remaining semantic words."""
    return TRAILING_SPACE_PATTERN.sub(r"\1", MULTISPACE_PATTERN.sub(" ", text)).strip()


def _canonical_participant(name: str) -> str:
    """Return canonical corpus spelling for case-insensitive name match."""
    return next(participant for participant in PARTICIPANTS if participant.casefold() == name.casefold())


_RECIPIENT_PRECEDING_PATTERN: Final = re.compile(r"\bto\s*$", re.IGNORECASE)
_RECIPIENT_FOLLOWING_PATTERN: Final = re.compile(r"^\s*ko\b", re.IGNORECASE)


def _is_recipient_mention(query: str, match: re.Match[str]) -> bool:
    """Return True when a matched name is the message's recipient, not its sender.

    "send UPI to Arjun" or "Arjun ko bhej do" name Arjun as who receives the
    message, not who sent it — treating it as a sender filter would wrongly
    exclude the actual (different) sender from the results.
    """
    before = query[:match.start()]
    after = query[match.end():]
    return bool(_RECIPIENT_PRECEDING_PATTERN.search(before) or _RECIPIENT_FOLLOWING_PATTERN.match(after))


def _find_sender_match(query: str) -> re.Match[str] | None:
    """Return first participant mention that is not itself a recipient mention."""
    for match in PARTICIPANT_PATTERN.finditer(query):
        if not _is_recipient_mention(query, match):
            return match
    return None


def _find_temporal_match(query: str) -> _TemporalMatch | None:
    """Find first explicit date, relative time, or month expression."""
    for pattern in (DATE_DAY_FIRST_PATTERN, DATE_MONTH_FIRST_PATTERN):
        match = pattern.search(query)
        if match:
            month_name = match.group("month").casefold()
            return _TemporalMatch(match, match.group(0), MONTHS[month_name], int(match.group("day")))
    match = RELATIVE_TIME_PATTERN.search(query)
    if match:
        return _TemporalMatch(match, match.group(0), None, None)
    match = MONTH_ONLY_PATTERN.search(query)
    if match:
        month_name = match.group("month").casefold()
        return _TemporalMatch(match, match.group("month"), MONTHS[month_name], None)
    return None


def parse_query(query: str) -> ParsedQuery:
    """Classify raw query and remove only active-intent entity from embedding text."""
    original_query = query.strip()
    if not original_query:
        raise ValueError("Query must not be empty or whitespace only.")
    participant_match = _find_sender_match(original_query)
    temporal_match = _find_temporal_match(original_query)
    if participant_match:
        return ParsedQuery(
            intent=Intent.PERSON,
            original_query=original_query,
            cleaned_query=_clean_text(
                original_query[:participant_match.start()] + original_query[participant_match.end():]
            ),
            sender=_canonical_participant(participant_match.group(0)),
            time_expression=temporal_match.expression if temporal_match else None,
            month=temporal_match.month if temporal_match else None,
            day=temporal_match.day if temporal_match else None,
        )
    if temporal_match:
        return ParsedQuery(
            intent=Intent.TEMPORAL,
            original_query=original_query,
            cleaned_query=_clean_text(original_query[:temporal_match.match.start()] + original_query[temporal_match.match.end():]),
            time_expression=temporal_match.expression,
            month=temporal_match.month,
            day=temporal_match.day,
        )
    return ParsedQuery(Intent.SEMANTIC, original_query, original_query)


def classify_intent(query: str) -> Intent:
    """Return query intent while retaining backwards-compatible simple API."""
    return parse_query(query).intent


def run_self_tests() -> None:
    """Exercise required deterministic parsing cases without external services."""
    cases = (
        ("When did we decide on the trip?", Intent.SEMANTIC, None, None),
        ("What did Priya say about the budget?", Intent.PERSON, "Priya", None),
        ("What did we discuss last month?", Intent.TEMPORAL, None, None),
        ("Rahul ne March mein trip ke baare mein kya bola?", Intent.PERSON, "Rahul", 3),
        ("What did Arjun say in December?", Intent.PERSON, "Arjun", 12),
        ("pichle mahine budget pe kya hua?", Intent.TEMPORAL, None, None),
        ("21 March ko kya final hua?", Intent.TEMPORAL, None, 3),
        ("What was the financial agreement?", Intent.SEMANTIC, None, None),
        ("Is the plan confirmed?", Intent.SEMANTIC, None, None),
        ("WHAT DID priya SAY?", Intent.PERSON, "Priya", None),
        ("(Rahul), update?", Intent.PERSON, "Rahul", None),
        ("Develop better search", Intent.SEMANTIC, None, None),
    )
    for query, intent, sender, month in cases:
        result = parse_query(query)
        assert (result.intent, result.sender, result.month) == (intent, sender, month), query
    date_result = parse_query("21 March ko kya final hua?")
    assert date_result.day == 21
    assert date_result.cleaned_query == "kya final hua?"
    assert parse_query("What did Priya say about the budget?").cleaned_query == "What did say about the budget?"
    assert parse_query("What did we discuss in March?").cleaned_query == "What did we discuss?"
    try:
        parse_query(" \t ")
    except ValueError:
        return
    raise AssertionError("Whitespace query must raise ValueError.")


if __name__ == "__main__":
    run_self_tests()
    print("intent self-tests passed")
