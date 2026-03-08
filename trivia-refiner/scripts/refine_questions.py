#!/usr/bin/env python3
"""
Trivia Question Refiner
Fetches 10 questions, rephrase with Gemini Flash, gets Sonnet feedback,
chooses category/difficulty, then asks for approval before submitting to DB.
"""

import json
import sys
import urllib.request
import os

# Tracking — import from same scripts/ directory
sys.path.insert(0, os.path.dirname(__file__))
from tracking import get_processed_ids_set, add_processed_id, print_summary

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

def fetch_questions(limit=30):
    """Fetch unapproved questions from the Questions table."""
    url = f"{SUPABASE_URL}/rest/v1/Questions?limit={limit}&order=id.asc"
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
    """Fetch all categories from trivia_categories table."""
    url = f"{SUPABASE_URL}/rest/v1/trivia_categories?order=id.asc"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    req = urllib.request.Request(url, headers=headers)
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
    # ── Show tracking stats upfront ──────────────────────────────────────────
    print_summary()
    already_refined = get_processed_ids_set()
    print()

    # Fetch more than needed so we have enough after filtering
    FETCH_LIMIT = 30
    TARGET = 10

    print(f"🔄 Fetching up to {FETCH_LIMIT} questions from database...")
    questions = fetch_questions(FETCH_LIMIT)

    if not questions:
        print("❌ No questions found.")
        return

    # ── Skip already-processed questions ────────────────────────────────────
    new_questions = [q for q in questions if q.get("id") not in already_refined]
    skipped_count = len(questions) - len(new_questions)

    if skipped_count:
        print(f"⏭️  Skipped {skipped_count} already-refined question(s)")

    if not new_questions:
        print("🎉 All fetched questions have already been refined. Nothing to do!")
        return

    # Trim to target batch size
    questions = new_questions[:TARGET]
    print(f"✅ Processing {len(questions)} new questions")

    print("\n📋 Fetching categories...")
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
