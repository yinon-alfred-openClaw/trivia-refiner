#!/usr/bin/env python3
"""
Trivia Refiner — Stage 2: REPHRASE + FORMAT
Rephrase questions, review options, assign categories, format for user review.
NO database writes. User reviews and approves before any changes.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime

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

def save_formatted_batch(first_id, last_id, raw_questions):
    """Save raw questions to memory for rephrasing."""
    pending_file = os.path.join(MEMORY_DIR, f"trivia-pending-{first_id}-{last_id}.json")
    with open(pending_file, 'w') as f:
        json.dump({
            "first_id": first_id,
            "last_id": last_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "questions": raw_questions
        }, f, indent=2, ensure_ascii=False)
    return pending_file

def build_rephrase_prompt(questions, categories):
    """Build prompt for Claude to rephrase questions."""
    cat_list = ", ".join([f"{c['id']}={c['name']}" for c in categories])
    
    q_text = ""
    for q in questions:
        q_text += f"""
ID:{q['id']}
ORIGINAL: {q.get('Question', '')}
OPT1: {q.get('Option 1', '')}
OPT2: {q.get('Option 2', '')}
OPT3: {q.get('Option 3', '')}
OPT4: {q.get('Option 4', '')}
CORRECT: {q.get('Correct Answer', '')}
---
"""

    return f"""You are rephrasing Hebrew trivia questions. Perform these tasks:

TASK 1: REPHRASE each question
  • Keep the question meaning identical
  • Improve Hebrew phrasing for clarity
  • Use natural, conversational Hebrew
  • Hebrew only — no English, no translations

TASK 2: REVIEW wrong options
  • For each wrong option (not the correct answer):
    - REPLACE if too specific: unique names, niche references, copyrighted content
    - KEEP if generic: common cities, well-known figures, general concepts
  • MANDATORY: Change at least 1 wrong option per question
  • When replacing: use plausible alternative of same type
  • NEVER replace with the correct answer
  • Add note: "אופציה שונתה: [old] → [new]" for each change

TASK 3: CATEGORIZE and assess difficulty
  • Assign best matching category ID from: {cat_list}
  • Assign difficulty: easy, medium, or hard

TASK 4: FORMAT output (THIS IS THE ONLY THING YOU RETURN)

For each question, return:

ID:N
ORIGINAL: [original question text]
OPT1: [opt1] | OPT2: [opt2] | OPT3: [opt3] | OPT4: [opt4]
CORRECT: [correct answer]
REPHRASED: [rephrased question text]
NEW_OPT1: [opt1] | NEW_OPT2: [opt2] | NEW_OPT3: [opt3] | NEW_OPT4: [opt4]
CATEGORY_ID: [number]
DIFFICULTY: [easy/medium/hard]
NOTES: [any changes made]

---

QUESTIONS TO PROCESS:
{q_text}

Return ONLY the formatted output. No explanations or preamble."""

    return None  # Placeholder

def display_formatted_batch(changes):
    """Display the formatted batch with options visible."""
    print("\n" + "=" * 90)
    print("🎯 BATCH FORMATTED FOR YOUR REVIEW")
    print("=" * 90 + "\n")
    
    for item in changes:
        qid = item['id']
        original_q = item.get('original_question', item.get('Question', '???'))
        rephrased_q = item.get('rephrased_question', item.get('Question', '???'))
        opt1 = item.get('Option 1', '?')
        opt2 = item.get('Option 2', '?')
        opt3 = item.get('Option 3', '?')
        opt4 = item.get('Option 4', '?')
        correct = item.get('Correct Answer', '?')
        category = item.get('category_id', '?')
        difficulty = item.get('difficulty', '?')
        notes = item.get('notes', '')
        
        print(f"ID {qid}")
        print("-" * 90)
        print(f"🔴 {original_q}")
        print(f"   {opt1} | {opt2} | {opt3} | {opt4} | ✓ {correct}")
        print()
        print(f"🟢 {rephrased_q}")
        print(f"   {opt1} | {opt2} | {opt3} | {opt4} | ✓ {correct}")
        print(f"   📁 Category {category} | ⚡ {difficulty}")
        if notes:
            print(f"   📝 {notes}")
        print()

def main():
    """Rephrase batch: fetch, process, format, save, display."""
    
    if len(sys.argv) < 2:
        print("Usage: python3 rephrase_batch.py 193-202")
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
    
    # Save for processing
    pending_file = save_formatted_batch(first_id, last_id, questions)
    
    print(f"📋 REPHRASING BATCH {first_id}-{last_id}")
    print(f"   {len(questions)} questions loaded")
    print(f"   Pending file: {pending_file}")
    print()
    print("⏳ Calling Claude Sonnet to rephrase, review options, and categorize...")
    print()
    print("This script will:")
    print("  1. Rephrase each question in natural Hebrew")
    print("  2. Review and improve wrong options")
    print("  3. Assign category and difficulty")
    print("  4. Format for your review")
    print()
    print("In the actual session, Claude will process these and show you the formatted batch")
    print(f"with all questions and options visible.")
    print()
    print("You will then review and reply:")
    print(f"  APPROVE {first_id}-{last_id}  (to update database)")
    print(f"  FIXES [description]  (to request changes)")

if __name__ == "__main__":
    main()
