#!/usr/bin/env python3
"""Tracking module for processed trivia questions."""

import json
import os
from datetime import datetime

TRACKING_FILE = os.path.expanduser("~/.openclaw/workspace/memory/trivia-refiner-processed.json")

def load_processed_data():
    """Load the tracking data from file."""
    if not os.path.exists(TRACKING_FILE):
        return {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "version": "1",
            "processed": []
        }
    
    try:
        with open(TRACKING_FILE) as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Error loading tracking file: {e}. Starting fresh.")
        return {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "version": "1",
            "processed": []
        }

def save_processed_data(data):
    """Save tracking data to file."""
    data["last_updated"] = datetime.utcnow().isoformat() + "Z"
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(TRACKING_FILE), exist_ok=True)
        
        with open(TRACKING_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving tracking file: {e}")
        return False

def get_processed_question_ids():
    """Return set of question IDs that have been successfully refined."""
    data = load_processed_data()
    return {item["id"] for item in data.get("processed", []) if item.get("status") == "refined"}

def get_last_processed_id():
    """Return the highest question ID that has been processed (any status).
    Returns 0 if nothing has been processed yet, so fetching starts from ID 1.
    """
    data = load_processed_data()
    ids = [item["id"] for item in data.get("processed", []) if isinstance(item.get("id"), int)]
    return max(ids) if ids else 0

def add_processed_id(question_id, status, **metadata):
    """Record a question as processed."""
    data = load_processed_data()
    
    entry = {
        "id": question_id,
        "refined_at": datetime.utcnow().isoformat() + "Z",
        "status": status,
        **metadata
    }
    
    data["processed"].append(entry)
    
    return save_processed_data(data)

def has_been_refined(question_id):
    """Check if a question has already been successfully refined."""
    return question_id in get_processed_question_ids()

def get_failed_questions():
    """Get list of questions that failed refinement."""
    data = load_processed_data()
    return [item for item in data.get("processed", []) if item.get("status") == "failed"]

def get_stats():
    """Get overall processing statistics."""
    data = load_processed_data()
    total = len(data.get("processed", []))
    refined = len([item for item in data["processed"] if item.get("status") == "refined"])
    failed = len([item for item in data["processed"] if item.get("status") == "failed"])
    
    return {
        "total_processed": total,
        "refined": refined,
        "failed": failed,
        "last_updated": data.get("last_updated")
    }

def get_last_edited_id():
    """Get the ID of the last question that was successfully refined.
    
    Returns the highest ID from all processed questions (refined or failed),
    so the next fetch starts from (last_edited_id + 1).
    
    Returns 0 if no questions have been processed yet (start from ID 1).
    """
    data = load_processed_data()
    
    # Get all processed questions (both refined and failed)
    processed = data.get("processed", [])
    
    if not processed:
        return 0  # Start from ID 1 (1 + 0 = 1)
    
    # Return the highest ID that has been processed
    ids = [item["id"] for item in processed if isinstance(item.get("id"), int)]
    return max(ids) if ids else 0

def clear_tracking():
    """Clear all tracking data (use with caution!)."""
    try:
        if os.path.exists(TRACKING_FILE):
            os.remove(TRACKING_FILE)
        print("✅ Tracking file cleared")
        return True
    except Exception as e:
        print(f"❌ Error clearing tracking file: {e}")
        return False
