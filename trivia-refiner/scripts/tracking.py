#!/usr/bin/env python3
"""Tracking module for processed trivia questions."""

import json
import os
from datetime import datetime

HE_TRACKING_FILE = os.path.expanduser("~/.openclaw/workspace/memory/trivia-refiner-processed.json")
EN_TRACKING_FILE = os.path.expanduser("~/.openclaw/workspace/memory/trivia-refiner-en-processed.json")


def get_tracking_file(tracking_lang="he"):
    return EN_TRACKING_FILE if tracking_lang == "en" else HE_TRACKING_FILE


def load_processed_data(tracking_lang="he"):
    """Load the tracking data from file."""
    tracking_file = get_tracking_file(tracking_lang)
    if not os.path.exists(tracking_file):
        return {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "version": "1",
            "processed": []
        }
    
    try:
        with open(tracking_file) as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Error loading tracking file: {e}. Starting fresh.")
        return {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "version": "1",
            "processed": []
        }


def save_processed_data(data, tracking_lang="he"):
    """Save tracking data to file."""
    data["last_updated"] = datetime.utcnow().isoformat() + "Z"
    tracking_file = get_tracking_file(tracking_lang)
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(tracking_file), exist_ok=True)
        
        with open(tracking_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving tracking file: {e}")
        return False

def get_processed_question_ids(tracking_lang="he"):
    """Return set of question IDs that have been successfully refined."""
    data = load_processed_data(tracking_lang)
    return {item["id"] for item in data.get("processed", []) if item.get("status") == "refined"}

def get_last_processed_id(tracking_lang="he"):
    """Return the highest question ID that has been processed (any status).
    Returns 0 if nothing has been processed yet, so fetching starts from ID 1.
    """
    data = load_processed_data(tracking_lang)
    ids = [item["id"] for item in data.get("processed", []) if isinstance(item.get("id"), int)]
    return max(ids) if ids else 0

def add_processed_id(question_id, status, tracking_lang="he", **metadata):
    """Record a question as processed."""
    data = load_processed_data(tracking_lang)
    
    entry = {
        "id": question_id,
        "refined_at": datetime.utcnow().isoformat() + "Z",
        "status": status,
        **metadata
    }
    
    data["processed"].append(entry)
    
    return save_processed_data(data, tracking_lang)

def has_been_refined(question_id, tracking_lang="he"):
    """Check if a question has already been successfully refined."""
    return question_id in get_processed_question_ids(tracking_lang)

def get_failed_questions(tracking_lang="he"):
    """Get list of questions that failed refinement."""
    data = load_processed_data(tracking_lang)
    return [item for item in data.get("processed", []) if item.get("status") == "failed"]

def get_stats(tracking_lang="he"):
    """Get overall processing statistics."""
    data = load_processed_data(tracking_lang)
    total = len(data.get("processed", []))
    refined = len([item for item in data["processed"] if item.get("status") == "refined"])
    failed = len([item for item in data["processed"] if item.get("status") == "failed"])
    
    return {
        "total_processed": total,
        "refined": refined,
        "failed": failed,
        "last_updated": data.get("last_updated")
    }

def get_last_edited_id(tracking_lang="he"):
    """Get the ID of the last question that was successfully refined.
    
    Returns the highest ID from all processed questions (refined or failed),
    so the next fetch starts from (last_edited_id + 1).
    
    Returns 0 if no questions have been processed yet (start from ID 1).
    """
    data = load_processed_data(tracking_lang)
    
    # Get all processed questions (both refined and failed)
    processed = data.get("processed", [])
    
    if not processed:
        return 0  # Start from ID 1 (1 + 0 = 1)
    
    # Return the highest ID that has been processed
    ids = [item["id"] for item in processed if isinstance(item.get("id"), int)]
    return max(ids) if ids else 0

def clear_tracking(tracking_lang="he"):
    """Clear all tracking data (use with caution!)."""
    tracking_file = get_tracking_file(tracking_lang)
    try:
        if os.path.exists(tracking_file):
            os.remove(tracking_file)
        print("✅ Tracking file cleared")
        return True
    except Exception as e:
        print(f"❌ Error clearing tracking file: {e}")
        return False
