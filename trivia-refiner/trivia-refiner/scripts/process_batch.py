#!/usr/bin/env python3
"""
Trivia Refiner — Step 2: PROCESS & FORMAT BATCH

⚙️  WHAT THIS DOES:
  • Takes a range of question IDs (e.g., "193-202")
  • Fetches those questions from Quiz DB
  • Calls Claude to rephrase + review options
  • Calls Claude to categorize + assign difficulty
  • Formats into old vs new comparison template
  • Saves formatted output for approval
  • Prints the formatted comparison to Telegram
  • Exits and waits for "APPROVE X-Y" command

📋 APPROVAL FLOW:
  1. User replies "PROCEED X-Y" to fetch message
  2. This script runs automatically
  3. Shows formatted questions side-by-side
  4. User replies "APPROVE X-Y"
  5. submit_batch.py submits to database

⚠️  THIS SCRIPT DOES:
  • Process & rephrase
  • Format for review
  • Save to memory (not database)
  • Wait for approval

⚠️  THIS SCRIPT DOES NOT:
  • Submit to database (that's submit_batch.py)
  • Make assumptions about user intent
"""

import json
import os
import sys
import urllib.request
import subprocess
from datetime import datetime

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

MEMORY_DIR = os.path.expanduser("~/.openclaw/workspace/memory")
os.makedirs(MEMORY_DIR, exist_ok=True)

def fetch_questions(question_ids):
    """Fetch specific questions from Quiz DB."""
    ids_str = ",".join(str(qid) for qid in question_ids)
    url = f"{SUPABASE_URL}/rest/v1/raw_questions_he?id=in.({ids_str})&order=id.asc"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"❌ Error fetching questions: {e}", file=sys.stderr)
        return []

def fetch_categories():
    """Fetch all categories from Quiz DB."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/get_all_categories"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, data=b'{}', headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"❌ Error fetching categories: {e}", file=sys.stderr)
        return []

def build_process_prompt(questions, categories):
    """Build the prompt for Claude to process questions."""
    cat_list = ", ".join([f"{c['id']}={c['name']}" for c in categories])
    
    # Format questions for the prompt
    q_text = ""
    for q in questions:
        q_text += f"""
ID:{q['id']}
Q: {q.get('Question', '')}
OPT1: {q.get('Option 1','')}
OPT2: {q.get('Option 2','')}
OPT3: {q.get('Option 3','')}
OPT4: {q.get('Option 4','')}
CORRECT: {q.get('Correct Answer','')}
---
"""

    return f"""You are refining Hebrew trivia questions. Process EXACTLY as specified below.

TASK 1: REPHRASE each question
  • Keep the question meaning identical
  • Improve Hebrew phrasing for clarity
  • Use natural, conversational Hebrew
  • Do NOT add English, do NOT add translations

TASK 2: REVIEW wrong options
  • For each wrong option (OPT1-4 that is NOT the CORRECT answer):
    - If it's too specific (unique name, niche reference, specific copyrighted content) → REPLACE it
    - If it's generic enough (common city, well-known person, general concept) → KEEP it
    - When replacing: use a plausible alternative of the same type
    - NEVER replace with the correct answer, even partially
  • MANDATORY: Change at least 1 wrong option per question, even if all seem generic
  • Add 📝 note for each change: "אופציה שונתה: [old] → [new]"

TASK 3: CATEGORIZE and assess difficulty
  • Assign the BEST matching category ID from: {cat_list}
  • Assign difficulty: easy, medium, or hard
  • Only you decide — no ambiguity

TASK 4: OUTPUT FORMAT
Return this exact format for each question (NO markdown, NO code blocks):

ID:N
ORIGINAL: [original question text]
OPT1: [option 1] | OPT2: [option 2] | OPT3: [option 3] | OPT4: [option 4]
CORRECT: [correct answer]
REPHRASED: [rephrased question text]
NEW_OPT1: [new option 1] | NEW_OPT2: [new option 2] | NEW_OPT3: [new option 3] | NEW_OPT4: [new option 4]
CORRECT: [correct answer - same as original UNLESS question structure inverted]
CATEGORY_ID: [number]
DIFFICULTY: [easy/medium/hard]
NOTES: [list any changes or issues]

---

SPECIAL CASES:

If question data is corrupted (makes no sense, contains unrelated words):
ID:N
STATUS: SKIP
REASON: [explain why]

---

If rephrasing inverts the question (original correct answer no longer fits):
ID:N
ORIGINAL: [original]
OPT1... CORRECT: [old correct answer]
REPHRASED: [new question]
NEW_OPT1... CORRECT: [NEW correct answer - different from original]
CATEGORY_ID: [number]
DIFFICULTY: [difficulty]
NOTES: ⚠️ שאלה הופכה — התשובה הנכונה השתנתה

---

QUESTIONS TO PROCESS:
{q_text}

Return ONLY the formatted output. No explanations, no preamble."""

    return None  # For now, return None to signal we're not calling Claude directly


def call_claude_for_processing(prompt):
    """Call Claude (via session) to process questions.
    
    In production, this would be handled by the main Alfred session
    which spawns a sub-agent or calls Claude directly.
    
    For now, return None to signal that the user must run this manually.
    """
    # This is a placeholder. In real usage:
    # - Alfred session receives "PROCEED X-Y"
    # - Spawns a sub-agent with this prompt
    # - Sub-agent returns JSON
    # - Main session formats and presents
    
    return None


def save_pending_batch(first_id, last_id, raw_questions):
    """Save raw questions to memory for processing."""
    pending_file = os.path.join(MEMORY_DIR, f"trivia-pending-{first_id}-{last_id}.json")
    with open(pending_file, 'w') as f:
        json.dump({
            "first_id": first_id,
            "last_id": last_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "questions": raw_questions
        }, f, indent=2, ensure_ascii=False)
    return pending_file


def main():
    """Process batch: rephrase, categorize, format for approval."""
    
    if len(sys.argv) < 2:
        print("Usage: python3 process_batch.py 193-202")
        sys.exit(1)
    
    # Parse range
    range_str = sys.argv[1]
    try:
        parts = range_str.split('-')
        first_id = int(parts[0])
        last_id = int(parts[1])
    except (ValueError, IndexError):
        print(f"❌ Invalid range format: {range_str}. Use: 193-202")
        sys.exit(1)
    
    # Fetch questions
    question_ids = list(range(first_id, last_id + 1))
    questions = fetch_questions(question_ids)
    
    if not questions:
        print(f"❌ No questions found in range {first_id}-{last_id}")
        sys.exit(1)
    
    if len(questions) != len(question_ids):
        print(f"⚠️  Expected {len(question_ids)} questions, got {len(questions)}")
    
    # Fetch categories
    categories = fetch_categories()
    
    # Build and save the processing prompt
    prompt = build_process_prompt(questions, categories)
    
    pending_file = save_pending_batch(first_id, last_id, questions)
    
    print(f"📋 PROCESSING BATCH {first_id}-{last_id}")
    print(f"   {len(questions)} questions loaded")
    print(f"   Pending file: {pending_file}")
    print()
    print("⏳ Waiting for Alfred to process...")
    print()
    print("This requires manual intervention from the main session.")
    print("Alfred will call Claude to rephrase and categorize these questions.")
    print()
    print(f"Reply to continue or 'SKIP' to abort.")


if __name__ == "__main__":
    main()
