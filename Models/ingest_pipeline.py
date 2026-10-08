"""
Ingestion pipeline for the Traditional Knowledge Repository (Project UG_COSEAT_11).

Flow:  Data/ (source files)  ->  extract  ->  clean  ->  chunk
       ->  relevance filter  ->  summarise  ->  AIOutput/pending/ (HITL queue)

Only records a human approves later (status "approved") should move into the
repository. Nothing here writes to the repository directly: this stage produces
the pending queue for Human-In-The-Loop verification.

Design note on "no wrong knowledge":
  The original passage is kept as the source of truth and is what retrieval
  should cite. The summary is for size, preview and search only. The default
  summariser is EXTRACTIVE (it only ever picks real sentences from the source,
  so it cannot invent text). An abstractive summariser is available with
  --abstractive but should be treated as a preview, not as answerable content.

Usage:
  python Models/ingest_pipeline.py --input Data/paper.pdf
  python Models/ingest_pipeline.py --all                 # every PDF in Data/
  python Models/ingest_pipeline.py --all --abstractive   # use transformers model
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to the repo root, resolved from this file's location)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "Data"
PENDING_DIR = REPO_ROOT / "AIOutput" / "pending"
SOURCES_MANIFEST = DATA_DIR / "sources.json"

# ---------------------------------------------------------------------------
# Config (tune these as the project scope sharpens)
# ---------------------------------------------------------------------------
# Words that signal a chunk is on-topic for Phase 1. Broad on purpose: the
# relevance filter only sets borderline items aside for review, it does not
# delete anything.
SCOPE_KEYWORDS = [
    "traditional knowledge", "indigenous", "aboriginal", "torres strait",
    "first nations", "custodian", "elder", "cultural", "heritage",
    "oral", "community", "country", "data sovereignty", "repository",
    "language", "practice", "ecological", "medicinal", "ceremony",
]

TARGET_CHUNK_CHARS = 1200      # rough size of each chunk before summarising
MIN_CHUNK_CHARS = 200          # chunks smaller than this are merged forward
RELEVANCE_THRESHOLD = 0.15     # below this -> status "needs_review" not "pending"
SUMMARY_SENTENCES = 3          # extractive summary length


# ---------------------------------------------------------------------------
# 1 + 2. Extract and clean
# ---------------------------------------------------------------------------
def extract_text(pdf_path: Path) -> str:
    """Pull text out of a PDF. Uses pdfplumber, falls back to pypdf."""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_path))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! could not extract {pdf_path.name}: {exc}", file=sys.stderr)
            return ""


def clean_text(text: str) -> str:
    """Strip the common junk Denver flagged: tags, stray whitespace, page numbers."""
    text = re.sub(r"<[^>]+>", " ", text)                 # any stray HTML/XML tags
    text = re.sub(r"\n\s*\d+\s*\n", "\n", text)          # lone page numbers
    text = re.sub(r"[ \t]+", " ", text)                   # collapse spaces
    text = re.sub(r"\n{3,}", "\n\n", text)                # collapse blank lines
    return text.strip()


# ---------------------------------------------------------------------------
# 3. Chunk
# ---------------------------------------------------------------------------
def chunk_text(text: str) -> list[str]:
    """Split into paragraph-based chunks near TARGET_CHUNK_CHARS."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, buffer = [], ""
    for para in paragraphs:
        if len(buffer) + len(para) + 1 <= TARGET_CHUNK_CHARS:
            buffer = f"{buffer}\n{para}".strip()
        else:
            if buffer:
                chunks.append(buffer)
            # a single giant paragraph is hard-split on sentence boundaries
            if len(para) > TARGET_CHUNK_CHARS:
                chunks.extend(_split_long(para))
                buffer = ""
            else:
                buffer = para
    if buffer:
        chunks.append(buffer)

    # merge any tiny trailing chunk into the previous one
    merged = []
    for c in chunks:
        if merged and len(c) < MIN_CHUNK_CHARS:
            merged[-1] = f"{merged[-1]}\n{c}"
        else:
            merged.append(c)
    return merged


def _split_long(para: str) -> list[str]:
    sentences = _sentences(para)
    out, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) + 1 <= TARGET_CHUNK_CHARS:
            buf = f"{buf} {s}".strip()
        else:
            if buf:
                out.append(buf)
            buf = s
    if buf:
        out.append(buf)
    return out


def _sentences(text: str) -> list[str]:
    # light sentence splitter: end punctuation followed by a space + capital
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# 4a. Relevance filter ("verify what's useful")
# ---------------------------------------------------------------------------
def relevance_score(chunk: str, keywords: list[str]) -> float:
    """Fraction-based score: how keyword-dense the chunk is, capped at 1.0."""
    low = chunk.lower()
    hits = sum(low.count(k) for k in keywords)
    words = max(len(low.split()), 1)
    # normalise: ~1 keyword hit per 25 words -> score ~1.0
    return min(hits / (words / 25), 1.0)


# ---------------------------------------------------------------------------
# 4b. Summarise  (extractive default = safe; abstractive optional = preview)
# ---------------------------------------------------------------------------
def extractive_summary(chunk: str, n: int = SUMMARY_SENTENCES) -> str:
    """Pick the n highest-scoring real sentences. Never invents text."""
    sentences = _sentences(chunk)
    if len(sentences) <= n:
        return chunk.strip()

    # word-frequency scoring (classic extractive approach)
    words = re.findall(r"[a-z]{3,}", chunk.lower())
    stop = _STOPWORDS
    freq = {}
    for w in words:
        if w not in stop:
            freq[w] = freq.get(w, 0) + 1
    if not freq:
        return " ".join(sentences[:n])
    peak = max(freq.values())
    for w in freq:
        freq[w] /= peak

    scored = []
    for idx, s in enumerate(sentences):
        sw = re.findall(r"[a-z]{3,}", s.lower())
        score = sum(freq.get(w, 0) for w in sw) / max(len(sw), 1)
        scored.append((score, idx, s))
    top = sorted(scored, reverse=True)[:n]
    # return them in original reading order
    return " ".join(s for _, _, s in sorted(top, key=lambda t: t[1]))


_ABSTRACTIVE = None


def abstractive_summary(chunk: str) -> str:
    """Optional transformers summary. Treat output as a preview, not a source."""
    global _ABSTRACTIVE
    if _ABSTRACTIVE is None:
        from transformers import pipeline  # imported only if --abstractive used
        _ABSTRACTIVE = pipeline(task="summarization")
    words = len(chunk.split())
    out = _ABSTRACTIVE(
        chunk,
        max_length=min(120, max(30, words // 2)),
        min_length=20,
        do_sample=False,
    )
    return out[0]["summary_text"].strip()


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
def load_metadata(pdf_path: Path) -> dict:
    """Read source metadata from Data/sources.json if present, else infer."""
    meta = {"title": pdf_path.stem, "author": "", "year": "", "url": ""}
    if SOURCES_MANIFEST.exists():
        try:
            manifest = json.loads(SOURCES_MANIFEST.read_text(encoding="utf-8"))
            if pdf_path.name in manifest:
                meta.update(manifest[pdf_path.name])
        except Exception as exc:  # noqa: BLE001
            print(f"  ! could not read sources.json: {exc}", file=sys.stderr)
    return meta


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def process_file(pdf_path: Path, use_abstractive: bool = False) -> dict:
    print(f"- {pdf_path.name}")
    raw = extract_text(pdf_path)
    if not raw.strip():
        print("    (no extractable text, skipped)")
        return {}

    text = clean_text(raw)
    chunks = chunk_text(text)
    meta = load_metadata(pdf_path)
    now = datetime.now(timezone.utc).isoformat()

    records = []
    kept, flagged = 0, 0
    for i, chunk in enumerate(chunks):
        score = relevance_score(chunk, SCOPE_KEYWORDS)
        status = "pending" if score >= RELEVANCE_THRESHOLD else "needs_review"
        if status == "pending":
            kept += 1
        else:
            flagged += 1

        if use_abstractive:
            try:
                summary = abstractive_summary(chunk)
                method = "abstractive"
            except Exception as exc:  # noqa: BLE001
                print(f"    ! abstractive failed ({exc}); using extractive")
                summary, method = extractive_summary(chunk), "extractive"
        else:
            summary, method = extractive_summary(chunk), "extractive"

        records.append({
            "id": str(uuid.uuid4()),
            "source": meta,
            "source_file": pdf_path.name,
            "chunk_index": i,
            "original_text": chunk,          # source of truth, for retrieval + citation
            "summary": summary,              # size/preview/search only
            "summary_method": method,
            "relevance_score": round(score, 3),
            "status": status,                # pending | needs_review -> later approved/rejected
            "reviewed_by": None,
            "reviewed_at": None,
            "ingested_at": now,
        })

    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PENDING_DIR / f"{pdf_path.stem}.json"
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"    {len(records)} chunks  ->  {kept} pending, {flagged} needs_review")
    print(f"    written: {out_path.relative_to(REPO_ROOT)}")
    return {"file": pdf_path.name, "chunks": len(records), "pending": kept, "needs_review": flagged}


def main():
    ap = argparse.ArgumentParser(description="Ingest sources into the HITL pending queue.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--input", help="a single PDF under Data/")
    g.add_argument("--all", action="store_true", help="process every PDF in Data/")
    ap.add_argument("--abstractive", action="store_true",
                    help="use the transformers summariser (preview only; default is extractive)")
    args = ap.parse_args()

    if args.all:
        targets = sorted(DATA_DIR.glob("*.pdf"))
        if not targets:
            print(f"No PDFs found in {DATA_DIR}")
            return
    else:
        p = Path(args.input)
        if not p.is_absolute():
            p = REPO_ROOT / p
        targets = [p]

    print(f"Ingesting {len(targets)} file(s). Summariser: "
          f"{'abstractive (preview)' if args.abstractive else 'extractive (safe)'}\n")
    summary = [process_file(t, args.abstractive) for t in targets]
    summary = [s for s in summary if s]
    total_chunks = sum(s["chunks"] for s in summary)
    total_pending = sum(s["pending"] for s in summary)
    print(f"\nDone. {len(summary)} file(s), {total_chunks} chunks, "
          f"{total_pending} pending review in AIOutput/pending/.")


# small stopword set for the extractive summariser
_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
    "has", "have", "was", "were", "this", "that", "these", "those", "with",
    "from", "they", "their", "them", "its", "his", "her", "our", "out",
    "which", "who", "whom", "what", "when", "where", "will", "would", "been",
    "being", "into", "than", "then", "also", "such", "some", "more", "most",
    "other", "there", "here", "about", "within", "between", "over", "under",
}

if __name__ == "__main__":
    main()
