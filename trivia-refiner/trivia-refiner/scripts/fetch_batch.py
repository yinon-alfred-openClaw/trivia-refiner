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

def get_last_processed_id():
    """Get the highest question ID that has been processed."""
    tracking_file = os.path.expanduser("~/.openclaw/workspace/memory/trivia-refiner-processed.json")
    if not os.path.exists(tracking_file):
        return 0
    
    try:
        with open(tracking_file) as f:
            data = json.load(f)
        ids = [item.get("id") for item in data.get("processed", []) if isinstance(item.get("id"), int)]
        return max(ids) if ids else 0
    except:
        return 0

def fetch_questions(after_id, limit=10):
    """Fetch raw questions from Quiz DB."""
    url = f"{SUPABASE_URL}/rest/v1/raw_questions_he?id=gt.{after_id}&limit={limit}&order=id.asc"
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
    last_id = get_last_processed_id()
    questions = fetch_questions(last_id)
    
    if not questions:
        print(f"❌ No more questions to process after ID {last_id}")
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
