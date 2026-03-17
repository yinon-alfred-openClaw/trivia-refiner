#!/usr/bin/env python3
"""
Submit approved question changes to the Supabase database.
Expects a JSON file with the changes to be applied.
"""

import json
import sys
import urllib.request
import os
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

VALID_DIFFICULTIES = {"easy", "medium", "hard"}
REQUIRED_FIELDS = {"Question", "Option 1", "Option 2", "Option 3", "Option 4", "category_id", "difficulty"}

def validate_change(change):
    """Validate that a change has all required fields."""
    missing = REQUIRED_FIELDS - set(change.keys())
    if missing:
        return False, f"Missing fields: {', '.join(missing)}"
    
    if change.get("difficulty") not in VALID_DIFFICULTIES:
        return False, f"Invalid difficulty '{change['difficulty']}'. Must be: {', '.join(VALID_DIFFICULTIES)}"
    
    if not isinstance(change.get("category_id"), int) or change.get("category_id") <= 0:
        return False, f"Invalid category_id '{change.get('category_id')}'. Must be a positive integer."
    
    return True, "Valid"

def update_question(question_id, data):
    """Update a question via the update_question RPC.
    Atomically updates raw_questions_he AND upserts into questions_he.
    Direct writes to questions_he are blocked by RLS — this is the only write path.
    """
    url = f"{SUPABASE_URL}/rest/v1/rpc/update_question"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    rpc_payload = {
        "p_id": question_id,
        "p_question": data.get("Question"),
        "p_option_1": data.get("Option 1"),
        "p_option_2": data.get("Option 2"),
        "p_option_3": data.get("Option 3"),
        "p_option_4": data.get("Option 4"),
        "p_correct_answer": data.get("Correct Answer"),
        "p_category_id": data.get("category_id"),
        "p_difficulty": data.get("difficulty")
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(rpc_payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            if result:
                # Mark as successfully refined
                add_processed_id(
                    question_id,
                    "refined",
                    difficulty=data.get("difficulty"),
                    category_id=data.get("category_id")
                )
            return result[0] if result else None
    except urllib.error.HTTPError as e:
        # Try to read error body for more details
        try:
            error_body = e.read().decode()
            error_msg = f"{e} — {error_body}"
        except:
            error_msg = str(e)
        
        # Mark as failed
        add_processed_id(question_id, "failed", error=error_msg)
        print(f"Error updating question {question_id}: {error_msg}")
        return None
    except Exception as e:
        # Mark as failed
        add_processed_id(question_id, "failed", error=str(e))
        print(f"Error updating question {question_id}: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 submit_changes.py <changes_file.json> [--dry-run]")
        sys.exit(1)
    
    changes_file = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    
    try:
        with open(changes_file) as f:
            changes = json.load(f)
    except Exception as e:
        print(f"Error reading changes file: {e}")
        sys.exit(1)
    
    if not isinstance(changes, list):
        changes = [changes]
    
    # Validate all changes first
    print(f"🔍 Validating {len(changes)} changes...")
    invalid = []
    for idx, change in enumerate(changes):
        valid, msg = validate_change(change)
        if not valid:
            invalid.append((change.get("id"), msg))
    
    if invalid:
        print(f"\n❌ Found {len(invalid)} validation error(s):\n")
        for qid, msg in invalid:
            print(f"  Question {qid}: {msg}")
        print("\n⚠️  Please fix the errors and try again.")
        return
    
    print(f"✅ All changes are valid\n")
    
    if dry_run:
        print("🏜️  DRY RUN — No changes will be submitted")
        print(f"Would update {len(changes)} questions:\n")
        for change in changes:
            qid = change.get("id")
            print(f"  • Question {qid}: {change.get('difficulty')} difficulty, category {change.get('category_id')}")
        print("\nTo actually submit, run without --dry-run flag")
        return
    
    print(f"📤 Submitting {len(changes)} question updates...\n")
    
    successful = 0
    failed = 0
    
    for change in changes:
        question_id = change.get("id")
        update_data = {k: v for k, v in change.items() if k != "id"}
        
        result = update_question(question_id, update_data)
        if result:
            successful += 1
            print(f"  ✅ Question {question_id} updated")
        else:
            failed += 1
            print(f"  ❌ Question {question_id} failed")
    
    print(f"\n{'='*60}")
    print(f"Results: {successful} succeeded, {failed} failed")
    print(f"Tracking file: {os.path.expanduser('~/.openclaw/workspace/memory/trivia-refiner-processed.json')}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
