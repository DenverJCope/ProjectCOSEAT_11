"""
Baseline ASR (speech-to-text) ingestion for the Traditional Knowledge Repository.

Audio in  ->  Whisper transcription  ->  the SAME downstream as text ingestion
(clean -> chunk -> relevance -> summarise)  ->  AIOutput/pending/  ->  HITL review

This reuses Models/ingest_pipeline.py so an audio transcript is treated exactly
like a text source after transcription: it still goes through the human review
and approval step before anything enters the repository.

Why review matters even more for audio:
  - ASR makes mistakes (names, places, language-specific terms especially).
  - Oral traditional knowledge may be culturally sensitive or restricted.
  So a transcript is never trusted automatically; a reviewer checks and corrects
  it in the queue, and sets the access level, before it is approved.

Transcriber: OpenAI Whisper (baseline). The "base" model is a reasonable default.
Needs ffmpeg installed on the system.

Usage:
  pip install openai-whisper          # plus ffmpeg on the system
  python Models/asr_ingest.py --input Data/audio/elder_recording.mp3
  python Models/asr_ingest.py --all                 # every audio file in Data/audio/
  python Models/asr_ingest.py --all --model small   # larger Whisper model
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# reuse the text pipeline (same folder, so a plain import works when run as a script)
import ingest_pipeline as ip

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = REPO_ROOT / "Data" / "audio"
PENDING_DIR = ip.PENDING_DIR

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".mp4", ".aac", ".wma"}

_WHISPER_MODEL = None


# ---------------------------------------------------------------------------
# Transcription (Whisper)
# ---------------------------------------------------------------------------
def transcribe(audio_path: Path, model_size: str = "base") -> dict:
    """Transcribe an audio file with Whisper. Returns text + segments + language."""
    global _WHISPER_MODEL
    try:
        import whisper
    except ImportError:
        raise RuntimeError(
            "Whisper is not installed. Run: pip install openai-whisper "
            "(and install ffmpeg on your system)."
        )
    if _WHISPER_MODEL is None:
        print(f"  loading Whisper model '{model_size}' (first run downloads it)...")
        _WHISPER_MODEL = whisper.load_model(model_size)
    result = _WHISPER_MODEL.transcribe(str(audio_path))
    return {
        "text": result.get("text", "").strip(),
        "language": result.get("language", ""),
        "segments": [
            {"start": round(s.get("start", 0), 2),
             "end": round(s.get("end", 0), 2),
             "text": s.get("text", "").strip()}
            for s in result.get("segments", [])
        ],
    }


# ---------------------------------------------------------------------------
# Build pending records from a transcript (mirrors ingest_pipeline.process_file,
# kept separate so it can be tested without audio or Whisper)
# ---------------------------------------------------------------------------
def build_records(text: str, source_file: str, meta: dict,
                  language: str = "", segments: list | None = None) -> list[dict]:
    text = ip.clean_text(text)
    if not text:
        return []
    chunks = ip.chunk_text(text)
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for i, chunk in enumerate(chunks):
        score = ip.relevance_score(chunk, ip.SCOPE_KEYWORDS)
        status = "pending" if score >= ip.RELEVANCE_THRESHOLD else "needs_review"
        records.append({
            "id": str(uuid.uuid4()),
            "source": meta,
            "source_file": source_file,
            "source_type": "audio",                     # marks this as an ASR transcript
            "language": language,
            "chunk_index": i,
            "original_text": chunk,                     # the transcript text, source of truth
            "summary": ip.extractive_summary(chunk),
            "summary_method": "extractive",
            "transcribed_by": "whisper",
            "needs_transcript_check": True,             # reviewer must verify ASR output
            "relevance_score": round(score, 3),
            "status": status,
            "access": "restricted",                     # audio defaults to restricted until a reviewer decides
            "reviewed_by": None,
            "reviewed_at": None,
            "ingested_at": now,
        })
    # keep the raw transcript + timestamps alongside, for the reviewer / future use
    if segments and records:
        records[0]["segments"] = segments
    return records


def process_audio(audio_path: Path, model_size: str = "base") -> dict:
    print(f"- {audio_path.name}")
    tr = transcribe(audio_path, model_size)
    if not tr["text"]:
        print("    (no speech detected, skipped)")
        return {}
    meta = {"title": audio_path.stem, "author": "", "year": "", "url": "",
            "note": "audio transcript (ASR)"}
    records = build_records(tr["text"], audio_path.name, meta,
                            language=tr["language"], segments=tr["segments"])
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    out = PENDING_DIR / f"audio_{audio_path.stem}.json"
    out.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"    language: {tr['language'] or 'unknown'}  |  {len(records)} chunk(s)")
    print(f"    written: {out.relative_to(REPO_ROOT)}  (flagged for transcript check)")
    return {"file": audio_path.name, "chunks": len(records)}


def main():
    ap = argparse.ArgumentParser(description="Transcribe audio and add it to the HITL queue.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--input", help="a single audio file")
    g.add_argument("--all", action="store_true", help="every audio file in Data/audio/")
    ap.add_argument("--model", default="base",
                    help="Whisper model size: tiny, base, small, medium, large (default base)")
    args = ap.parse_args()

    if args.all:
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        targets = sorted(p for p in AUDIO_DIR.iterdir() if p.suffix.lower() in AUDIO_EXTS)
        if not targets:
            print(f"No audio files found in {AUDIO_DIR}")
            return
    else:
        p = Path(args.input)
        if not p.is_absolute():
            p = REPO_ROOT / p
        targets = [p]

    print(f"Transcribing {len(targets)} file(s) with Whisper '{args.model}'.\n")
    done = [process_audio(t, args.model) for t in targets]
    done = [d for d in done if d]
    print(f"\nDone. {len(done)} file(s) transcribed into AIOutput/pending/ for review.")


if __name__ == "__main__":
    main()
