"""
API for the Traditional Knowledge Repository (Project UG_COSEAT_11).

Connects the ingestion pipeline's HITL queue to the review frontend, and
handles the approve step that moves a record into the repository.

Stores (all under AIOutput/):
  pending/   one JSON array per source file, written by Models/ingest_pipeline.py
  approved/  one JSON per approved record  <- this is the repository store for now
  rejected/  one JSON per rejected record

A record is "waiting for review" if it is in a pending file and has NOT yet been
approved or rejected. We never mutate the pipeline's pending files; decisions are
recorded by writing to approved/ or rejected/. That keeps the raw ingest output
intact and makes every decision auditable.

Run:
  pip install fastapi uvicorn
  uvicorn API.app:app --reload        # from the repo root
  then open http://127.0.0.1:8000/
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
PENDING_DIR = REPO_ROOT / "AIOutput" / "pending"
APPROVED_DIR = REPO_ROOT / "AIOutput" / "approved"
REJECTED_DIR = REPO_ROOT / "AIOutput" / "rejected"
FRONTEND_DIR = REPO_ROOT / "FrontEnd"

for d in (PENDING_DIR, APPROVED_DIR, REJECTED_DIR):
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Traditional Knowledge Repository API", version="0.1.0")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _decided_ids() -> set[str]:
    ids = set()
    for d in (APPROVED_DIR, REJECTED_DIR):
        for f in d.glob("*.json"):
            ids.add(f.stem)
    return ids


def _all_pending_records() -> dict[str, dict]:
    """Every record from the pipeline output, keyed by id."""
    records = {}
    for f in sorted(PENDING_DIR.glob("*.json")):
        data = _read_json(f) or []
        for rec in data:
            records[rec["id"]] = rec
    return records


def _to_item(rec: dict) -> dict:
    """Map a pipeline record to the shape the review frontend uses."""
    src = rec.get("source", {}) or {}
    cite = src.get("title") or rec.get("source_file", "Unknown source")
    if src.get("author"):
        cite = f"{src['author']} - {cite}"
    return {
        "id": rec["id"],
        "title": src.get("title") or rec.get("source_file", "Untitled"),
        "summary": rec.get("summary", ""),
        "original_text": rec.get("original_text", ""),   # source of truth for the reviewer
        "status": rec.get("status", "pending"),
        # relevance_score is a review signal (how on-topic), not AI answer confidence
        "confidence": rec.get("relevance_score", 0),
        "access": rec.get("access", "community"),
        "source": cite,
        "source_meta": src,
        "source_file": rec.get("source_file"),
        "chunk_index": rec.get("chunk_index"),
        "summary_method": rec.get("summary_method"),
    }


# ---------------------------------------------------------------------------
# request models
# ---------------------------------------------------------------------------
class ApproveBody(BaseModel):
    reviewed_by: str
    access: str = "community"          # public | community | restricted | sacred
    summary: str | None = None         # reviewer may correct the summary
    original_text: str | None = None   # reviewer may correct the source text


class RejectBody(BaseModel):
    reviewed_by: str
    reason: str | None = None


class SubmitBody(BaseModel):
    title: str
    text: str
    access: str = "community"
    source: str = "Manual submission"


# ---------------------------------------------------------------------------
# endpoints  (the contract the frontend fetches)
# ---------------------------------------------------------------------------
@app.get("/api/pending")
def get_pending():
    decided = _decided_ids()
    items = [_to_item(r) for rid, r in _all_pending_records().items() if rid not in decided]
    # most on-topic first
    items.sort(key=lambda i: i["confidence"], reverse=True)
    return items


@app.get("/api/approved")
def get_approved():
    items = []
    for f in sorted(APPROVED_DIR.glob("*.json")):
        rec = _read_json(f)
        if rec:
            items.append(_to_item(rec))
    return items


@app.get("/api/stats")
def get_stats():
    decided = _decided_ids()
    pending = [rid for rid in _all_pending_records() if rid not in decided]
    return {
        "pending": len(pending),
        "approved": len(list(APPROVED_DIR.glob("*.json"))),
        "rejected": len(list(REJECTED_DIR.glob("*.json"))),
    }


@app.post("/api/items/{item_id}/approve")
def approve(item_id: str, body: ApproveBody):
    rec = _all_pending_records().get(item_id)
    if rec is None:
        raise HTTPException(404, "item not found in pending queue")
    rec = dict(rec)
    if body.summary is not None:
        rec["summary"] = body.summary
    if body.original_text is not None:
        rec["original_text"] = body.original_text
    rec["access"] = body.access
    rec["status"] = "approved"
    rec["reviewed_by"] = body.reviewed_by
    rec["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    (APPROVED_DIR / f"{item_id}.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    # if it had been rejected before, clear that
    (REJECTED_DIR / f"{item_id}.json").unlink(missing_ok=True)
    return {"ok": True, "status": "approved", "id": item_id}


@app.post("/api/submit")
def submit(body: SubmitBody):
    """Manual submission (e.g. an elder recording). Goes to the same HITL queue."""
    import uuid
    rec = {
        "id": str(uuid.uuid4()),
        "source": {"title": body.title, "author": "", "year": "", "url": "",
                   "note": body.source},
        "source_file": "manual",
        "chunk_index": 0,
        "original_text": body.text,
        "summary": body.text,              # reviewer summarises/verifies in the queue
        "summary_method": "manual",
        "relevance_score": 1.0,
        "status": "pending",
        "access": body.access,
        "reviewed_by": None,
        "reviewed_at": None,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    (PENDING_DIR / f"manual_{rec['id']}.json").write_text(
        json.dumps([rec], indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "id": rec["id"]}


@app.post("/api/items/{item_id}/reject")
def reject(item_id: str, body: RejectBody):
    rec = _all_pending_records().get(item_id)
    if rec is None:
        raise HTTPException(404, "item not found in pending queue")
    rec = dict(rec)
    rec["status"] = "rejected"
    rec["reviewed_by"] = body.reviewed_by
    rec["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    rec["reject_reason"] = body.reason
    (REJECTED_DIR / f"{item_id}.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    (APPROVED_DIR / f"{item_id}.json").unlink(missing_ok=True)
    return {"ok": True, "status": "rejected", "id": item_id}


@app.get("/api/ask")
def ask(q: str, access: str = "community"):
    """Answer a question from approved records only, with citations, or abstain.
    Generates nothing: returns verbatim source passages so it cannot hallucinate."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "retrieval", str(REPO_ROOT / "Models" / "retrieval.py"))
    retrieval = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(retrieval)
    return retrieval.answer(q, viewer_access=access)


@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})


# serve the frontend from the same origin so no CORS setup is needed.
# mounted LAST so it does not shadow the /api and /health routes above.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR / "HTML"), html=True), name="frontend")
