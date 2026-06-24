#!/usr/bin/env python3
"""
Trivia Refiner — Stage 1: FETCH
Fetch 10 raw questions and ask for rephrasing approval.
Safe for cron — read-only, no database changes.
"""

import json
import os
import sys
import urllib.request

# Load credentials
creds_path = os.path.expanduser("~/.openclaw/workspace/memory/supabase-creds.json")
try:
    with open(creds_path) as f:
        creds = json.load(f)
    SUPABASE_URL = creds["url"]
    SUPABASE_KEY = creds["key"]
except Exception as e:
    print(f"❌ Error loading credentials: {e}")
    sys.exit(1)

FINAL_TABLE = "questions_he"
RAW_TABLE = "raw_questions_he"

def get_last_final_question_id():
    """Get the highest question ID already present in questions_he."""
    url = f"{SUPABASE_URL}/rest/v1/{FINAL_TABLE}?select=id&order=id.desc&limit=1"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            rows = json.loads(response.read().decode())
    except Exception as e:
        print(f"❌ Error reading latest {FINAL_TABLE} id: {e}", file=sys.stderr)
        sys.exit(1)

    return rows[0]["id"] if rows else 0

def fetch_questions(start_id, limit=10):
    """Fetch raw questions from Quiz DB."""
    url = f"{SUPABASE_URL}/rest/v1/{RAW_TABLE}?id=gte.{start_id}&limit={limit}&order=id.asc"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"❌ Error fetching questions: {e}", file=sys.stderr)
        return []

def main():
    """Fetch batch and ask for approval."""
    last_id = get_last_final_question_id()
    next_id = last_id + 1
    questions = fetch_questions(next_id)
    
    if not questions:
        print(f"❌ No more questions to process starting from ID {next_id}")
        return
    
    first_id = questions[0]['id']
    last_fetched_id = questions[-1]['id']
    
    print(f"📋 BATCH FETCHED — {len(questions)} questions")
    print(f"IDs: {first_id}–{last_fetched_id}")
    print()
    
    for q in questions:
        qid = q['id']
        category = q.get('Category', 'unknown')
        question = q.get('Question', '???')
        print(f"ID {qid} | {category}: {question[:60]}...")
    
    print()
    print(f"⏸️  Ready to rephrase & review? Reply with:")
    print(f"   REPHRASE {first_id}-{last_fetched_id}")
    print()
    print("Or reply SKIP to wait for the next batch.")

if __name__ == "__main__":
    main()
