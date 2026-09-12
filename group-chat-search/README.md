# ConvoLens — Group Chat Search

Semantic search over a fictional Hinglish (Hindi-English code-mixed) WhatsApp-style
group chat, built to answer natural-language questions like *"When did we decide on
the trip?"* or *"What did Priya say about the budget?"* by finding the message that
actually answers the question — not just the one with matching keywords.

## Problem

Group chats bury decisions, confirmations, and plans under hundreds of casual
messages. Keyword search fails when the answer is phrased differently from the
question (Hinglish slang, emoji-only reactions, implicit references). This project
retrieves the right message using semantic embeddings, then re-ranks with a
cross-encoder for precision, and surfaces the surrounding conversation for context.

## Architecture & Tech Stack

```
Query → Intent Parsing → Chroma Retrieval → Cross-Encoder Rerank → RRF + Decision Ranking → Context Window → API/UI
```

| Layer | Technology |
|---|---|
| Embeddings | `intfloat/multilingual-e5-large` (via `sentence-transformers`) |
| Vector store | ChromaDB (persistent, cosine similarity) |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` (falls back from a multilingual model if not cached) |
| API | FastAPI |
| UI | Streamlit |
| Data | Deterministic synthetic corpus generator (`data/generate_corpus.py`) |

### Query intents

Queries are classified deterministically (`backend/search/intent.py`) into one of
three intents, which changes how retrieval is filtered:

- **SEMANTIC** — general topical questions ("What was the financial agreement?"). No hard filter; relies entirely on embedding + reranker relevance.
- **PERSON** — a participant name is mentioned as the message's sender (not merely referenced as a recipient — "send UPI *to* Arjun" is not treated as an Arjun-authored filter). Hard-filters candidates to that sender.
- **TEMPORAL** — a date, month, or relative time expression is detected ("last month", "21 March"). The date is folded into the query text for embedding but is **not** used as a hard filter, since a message can *discuss* a date without being *sent on* that date.

### Retrieval → reranking → ranking pipeline

1. **Retrieval** (`retriever.py`): both the raw and cleaned query forms are embedded and queried against ChromaDB independently, then fused with Reciprocal Rank Fusion (RRF) for recall. Near-duplicate messages (same text sent by multiple senders) are deduplicated, keeping the best-scoring instance.
2. **Cross-encoder reranking** (`reranker.py`): every retrieved candidate is scored jointly with the query by a cross-encoder, which is far more precise than cosine similarity but more expensive, hence the two-stage design.
3. **Decision ranking** (`decision_ranker.py`): retrieval rank and reranker rank are fused via RRF (weighted 20/80 toward the reranker). Two small, deliberately limited heuristics sit on top:
   - Short/emoji-only messages that rank near the top of retrieval (rank ≤ 3) but score poorly under the cross-encoder (which struggles on near-empty text) get their reranker rank clamped so they aren't buried.
   - A small tie-breaking bonus is added when the query explicitly asks about a decision/confirmation/financial event *and* the candidate contains a decision keyword — sized to only break close ties, not override the reranker's ordering.
4. **Context window**: each result is returned with the 2 chronological messages immediately before and after it (`context_builder.py`, `CONTEXT_WINDOW = 2`), so a short answer like "pakka" is shown with the conversation that gives it meaning.

### Relevance gate ("not found")

The `/search` endpoint drops all results when the top result's cross-encoder score
falls below a fixed threshold, returning an empty list so the UI shows "No relevant
conversations found" instead of unrelated messages for off-topic queries (raw
embedding cosine similarity was tried and rejected for this gate — it stays in a
narrow band regardless of topical relevance for this corpus and doesn't separate
on-topic from off-topic queries).

## Setup & Run

```bash
pip install -r requirements.txt

# 1. Generate the synthetic corpus (already committed as data/corpus.json)
python data/generate_corpus.py

# 2. Build the ChromaDB index from the corpus
python backend/ingestion/ingest.py

# 3. Start the API (http://127.0.0.1:8000)
./run.sh
# or: uvicorn backend.main:app --app-dir . --reload

# 4. Start the UI (http://127.0.0.1:8501), in a separate terminal
streamlit run frontend/app.py
```

Configure the UI's backend URL with `GROUP_CHAT_API_URL` (defaults to
`http://127.0.0.1:8000`).

### API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness check |
| `POST /search` | `{"query": str, "top_k": int}` → ranked results + context |
| `GET /message/{message_id}` | One message plus its chronological context |
| `GET /messages?offset=&limit=` | Paginated raw corpus browsing |
| `GET /stats` | Corpus size, participants, date range, model config |
| `GET /evaluate` | Runs the full 40-query evaluation and returns metrics |

## Dataset

`data/generate_corpus.py` deterministically generates **4,200 messages** across
**8 participants** (Priya, Rahul, Sneha, Arjun, Kavya, Dev, Mehak, Rohan) spanning
October 2023 to March 2024, simulating a trip-planning group chat: destination
debate, date-fixing, payment splits, and departure logistics, with Hinglish phrasing,
emoji reactions, and casual short replies. Three key decision points are planted at
fixed message IDs so evaluation queries have a stable ground truth.

`data/test_queries.json` holds **40 evaluation queries**, each with a ground-truth
message ID:

- **32 easy queries** — natural paraphrases with some lexical or semantic overlap with the target message.
- **8 hard queries** (`is_hard: true`) — deliberately constructed with **zero word overlap** with their ground-truth message, testing pure semantic understanding rather than lexical matching.

## Evaluation Method

`evaluation/eval.py` runs every one of the 40 fixture queries through the full
production pipeline (retrieval → reranking → decision ranking, identical to what
`/search` does) and checks whether the ground-truth message appears at rank 1
(Hit@1) or within the top 5 (Hit@5). Results are broken down as Overall, Hard-8, and
Easy-32, plus the Easy-minus-Hard accuracy gap. Run it with:

```bash
python -m evaluation.eval
```

or via `GET /evaluate` while the API is running.

### Actual measured results

```
Overall  Hit@5     : 30/40  (75.0%)
Overall  Hit@1     : 27/40  (67.5%)
Hard-8   Hit@5     : 6/8   (75.0%)
Hard-8   Hit@1     : 5/8   (62.5%)
Easy-32  Hit@5     : 24/32  (75.0%)
Easy-32  Hit@1     : 22/32  (68.8%)
Gap (Easy − Hard) @5: 0.0 pp
```

Measured by running `python -m evaluation.eval` against the current corpus and
ChromaDB index. Re-run it yourself to reproduce — do not take these numbers as
fixed if the corpus or index changes.

## Known Limitation

The synthetic corpus uses a limited number of message templates repeated with
variation (Faker-style generation), which produces near-duplicate phrasing across
many messages. This repetition compresses the embedding space for short, generic
replies ("done", "haan", "sure") and makes it harder for the retriever to isolate a
single correct answer among many similarly-worded candidates — this specifically
affects the harder, zero-lexical-overlap queries, which depend entirely on the
retriever separating semantically similar but distinct messages. This is a property
of the synthetic dataset, not the ranking pipeline, and would not be expected to the
same degree on organic chat data with naturally varied phrasing.

## Project Structure

```
group-chat-search/
├── backend/
│   ├── main.py                   # FastAPI app and endpoints
│   ├── models.py                 # Pydantic request/response models, Intent enum
│   ├── constants.py              # Decision keywords, thread metadata
│   ├── ingestion/ingest.py       # Corpus → ChromaDB embedding ingestion
│   └── search/
│       ├── intent.py             # Query intent parsing (semantic/person/temporal)
│       ├── embedder.py           # E5 embedding wrapper
│       ├── retriever.py          # ChromaDB retrieval + dual-query RRF fusion
│       ├── reranker.py           # Cross-encoder reranking
│       ├── decision_ranker.py    # Final RRF fusion + decision-boost ranking
│       └── context_builder.py    # ±2 chronological message context
├── data/
│   ├── generate_corpus.py        # Synthetic corpus generator
│   ├── corpus.json               # 4,200-message generated corpus
│   └── test_queries.json         # 40 evaluation queries (8 hard)
├── evaluation/eval.py            # Hit@1 / Hit@5 evaluation harness
├── frontend/app.py               # Streamlit chat-style search UI
├── run.sh                        # Starts the FastAPI backend
└── requirements.txt
```

## Example Queries

These are also the example chips shown in the UI — each is verified (via
`evaluation/eval.py`) to return the correct message at rank 1 against the
current corpus and index:

- "Which member voiced excitement after the hill station was locked in?"
- "What did Sneha advise about accommodation cost sharing?"
- "Who raised the concern about getting reimbursement if someone drops out?"
- "What did Priya say about 21-24 dates?"

## Demo / Submission Checklist

- [x] Backend starts cleanly (`./run.sh`) and `/health` responds
- [x] `/stats` reports 4,200 messages, 8 participants
- [x] `/search` returns ranked results with context for on-topic queries
- [x] `/search` returns an empty list ("No relevant conversations found") for off-topic queries
- [x] Streamlit UI launches and connects to the API
- [x] `python -m evaluation.eval` runs to completion and matches the numbers above
- [x] `.chroma/`, `__pycache__/`, and `.env` are git-ignored (rebuild the index locally with `python backend/ingestion/ingest.py`)
- [ ] Record a short demo covering: a semantic query, a person query, a temporal query, and an off-topic "not found" query
