#!/usr/bin/env python3
"""
Submit approved question changes to the Supabase database.
Expects a JSON file with the changes to be applied.
"""

import json
import sys
import urllib.request
import os

# Tracking
sys.path.insert(0, os.path.dirname(__file__))
from tracking import add_processed_id

# Load credentials from memory/supabase-creds.json
creds_path = os.path.expanduser("~/.openclaw/workspace/memory/supabase-creds.json")
try:
    with open(creds_path) as f:
        creds = json.load(f)
    SUPABASE_URL = creds["url"]
    SUPABASE_KEY = creds["key"]
except Exception as e:
    print(f"Error loading credentials from {creds_path}: {e}")
    sys.exit(1)

def update_question(question_id, data):
    """Update a single question in the database."""
    url = f"{SUPABASE_URL}/rest/v1/Questions?id=eq.{question_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='PATCH'
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result[0] if result else None
    except Exception as e:
        print(f"Error updating question {question_id}: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 submit_changes.py <changes_file.json>")
        sys.exit(1)
    
    changes_file = sys.argv[1]
    
    try:
        with open(changes_file) as f:
            changes = json.load(f)
    except Exception as e:
        print(f"Error reading changes file: {e}")
        sys.exit(1)
    
    if not isinstance(changes, list):
        changes = [changes]
    
    print(f"📤 Submitting {len(changes)} question updates...")
    
    successful = 0
    failed = 0
    
    for change in changes:
        question_id = change.get("id")
        update_data = {k: v for k, v in change.items() if k != "id"}
        
        result = update_question(question_id, update_data)
        if result:
            successful += 1
            add_processed_id(question_id, status="refined")
            print(f"  ✅ Question {question_id} updated")
        else:
            failed += 1
            add_processed_id(question_id, status="failed", notes="PATCH returned empty/error")
            print(f"  ❌ Question {question_id} failed")
    
    print(f"\n{'='*60}")
    print(f"Results: {successful} succeeded, {failed} failed")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
