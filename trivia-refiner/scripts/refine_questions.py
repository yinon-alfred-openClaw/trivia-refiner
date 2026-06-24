#!/usr/bin/env python3
"""
Trivia Question Refiner
Fetches 10 unprocessed questions starting from the last edited ID.
"""

import json
import sys
import urllib.request
import os
from tracking import get_stats

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

FINAL_TABLE = "questions_he"
RAW_TABLE = "raw_questions_he"

def get_last_final_question_id():
    """Return the highest ID already present in questions_he."""
    url = f"{SUPABASE_URL}/rest/v1/{FINAL_TABLE}?select=id&order=id.desc&limit=1"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            rows = json.loads(response.read().decode())
    except Exception as e:
        print(f"Error reading latest {FINAL_TABLE} id: {e}")
        sys.exit(1)

    return rows[0]["id"] if rows else 0

def fetch_questions_from_id(start_id, limit=10):
    """Fetch questions starting from a specific raw question ID."""
    url = f"{SUPABASE_URL}/rest/v1/{RAW_TABLE}?id=gte.{start_id}&limit={limit}&order=id.asc"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching questions: {e}")
        return []

def fetch_categories():
    """Fetch all categories via get_all_categories RPC."""
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
        print(f"Error fetching categories: {e}")
        return []

def format_question_for_display(q):
    """Format a question nicely for display."""
    return {
        "id": q.get("id"),
        "original_question": q.get("Question"),
        "original_category": q.get("Category"),
        "original_category_id": q.get("category_id"),
        "option_1": q.get("Option 1"),
        "option_2": q.get("Option 2"),
        "option_3": q.get("Option 3"),
        "option_4": q.get("Option 4"),
        "correct_answer": q.get("Correct Answer")
    }

def main():
    # Show tracking stats upfront
    stats = get_stats()
    if stats["total_processed"] > 0:
        print(f"📊 Tracking Stats: {stats['refined']} refined, {stats['failed']} failed")
        print(f"   Last updated: {stats['last_updated']}\n")
    
    # Use questions_he as the source of truth for the next raw ID.
    last_edited_id = get_last_final_question_id()
    next_start_id = last_edited_id + 1
    
    print(f"🔄 Fetching 10 questions starting from ID {next_start_id}...")
    questions = fetch_questions_from_id(next_start_id, limit=10)
    
    if not questions:
        if last_edited_id == 0:
            print("❌ No questions found in the database.")
        else:
            print(f"✅ All questions processed! (reached ID {last_edited_id})")
            print(f"   No more unprocessed questions available.")
        return
    
    actual_ids = [q.get("id") for q in questions]
    print(f"✅ Fetched {len(questions)} questions (IDs {actual_ids[0]}–{actual_ids[-1]})\n")
    
    print("📋 Fetching categories...")
    categories = fetch_categories()
    category_list = "\n".join([f"{c['id']}. {c['name']}" for c in categories])
    
    # Prepare data structure for processing
    all_questions = []
    for q in questions:
        formatted = format_question_for_display(q)
        all_questions.append(formatted)
    
    # Output for the user to see the raw data
    print(f"\n{'='*60}")
    print("QUESTIONS TO PROCESS (Raw Data)")
    print(f"{'='*60}\n")
    
    for idx, q in enumerate(all_questions, 1):
        print(f"Question {idx} (ID: {q['id']})")
        print(f"  Original: {q['original_question']}")
        print(f"  Category: {q['original_category']}")
        print(f"  Options:")
        print(f"    1. {q['option_1']}")
        print(f"    2. {q['option_2']}")
        print(f"    3. {q['option_3']}")
        print(f"    4. {q['option_4']}")
        print(f"  Correct: {q['correct_answer']}")
        print()
    
    print(f"\n{'='*60}")
    print("AVAILABLE CATEGORIES FOR ASSIGNMENT")
    print(f"{'='*60}\n{category_list}")
    print(f"\n{'='*60}")
    
    # Return structured data for processing
    return {
        "questions": all_questions,
        "categories": categories,
        "category_list_text": category_list
    }

if __name__ == "__main__":
    main()
