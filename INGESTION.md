# Ingestion + HITL review flow

Pipeline:  Data/  ->  ingest  ->  verify (relevance)  ->  summarise  ->  AIOutput/pending/  ->  HITL review  ->  AIOutput/approved/ (repository)

## 1. Ingest source files
Put PDFs in `Data/`. Optionally add source metadata in `Data/sources.json`:

```json
{ "paper.pdf": { "title": "...", "author": "...", "year": "2024", "url": "..." } }
```

Run the pipeline:

```bash
pip install -r requirements.txt
python Models/ingest_pipeline.py --all          # or --input Data/paper.pdf
```

This extracts text, cleans it, splits it into chunks, scores each chunk for
relevance (on-topic -> `pending`, off-topic -> `needs_review`), summarises it,
and writes records to `AIOutput/pending/`.

Summaries are EXTRACTIVE by default (real sentences only, no invented text).
`--abstractive` uses the transformers model but should be treated as a preview,
not as answerable content.

## 2. Review (Human-In-The-Loop)
Start the API (it also serves the review frontend):

```bash
uvicorn API.app:app --reload
# open http://127.0.0.1:8000/  ->  Review queue
```

A reviewer approves, edits, or rejects each item. The original source text is
kept as the source of truth and can be corrected before approval.

## 3. Repository
Approved records are written to `AIOutput/approved/` (the repository store for
now). Search and Browse read from there. Rejected items go to
`AIOutput/rejected/`. The raw pipeline output in `AIOutput/pending/` is never
mutated, so every decision is auditable.

## 4. Ask (retrieval)
`Models/retrieval.py` searches the approved records and answers a question using
only those records. It returns the matching source passages word for word, each
with its citation. If nothing approved is relevant enough, it abstains rather
than guessing. Sacred items are never returned, and a viewer only sees items at
or below their access level.

```bash
python Models/retrieval.py "who holds traditional knowledge"
# or via the API / Ask box on the site:
# GET /api/ask?q=...&access=community
```

Retrieval is TF-IDF cosine similarity (lexical, offline). To move to semantic
retrieval later, swap the vectoriser in retrieval.py for sentence-transformer
embeddings + FAISS; the abstain/citation logic stays the same.

## Next steps
- Swap the flat `approved/` store for a database and the TF-IDF index for
  semantic embeddings (sentence-transformers + FAISS) as the corpus grows.
- Add real reviewer accounts / elder sign-off instead of the name prompt.
