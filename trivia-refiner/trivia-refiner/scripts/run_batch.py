#!/usr/bin/env python3
"""
Trivia Refiner — Step 1: FETCH BATCH

⚙️  WHAT THIS DOES:
  • Fetches the next 10 unprocessed questions from Quiz DB
  • Displays them raw (no processing)
  • Asks user for approval to proceed
  • Exits and waits for "PROCEED X-Y" command

📋 APPROVAL FLOW:
  1. Cron runs this script → sends questions to Telegram
  2. User sees batch + replies "PROCEED X-Y"
  3. User's reply triggers process_batch.py (handled by Alfred session)
  4. process_batch.py processes + formats + shows comparison
  5. User replies "APPROVE X-Y"
  6. submit_batch.py submits to database

⚠️  THIS SCRIPT DOES NOT:
  • Process questions
  • Format output
  • Submit to database
  • Make any decisions

It only fetches and asks. That's it.
"""

import json
import os
import sys
import urllib.request
from tracking import get_last_edited_id

# Load credentials (Quiz DB only)
creds_path = os.path.expanduser("~/.openclaw/workspace/memory/supabase-creds.json")
try:
    with open(creds_path) as f:
        creds = json.load(f)
    SUPABASE_URL = creds["url"]
    SUPABASE_KEY = creds["key"]
except Exception as e:
    print(f"❌ Error loading credentials: {e}")
    sys.exit(1)

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
    """Fetch batch and ask for approval. That's all."""
    
    last_id = get_last_edited_id()
    questions = fetch_questions(last_id)
    
    if not questions:
        print(f"❌ No more questions to process after ID {last_id}")
        return
    
    first_id = questions[0]['id']
    last_fetched_id = questions[-1]['id']
    
    # Print raw questions for user review
    print(f"📋 BATCH FETCHED — {len(questions)} questions")
    print(f"IDs: {first_id}–{last_fetched_id}")
    print()
    
    for q in questions:
        qid = q['id']
        category = q.get('Category', 'unknown')
        question = q.get('Question', '???')
        print(f"ID {qid} | {category}: {question[:60]}...")
    
    print()
    print(f"⏸️  Ready to process? Reply with:")
    print(f"   PROCEED {first_id}-{last_fetched_id}")
    print()
    print("Or reply SKIP to wait for the next batch.")

if __name__ == "__main__":
    main()
