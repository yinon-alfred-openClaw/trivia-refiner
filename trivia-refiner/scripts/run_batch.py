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
    data["last_updated"] = __import__('datetime').datetime.utcnow().isoformat() + 'Z'
    with open(TRACKING_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def fetch_questions(after_id, limit=10):
    url = f"{SUPABASE_URL}/rest/v1/raw_questions_he?id=gt.{after_id}&limit={limit}&order=id.asc"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"❌ Error fetching questions: {e}", file=sys.stderr)
        return []

def fetch_categories():
    url = f"{SUPABASE_URL}/rest/v1/rpc/get_all_categories"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=b'{}', headers=headers, method='POST')
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

TASK 1 — REPHRASE each question AND review its wrong options:
- Rephrasing is MANDATORY for every question
- Hebrew only — no English, no parentheses with translations
- Keep the correct answer UNCHANGED — never alter it, never use it as a wrong option
- If question data is clearly corrupted (e.g. contains unrelated words like ingredient names), mark it SKIP

OPTION RULES (preserve correctness first):
- בדוק מחדש את כל האפשרויות השגויות בכל שאלה שאינה SKIP
- נסה לשנות לפחות אפשרות שגויה אחת בכל שאלה, אבל רק אם זה בטוח וברור לחלוטין
- העדף מסיח סביר מאותו סוג, שברור שהוא שגוי עבור השאלה הזו
- לפני כל שינוי, ודא שההחלפה לא יוצרת תשובה נכונה נוספת ולא הופכת את השאלה לעמומה
- אם שינוי אפשרות עלול לפגוע בנכונות השאלה, השאר את האפשרויות כפי שהן
- מותר להשאיר את כל האפשרויות ללא שינוי רק אם אינך בטוח שיש החלפה בטוחה
- תיקון כתיב, ניקוד, פיסוק או ניסוח זעיר של אותה אפשרות לא נחשב לשינוי אפשרות אמיתי, ולא מספיק לבדו
- עבור שאלות מהסוג "איזו מהאפשרויות אינה...", "מי מהבאים אינו...", "איזה מהבאים אינו..." או שאלות outsider / NOT אחרות:
  - שמור על מבנה קבוצת-הפנים
  - אל תכפה שינוי אפשרויות
  - שנה אפשרות רק אם היא פגומה, כפולה, לא תקינה, או אם אפשר להחליף אותה בבטחה באפשרות אחרת מאותה קבוצה
- לעולם אל תשתמש בתשובה הנכונה כאפשרות שגויה, גם לא חלקית
- הוסף 📝 הערה רק על שינוי אפשרות אמיתי: "אופציה שונתה: [old] → [new]"

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
    """
    NOTE: This function is intentionally left as a passthrough.
    run_batch.py outputs the prompt + raw questions for Alfred (Claude)
    to process directly in the session. Alfred applies the option-change
    rules and rephrasing, then the user approves before submit_changes.py runs.
    Returning None here signals main() to print the prompt for Alfred instead.
    """
    return None

def main():
    batch_count = get_batch_count()

    last_id = get_last_edited_id()
    questions = fetch_questions(last_id)
    if not questions:
        print(f"❌ לא נמצאו שאלות נוספות החל מ-ID {last_id + 1}")
        return

    categories = fetch_categories()
    prompt = build_orchestrator_prompt(questions, categories)
    
    # Output the prompt for Alfred to process directly in the session
    print(f"📋 **בצ'ים {batch_count + 1} — {len(questions)} שאלות | IDs {questions[0]['id']}–{questions[-1]['id']}**")
    print()
    print("Alfred — process the following questions using the rules below:")
    print()
    print(prompt)
    
    # Increment batch count
    increment_batch_count()
    print(f"\n✅ בצ'ים {batch_count + 1} מוכן לעיבוד.", file=sys.stderr)

if __name__ == "__main__":
    main()
