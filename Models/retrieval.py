"""
Retrieval over APPROVED records only, for the Traditional Knowledge Repository.

Design goal: no wrong knowledge.
  - Answers are drawn ONLY from approved records (the repository store).
  - The answer is EXTRACTIVE: it returns the real source passages with citations.
    Nothing is generated, so nothing can be hallucinated.
  - If no approved record is relevant enough, the system ABSTAINS ("not enough
    information") rather than guessing. Silence is preferred over a wrong answer.
  - Access control: sacred items are never returned here; a viewer only sees
    items at or below their access level.

Retrieval is TF-IDF cosine similarity (lexical). It works offline and is a
sensible Phase 1 choice. To move to semantic retrieval later, swap build_index
and _vectorise for sentence-transformer embeddings + FAISS; the rest is unchanged.
"""

import json
import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

REPO_ROOT = Path(__file__).resolve().parent.parent
APPROVED_DIR = REPO_ROOT / "AIOutput" / "approved"

# viewer access hierarchy; a viewer sees items at or below their own level.
# "sacred" is intentionally absent: sacred items are never served through ask().
ACCESS_RANK = {"public": 0, "community": 1, "restricted": 2}

SIM_THRESHOLD = 0.08   # below this, abstain. Tune on real data.
TOP_K = 3


def load_approved() -> list[dict]:
    records = []
    for f in sorted(APPROVED_DIR.glob("*.json")):
        try:
            records.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return records


def _visible(rec: dict, viewer_access: str) -> bool:
    access = rec.get("access", "community")
    if access == "sacred":
        return False                      # never served through retrieval
    viewer_rank = ACCESS_RANK.get(viewer_access, 1)
    return ACCESS_RANK.get(access, 1) <= viewer_rank


def _citation(rec: dict) -> str:
    src = rec.get("source", {}) or {}
    bits = []
    if src.get("author"):
        bits.append(src["author"])
    if src.get("title"):
        bits.append(src["title"])
    if src.get("year"):
        bits.append(f"({src['year']})")
    cite = ", ".join(bits) if bits else rec.get("source_file", "Unknown source")
    if src.get("url"):
        cite += f". {src['url']}"
    return cite


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _best_snippet(query: str, passage: str, vectoriser: TfidfVectorizer) -> str:
    """Return the sentence(s) in the passage closest to the query (extractive)."""
    sents = _sentences(passage)
    if len(sents) <= 2:
        return passage.strip()
    try:
        mat = vectoriser.transform(sents)
        qv = vectoriser.transform([query])
        sims = cosine_similarity(qv, mat)[0]
        top = sims.argsort()[::-1][:2]
        return " ".join(sents[i] for i in sorted(top))
    except Exception:
        return sents[0]


def answer(query: str, viewer_access: str = "community",
           k: int = TOP_K, threshold: float = SIM_THRESHOLD) -> dict:
    """Answer a query from approved records only, with citations, or abstain."""
    query = (query or "").strip()
    if not query:
        return {"query": query, "abstained": True,
                "reason": "empty query", "passages": []}

    records = [r for r in load_approved() if _visible(r, viewer_access)]
    if not records:
        return {"query": query, "abstained": True,
                "reason": "no approved knowledge available yet", "passages": []}

    texts = [r.get("original_text", "") for r in records]
    vectoriser = TfidfVectorizer(stop_words="english")
    matrix = vectoriser.fit_transform(texts)
    qv = vectoriser.transform([query])
    sims = cosine_similarity(qv, matrix)[0]

    order = np.argsort(sims)[::-1]
    hits = [(i, float(sims[i])) for i in order if sims[i] >= threshold][:k]

    if not hits:
        # the core "no wrong knowledge" behaviour: say nothing rather than guess
        return {"query": query, "abstained": True,
                "reason": "no approved source is relevant enough to answer safely",
                "passages": []}

    passages = []
    for i, score in hits:
        rec = records[i]
        passages.append({
            "snippet": _best_snippet(query, rec.get("original_text", ""), vectoriser),
            "source_text": rec.get("original_text", ""),   # full passage, verbatim
            "citation": _citation(rec),
            "access": rec.get("access", "community"),
            "score": round(score, 3),
            "id": rec.get("id"),
        })

    return {"query": query, "abstained": False, "passages": passages}


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "what is traditional knowledge"
    res = answer(q)
    if res["abstained"]:
        print(f"ABSTAIN: {res['reason']}")
    else:
        for p in res["passages"]:
            print(f"[{p['score']}] {p['snippet']}")
            print(f"    source: {p['citation']}\n")
