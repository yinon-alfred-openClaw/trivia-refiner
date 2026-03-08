#!/usr/bin/env python3
"""
Tracking utilities for trivia-refiner.
Maintains a log of which question IDs have been processed to avoid re-processing.
"""

import json
import os
from datetime import datetime, timezone

# Default path for the tracking file
TRACKING_FILE = os.path.expanduser(
    "~/.openclaw/workspace/memory/trivia-refiner-processed.json"
)


def load_processed_ids(path: str = TRACKING_FILE) -> dict:
    """
    Load the processed IDs tracking file.
    Creates an empty structure if the file doesn't exist.

    Returns a dict keyed by question ID (as string) for O(1) lookup:
    {
        "version": 1,
        "entries": {
            "42": {
                "id": 42,
                "refined_at": "2026-03-08T10:00:00+00:00",
                "status": "refined",        # "refined" | "failed" | "skipped"
                "attempt_count": 1,
                "notes": ""                 # optional free-text for failures
            }
        }
    }
    """
    if not os.path.exists(path):
        return {"version": 1, "entries": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Back-compat: if old format is a flat list, migrate it
        if isinstance(data, list):
            entries = {}
            for item in data:
                qid = str(item.get("id", ""))
                if qid:
                    entries[qid] = item
            data = {"version": 1, "entries": entries}
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️  Warning: could not read tracking file ({e}). Starting fresh.")
        return {"version": 1, "entries": {}}


def save_processed_ids(data: dict, path: str = TRACKING_FILE) -> None:
    """Persist the tracking data atomically (write to .tmp, then rename)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def add_processed_id(
    question_id: int,
    status: str = "refined",
    notes: str = "",
    path: str = TRACKING_FILE,
) -> None:
    """
    Record a question ID as processed.

    Args:
        question_id: The numeric ID of the question.
        status:      "refined" | "failed" | "skipped"
        notes:       Optional details (e.g. error message on failure).
        path:        Override the default tracking file path.
    """
    data = load_processed_ids(path)
    qid_str = str(question_id)
    existing = data["entries"].get(qid_str, {})

    data["entries"][qid_str] = {
        "id": question_id,
        "refined_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "attempt_count": existing.get("attempt_count", 0) + 1,
        "notes": notes,
    }
    save_processed_ids(data, path)


def is_processed(question_id: int, path: str = TRACKING_FILE) -> bool:
    """Return True if this question ID already has status='refined'."""
    data = load_processed_ids(path)
    entry = data["entries"].get(str(question_id))
    return entry is not None and entry.get("status") == "refined"


def get_processed_ids_set(path: str = TRACKING_FILE) -> set:
    """Return a set of question IDs that were successfully refined (fast bulk check)."""
    data = load_processed_ids(path)
    return {
        int(qid)
        for qid, entry in data["entries"].items()
        if entry.get("status") == "refined"
    }


def print_summary(path: str = TRACKING_FILE) -> None:
    """Print a short summary of the tracking file."""
    data = load_processed_ids(path)
    entries = data["entries"]
    refined = sum(1 for e in entries.values() if e.get("status") == "refined")
    failed  = sum(1 for e in entries.values() if e.get("status") == "failed")
    skipped = sum(1 for e in entries.values() if e.get("status") == "skipped")
    print(f"📊 Tracking summary  ({path})")
    print(f"   Total tracked : {len(entries)}")
    print(f"   ✅ Refined     : {refined}")
    print(f"   ❌ Failed      : {failed}")
    print(f"   ⏭️  Skipped     : {skipped}")


if __name__ == "__main__":
    print_summary()
