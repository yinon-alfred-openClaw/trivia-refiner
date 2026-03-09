#!/usr/bin/env python3
"""
Trivia Refiner — Daily Batch Runner
Fetches 10 questions, processes them via Sonnet,
and prints the formatted comparison for user approval.
Cron's --announce flag sends output to Telegram.
"""

import json
import os
import sys
import urllib.request
import subprocess

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

TRACKING_FILE = os.path.expanduser("~/.openclaw/workspace/memory/trivia-refiner-processed.json")
MAX_BATCHES = 10

def load_tracking():
    if not os.path.exists(TRACKING_FILE):
        return {"version": "1", "processed": [], "batch_count": 0}
    with open(TRACKING_FILE) as f:
        return json.load(f)

def get_last_edited_id():
    data = load_tracking()
    ids = [item["id"] for item in data.get("processed", []) if isinstance(item.get("id"), int)]
    return max(ids) if ids else 0

def get_batch_count():
    data = load_tracking()
    return data.get("batch_count", 0)

def increment_batch_count():
    data = load_tracking()
    data["batch_count"] = data.get("batch_count", 0) + 1
    with open(TRACKING_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def fetch_questions(after_id, limit=10):
    url = f"{SUPABASE_URL}/rest/v1/Questions?id=gt.{after_id}&limit={limit}&order=id.asc"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"❌ Error fetching questions: {e}", file=sys.stderr)
        return []

def fetch_categories():
    url = f"{SUPABASE_URL}/rest/v1/trivia_categories?order=id.asc"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"❌ Error fetching categories: {e}", file=sys.stderr)
        return []

def build_orchestrator_prompt(questions, categories):
    cat_list = ", ".join([f"{c['id']}={c['name']}" for c in categories])
    
    q_text = ""
    for q in questions:
        q_text += f"""
ID:{q['id']} | {q.get('Question', '')}
OPT1:{q.get('Option 1','')} | OPT2:{q.get('Option 2','')} | OPT3:{q.get('Option 3','')} | OPT4:{q.get('Option 4','')} | CORRECT:{q.get('Correct Answer','')}
"""

    return f"""You are processing Hebrew trivia questions. You must do THREE tasks and return ONLY the final formatted output — nothing else.

TASK 1 — REPHRASE each question:
- Rephrasing is MANDATORY for every question
- Hebrew only — no English, no parentheses with translations
- Keep the correct answer unchanged
- Optionally improve 1-2 weak wrong options
- If question data is clearly corrupted (e.g. contains unrelated words like ingredient names), mark it SKIP

TASK 2 — CATEGORIZE each question:
Available categories: {cat_list}
Assign the single most fitting category ID and difficulty (easy/medium/hard).

TASK 3 — FORMAT the output as follows (this is the ONLY thing you return):

For each valid question:
ID:N
🔴 [original question]
[orig opt1] | [orig opt2] | [orig opt3] | [orig opt4] | ✓ [correct answer]
🟢 [rephrased question]
[new opt1] | [new opt2] | [new opt3] | [new opt4] | ✓ [correct answer]
📁 [category_id] | ⚡ [difficulty]

---

For SKIP questions:
ID:N — ⚠️ דילוג — שאלה פגומה בבסיס הנתונים

---

For questions where rephrasing INVERTED the question structure (old correct answer no longer fits the new question):
ID:N
🔴 [original question]
[original options] | ✓ [old correct answer]
🟢 [rephrased question]
[new options] | ✓ [NEW correct answer]
📁 [category_id] | ⚡ [difficulty]
⚠️ שאלה הופכה — התשובה הנכונה עודכנה ל: [new correct answer]

---

End the entire output with this line:
האם לאשר ולשלוח את השינויים לבסיס הנתונים? ✅ / ❌

QUESTIONS TO PROCESS:
{q_text}

Return ONLY the formatted output. No explanations, no preamble, no markdown code blocks."""

def call_sonnet(prompt):
    """Call Sonnet via openclaw sessions_spawn subagent"""
    try:
        # Call OpenClaw subagent with Sonnet
        result = subprocess.run([
            "openclaw", "sessions_spawn",
            "--runtime", "subagent",
            "--mode", "run",
            "--model", "sonnet",
            "--task", prompt
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            print(f"❌ Sonnet error: {result.stderr}", file=sys.stderr)
            return None
        
        return result.stdout.strip()
    except Exception as e:
        print(f"❌ Error calling Sonnet: {e}", file=sys.stderr)
        return None

def main():
    batch_count = get_batch_count()
    if batch_count >= MAX_BATCHES:
        print("✅ כל 10 הבאצ'ים הושלמו. הסקריפט יופסק.")
        return

    last_id = get_last_edited_id()
    questions = fetch_questions(last_id)
    if not questions:
        print(f"❌ לא נמצאו שאלות נוספות החל מ-ID {last_id + 1}")
        return

    categories = fetch_categories()
    prompt = build_orchestrator_prompt(questions, categories)
    
    # Call Sonnet to process the batch
    print(f"🔄 עיבוד בצ'ים {batch_count + 1}/10...", file=sys.stderr)
    response = call_sonnet(prompt)
    
    if not response:
        print("❌ שגיאה בעיבוד השאלות. אנא נסה שוב.")
        return
    
    # Output formatted comparison (cron's --announce sends this to Telegram)
    header = f"📋 **בצ'ים {batch_count + 1}/10 — {len(questions)} שאלות**\n\n"
    print(header + response)
    
    # Increment batch count
    increment_batch_count()
    print(f"✅ בצ'ים {batch_count + 1} שלח לאישור.", file=sys.stderr)

if __name__ == "__main__":
    main()
