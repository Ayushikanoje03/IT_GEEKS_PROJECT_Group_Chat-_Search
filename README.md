# IT_GEEKS_PROJECT_Group_Chat-_Search

Semantic search over a fictional Hinglish (Hindi-English code-mixed) group chat —
find the message that actually answers a question, not just the one with
matching keywords.

The project lives in [`group-chat-search/`](group-chat-search/). See
**[group-chat-search/README.md](group-chat-search/README.md)** for the full
overview: architecture, tech stack, setup & run instructions, dataset,
evaluation method and results, and project structure.

## Quick start

```bash
cd group-chat-search
pip install -r requirements.txt
python data/generate_corpus.py
python backend/ingestion/ingest.py
./run.sh                      # FastAPI on http://127.0.0.1:8000
streamlit run frontend/app.py # Streamlit UI on http://127.0.0.1:8501
```
