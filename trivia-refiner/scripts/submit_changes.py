#!/usr/bin/env python3
"""
Submit approved question changes to the QUIZ SUPABASE DATABASE (uhfsfedwteeoxsvixvtr).

This script calls the `update_question` RPC function, which is responsible for
updating both the raw table and the final questions table for the selected
language.

Default language: Hebrew (`he`)
Optional language: English (`en`) via `--lang en`

Credentials loaded from ~/.openclaw/workspace/memory/supabase-creds.json (Quiz DB, not Alfred's DB)
"""

import argparse
import json
import sys
import urllib.error
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

def update_question(question_id, data, lang="he"):
    """Update a question by calling the database RPC function `update_question`."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    payload = {
        "p_id": question_id,
        "p_question": data.get("Question"),
        "p_option_1": data.get("Option 1"),
        "p_option_2": data.get("Option 2"),
        "p_option_3": data.get("Option 3"),
        "p_option_4": data.get("Option 4"),
        "p_correct_answer": data.get("Correct Answer"),
        "p_category_id": data.get("category_id"),
        "p_difficulty": data.get("difficulty"),
        "p_lang": lang,
    }

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/update_question",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            response.read()  # 204 is fine; body may be empty

        add_processed_id(
            question_id,
            "refined",
            difficulty=data.get("difficulty"),
            category_id=data.get("category_id"),
            lang=lang,
        )
        return True
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode()
            error_msg = f"{e} — {error_body}"
        except Exception:
            error_msg = str(e)

        add_processed_id(question_id, "failed", error=error_msg, lang=lang)
        print(f"Error updating question {question_id}: {error_msg}")
        return False
    except Exception as e:
        add_processed_id(question_id, "failed", error=str(e), lang=lang)
        print(f"Error updating question {question_id}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("changes_file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--lang", choices=["he", "en"], default="he")
    args = parser.parse_args()

    changes_file = args.changes_file
    dry_run = args.dry_run
    lang = args.lang
    
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
        print(f"🏜️  DRY RUN — No changes will be submitted (lang={lang})")
        print(f"Would update {len(changes)} questions:\n")
        for change in changes:
            qid = change.get("id")
            print(f"  • Question {qid}: {change.get('difficulty')} difficulty, category {change.get('category_id')}")
        print("\nTo actually submit, run without --dry-run flag")
        return
    
    print(f"📤 Submitting {len(changes)} question updates (lang={lang})...\n")
    
    successful = 0
    failed = 0
    
    for change in changes:
        question_id = change.get("id")
        update_data = {k: v for k, v in change.items() if k != "id"}
        
        result = update_question(question_id, update_data, lang=lang)
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
