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
FINAL_TABLE = "questions_he"
RAW_TABLE = "raw_questions_he"

def load_tracking():
    if not os.path.exists(TRACKING_FILE):
        return {"version": "1", "processed": [], "batch_count": 0}
    with open(TRACKING_FILE) as f:
        return json.load(f)

def get_last_final_question_id():
    """Return the highest ID already present in questions_he.

    The final table is the source of truth for auto batch selection. The local
    tracking file is useful for audit history, but it must not decide the next
    raw IDs to process.
    """
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

def get_batch_count():
    data = load_tracking()
    return data.get("batch_count", 0)

def increment_batch_count():
    data = load_tracking()
    data["batch_count"] = data.get("batch_count", 0) + 1
    data["last_updated"] = __import__('datetime').datetime.utcnow().isoformat() + 'Z'
    with open(TRACKING_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def fetch_questions(start_id, limit=10):
    url = f"{SUPABASE_URL}/rest/v1/{RAW_TABLE}?id=gte.{start_id}&limit={limit}&order=id.asc"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "x-admin-secret": "vM7N5v16k14cxs5MJZj3BjZ2bxyYr0KERPSnb5ZTr7g"}
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
    req = urllib.request.Request(url, data=json.dumps({"language": "he"}).encode("utf-8"), headers=headers, method='POST')
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

    return f"""You are processing Hebrew trivia questions in CONSENSUS AUTO mode. Your goal is autonomous high-quality updating, not over-holding. Fix what you can fix safely. This is an execution task, not a text-only formatting task: use tools/commands to save artifacts, request audit, submit approved clean questions, verify the database, and only then return the final concise user-facing output.

FULL QUESTION DATA IS PROVIDED HERE. Do not ask the user to provide it again.
QUESTIONS TO PROCESS:
{q_text}

CRITICAL CONSENSUS FLOW — BEFORE ANY DATABASE WRITE:
1. First create your full refined proposal for every question.
2. Save it as JSON under:
   /home/ubuntu/.openclaw/workspace/memory/trivia-consensus/he/batch-{questions[0]['id']}-{questions[-1]['id']}-trivia-manager.json
   The proposal JSON may contain audit fields, but every item that might be submitted must also include this exact update schema:
   "id", "Question", "Option 1", "Option 2", "Option 3", "Option 4", "Correct Answer", "category_id", "difficulty".
3. Do not hand-write JSON with shell heredocs. Hebrew strings may contain quote characters such as הנח"ל. Use Python `json.dump(..., ensure_ascii=False, indent=2)` or another real JSON serializer, then immediately validate the file with Python `json.load`.
4. If the proposal JSON or submitted-clean JSON does not parse, fix the JSON before audit/submission. Invalid JSON means zero updates and must be reported as failure.
5. Ask Alfred/main agent to audit the original batch plus your proposal BEFORE submitting.
   Do NOT use `sessions_send` or `sessions_history` for this audit because that path is asynchronous and may return before Alfred has answered.
   Use a blocking CLI command through the shell, for example:
   /home/ubuntu/.npm-global/bin/openclaw agent --agent main --timeout 600 --message "<audit request>"
   The audit request MUST define Alfred as reviewer only, not a second refiner:
   - Allowed classifications: `agree`, `reject`, `unresolved`.
   - `agree` means Alfred confirms your exact final update preserves the original meaning, correct answer, and safe options.
   - `reject` means your proposal changes meaning, adds unsupported facts, has unsafe options, or otherwise should not auto-submit.
   - `unresolved` means the source/fact problem cannot be safely judged from the provided data.
   - Do NOT ask Alfred for rewrites, improved wording, or replacement update fields.
   - Do NOT allow an `alfred_fix` path. If Alfred returns a rewrite/fix anyway, treat that question as `reject` or `unresolved`; never submit Alfred's rewrite automatically and never show it as an alternate suggestion.
6. If Alfred/main audit fails, is blocked, or does not clearly approve your exact clean final version, do NOT submit and do NOT claim updates for that question.
7. If Alfred agrees with your exact final version, submit automatically only if the final version still meets all auto-submit criteria below.
8. If Alfred rejects or marks a question unresolved, do NOT ask Alfred to fix it. Hold it for Yinon review with your proposal and Alfred's reason.
   For every held question, also create a separate safe_suggestion when possible. The safe_suggestion is for Yinon approval only, not automatic DB submission.
9. Write submitted clean questions to this exact JSON file containing ONLY the exact update schema required by `submit_changes.py`:
   /home/ubuntu/.openclaw/workspace/memory/trivia-consensus/he/batch-{questions[0]['id']}-{questions[-1]['id']}-submitted.json
10. Validate the submitted-clean JSON with Python `json.load` before running `submit_changes.py`.
11. Submit approved clean questions with:
   python3 /home/ubuntu/.openclaw/workspace/skills/trivia-refiner/trivia-refiner/scripts/submit_changes.py <submitted-clean-json> --lang he
12. After submission, verify that `questions_he` contains every submitted ID and that `/home/ubuntu/.openclaw/workspace/memory/trivia-refiner-processed.json` advanced accordingly. If verification fails, report the failure instead of success.
13. If the final version after Alfred review is still score ≤6, has any 🚩/⚠️, or has unresolved truth/meaning risk, do NOT submit it; send it to Yinon for review.
14. If Alfred rejects your proposal or marks the question unresolved, do NOT submit that question; send Yinon your proposal, Alfred's review reason, and a safe_suggestion if one can be made.
15. Do not use “hold” as the first response to normal fixable issues. Answer-type mismatch, too-close distractor, weak phrasing, or category/difficulty problems should be fixed, then submitted only after Alfred agrees and the final re-score is clean 7+.

TASK 1 — REPHRASE each question AND review its wrong options:
- Rephrasing is MANDATORY for every question
- Hebrew only — no English, no parentheses with translations
- The QUESTION TEXT itself must be rephrased every time. Changing only the options is NOT enough
- Keep the correct answer UNCHANGED — never alter it, never use it as a wrong option
- If the question is true/false (only two answers such as נכון/לא נכון or True/False), preserve the two-answer structure and keep Option 3/4 as null/empty; do not invent extra distractors
- Mark a question as SKIP only if it is truly broken: gibberish, malformed structure, missing core data, or another concrete source failure
- Do NOT treat a valid true/false question as broken only because Option 3 and Option 4 are None/null/empty; two-answer true/false questions are allowed
- If the question text is damaged, missing, or appears to contain only answer options, but the options and correct answer exist:
  - FLAG the issue with a 🚩 note
  - Try to infer the intended question from the options and correct answer
  - If you can reconstruct a sensible, useful question, include it in the batch with the reconstructed question, category, difficulty, and a low confidence score
  - If no good question can be inferred safely, mark it SKIP; do not invent a weak question just to avoid skipping
- If the question is understandable but you think it is weak, ambiguous, disputed, outdated, or badly written, do NOT mark it SKIP
- Instead, process it normally and add a bottom note in this format: 🚩 [short reason why the question may be problematic]

OPTION RULES (preserve correctness first):
- בדוק מחדש את כל האפשרויות השגויות בכל שאלה שאינה SKIP
- נסה לשנות לפחות אפשרות שגויה אחת בכל שאלה, אבל רק אם זה בטוח וברור לחלוטין
- העדף מסיח סביר מאותו סוג, שברור שהוא שגוי עבור השאלה הזו
- לפני כל שינוי, ודא שההחלפה לא יוצרת תשובה נכונה נוספת ולא הופכת את השאלה לעמומה
- ודא שהמסיח החדש שגוי בבירור. אל תשתמש במסיח שקרוב מדי סמנטית לתשובה הנכונה, נכון חלקית, או עלול לבלבל שחקן סביר
- אם שינוי אפשרות עלול לפגוע בנכונות השאלה, השאר את האפשרויות כפי שהן
- מותר להשאיר את כל האפשרויות ללא שינוי רק אם אינך בטוח שיש החלפה בטוחה
- תיקון כתיב, ניקוד, פיסוק או ניסוח זעיר של אותה אפשרות לא נחשב לשינוי אפשרות אמיתי, ולא מספיק לבדו
- עבור שאלות מהסוג "איזו מהאפשרויות אינה...", "מי מהבאים אינו...", "איזה מהבאים אינו..." או שאלות outsider / NOT אחרות:
  - שמור על מבנה קבוצת-הפנים
  - אל תכפה שינוי אפשרויות
  - שנה אפשרות רק אם היא פגומה, כפולה, לא תקינה, או אם אפשר להחליף אותה בבטחה באפשרות אחרת מאותה קבוצה
- עבור שאלות מסוג "כל התשובות נכונות", "אף תשובה אינה נכונה" או מבנים מקבילים שבהם ההיגיון תלוי בכלל האפשרויות יחד:
  - העדף לנסח מחדש רק את השאלה עצמה
  - השאר את התשובה הנכונה ללא שינוי
  - אל תשנה אפשרויות אם שינוי שלהן עלול לשבור את ההיגיון של "כל התשובות נכונות" / "אף תשובה אינה נכונה"
  - אל תהפוך את מבנה השאלה אם אפשר להימנע מזה
- לעולם אל תשתמש בתשובה הנכונה כאפשרות שגויה, גם לא חלקית
- הוסף 📝 הערה רק על שינוי אפשרות אמיתי: "אופציה שונתה: [old] → [new]"

EXAMPLES:
- BAD: להשאיר את השאלה המקורית כמו שהיא ולשנות רק אפשרות אחת
- RIGHT: לנסח מחדש את השאלה עצמה גם אם שינוי האפשרויות מינימלי או לא נדרש
- BAD: בשאלת "כל התשובות נכונות" לשנות את מבנה השאלה, להחליף אפשרויות, או לעדכן את התשובה הנכונה כשאין בכך הכרח
- RIGHT: בשאלת "כל התשובות נכונות" לנסח מחדש רק את השאלה עצמה, ולהשאיר את האפשרויות ואת התשובה הנכונה כפי שהן אם שינוי עלול לפגוע בלוגיקה

TASK 2 — CATEGORIZE each question:
Available categories: {cat_list}
Assign the single most fitting category ID and difficulty (easy/medium/hard).

TASK 3 — SELF-RANK your own work for each question:
- Add a self-score from 1 to 10 based on how confident you are in the rephrase, option quality, and overall soundness
- 1 = very poor / badly broken / strong unresolved concern
- 5 = usable but shaky, notable concern remains
- 10 = excellent, confident result
- If you add a 🚩 note for any reason, the score MUST be BELOW 5
- If you noticed a problem in the source question, ambiguity, outdated fact risk, weak distractors, or any compromise in your refinement, the score MUST be BELOW 5
- Scores above 5 are only for clean questions with no 🚩 note and no unresolved concern
- Use this scale strictly:
  - 1-4 = warning / problematic / compromised
  - 5 = borderline but still usable
  - 6-10 = clean and confident, no warning note

TASK 3.5 — CONSENSUS AUTO DECISION:
- Mark each processed question internally as CONSENSUS-SUBMIT only if ALL are true:
  - score is 7+
  - no 🚩 warning and no ⚠️ low-score line
  - not reconstructed from damaged/missing source text
  - not a fragile "כל התשובות נכונות" / "אף תשובה אינה נכונה" logic question
  - no factual uncertainty, ambiguity, disputed wording, or outdated-fact risk
  - correct answer is preserved and options are safe
- Questions become DB updates only after Alfred/main agent agrees with your exact final version, AND the final submitted version is scored 7+ with no 🚩/⚠️ and no unresolved concern.
- If the refiner score is low and Alfred/main also agrees the final version remains low/risky, send it to Yinon for review instead of submitting.
- Send to Yinon only rejected, unresolved, or final low/risky questions.
- Always provide a summary: "Hebrew trivia: updated X by consensus, sent Y for review."
- X must be the number of questions actually submitted by `submit_changes.py` and verified in `questions_he`. If you did not run submit + verify successfully, X must be 0 and you must report the concrete failure.
- If Y > 0, send only rejected/unresolved blocks. If Y = 0, send only the summary.

TASK 3.6 — SAFE SUGGESTIONS FOR HELD QUESTIONS:
- For every question sent to Yinon for review, include a safe_suggestion block unless no safe version can be made.
- The safe_suggestion must directly address the reason the question was held or rejected:
  - unsafe distractor: replace it with clearly wrong distractors of the same type
  - current/source-dependent wording: reframe to a stable verified fact
  - disputed origin/superlative/date: ask a narrower, better-sourced fact
  - damaged premise: reconstruct only if the answer/options make one safe question obvious
- Use web verification for unstable, disputed, current, origin, political, legal, medical, superlative, or celebrity-family facts.
- Include source URLs for every safe_suggestion that used web verification.
- If no safe suggestion can be made, write: "🛟 הצעה בטוחה: אין — [specific blocker]".
- Never submit a safe_suggestion automatically. It requires Yinon's explicit approval and a later `submit_changes.py --lang he` run.

TASK 4 — FORMAT USER-FACING OUTPUT AFTER CONSENSUS SUBMISSION:
- Do not show the full batch by default.
- After consensus-submitting eligible questions, output the summary first.
- Then include only REJECTED/UNRESOLVED question blocks for Yinon review.
- If no questions need review, output only the summary.

For each REJECTED/UNRESOLVED valid question:
ID:N
🔴 [original question]
[orig opt1] | [orig opt2] | [orig opt3] | [orig opt4] | ✓ [correct answer]
🟢 [rephrased question]
[new opt1] | [new opt2] | [new opt3] | [new opt4] | ✓ [correct answer]
📁 [category_id] | ⚡ [difficulty] | 🎯 [score]/10
🛟 הצעה בטוחה:
[safe question]
[safe opt1] | [safe opt2] | [safe opt3] | [safe opt4] | ✓ [safe correct answer]
למה זה בטוח: [short reason tied to Alfred's flag/rejection]
מקורות: [URLs, if web verification was used]

If score < 5, add this line directly under the question block:
⚠️ דירוג נמוך — [short reason]

---

For UNRESOLVED/SKIP questions:
ID:N — ⚠️ דילוג — שאלה פגומה בבסיס הנתונים

---

If you have concerns about a question but it is still processable, add this line directly under that question block:
🚩 [short reason why the question may be problematic]

---

For questions where rephrasing INVERTED the question structure (old correct answer no longer fits the new question):
ID:N
🔴 [original question]
[original options] | ✓ [old correct answer]
🟢 [rephrased question]
[new options] | ✓ [NEW correct answer]
📁 [category_id] | ⚡ [difficulty] | 🎯 [score]/10
⚠️ שאלה הופכה — התשובה הנכונה עודכנה ל: [new correct answer]

---

If there are questions for review, end with this line:
לבחור/לתקן את השאלות למעלה? ✅ / ❌

If there are no review questions, end after the summary line.

Do not return a success summary until after tool/command execution is complete. Final response rules:
- If submit + verification succeeded, return only: "Hebrew trivia: updated X by consensus, sent Y for review." plus any held question blocks.
- If submit or verification failed, return a concise failure summary naming the failed step.
- No markdown code blocks."""

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

    last_id = get_last_final_question_id()
    next_id = last_id + 1
    questions = fetch_questions(next_id)
    if not questions:
        print(f"❌ לא נמצאו שאלות נוספות החל מ-ID {next_id}")
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
