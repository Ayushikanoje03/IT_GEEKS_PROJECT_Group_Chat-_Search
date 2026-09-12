# Search a Group Chat Properly — Implementation Status

## Implemented

- Deterministic fictional Hinglish corpus generator: 4,200 messages, eight participants, October 2023 to March 2024.
- Ground-truth fixture with 40 evaluation queries, including eight zero-word-overlap hard queries.
- Rule-based semantic, person, and temporal query parsing.
- `intfloat/multilingual-e5-large` embeddings with internal E5 `query:` and `passage:` prefixes.
- Persistent ChromaDB ingestion with batch upserts and searchable message metadata.
- Chroma retrieval, sender/month metadata filtering, cross-encoder reranking, and conservative decision boost.
- Chronological message context: two messages before and after each returned result.
- FastAPI endpoints: `/health`, `/stats`, `/search`, `/message/{message_id}`, and `/evaluate`.
- Streamlit search UI, context display, system sidebar, and live evaluation tab.
- Evaluation CLI for final top-five results across all 40 fixture queries.

## Not Implemented

- User accounts, authentication, multi-chat uploads, and production hosting.
- Live chat import. Corpus is intentionally synthetic only.
- LLM-generated answers or summaries. Search returns source messages and context.
- Automatic retraining or external quality monitoring.
- A claim that every zero-overlap query is solved. Results must be read from the live evaluation.

## Current Validation Procedure

1. Rebuild the local Chroma index after `data/corpus.json` changes.
2. Start FastAPI and Streamlit.
3. Check `/health`, `/stats`, `/search`, and `/message/{message_id}`.
4. Run `python evaluation/eval.py` for measured accuracy.

## Latest Measured Results

Measured after rebuilding ChromaDB from the current corpus:

- Overall Hit@5: 23/40 (57.5%).
- Overall Hit@1: 20/40 (50.0%).
- Hard-8 Hit@5: 2/8 (25.0%).
- Easy-32 Hit@5: 21/32 (65.6%).
- Easy-to-hard Hit@5 gap: 40.6 percentage points.

## Accuracy Repair Applied

- Rebuilt the persistent ChromaDB collection because its stored documents were from an older corpus revision under the same message IDs.
- Search result text and its context now resolve to the same canonical corpus message.
- The hard-query score improved from the prior stale-index baseline, but zero-overlap search remains the main quality limitation.

## UI Theme

- Default UI is light blue.
- Dark mode remains available from the sidebar toggle.
