#!/usr/bin/env python3
"""Config-driven trivia refiner batch prompt builder.

This script intentionally does not refine or submit questions itself. It reads
the next raw batch for the requested language, builds the prompt for the
trivia-manager agent, and increments the per-language batch counter.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
SKILL_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = SKILL_ROOT / "config"
CREDS_PATH = WORKSPACE / "memory" / "supabase-creds.json"

LANGUAGE_PROFILES = {
    "he": {
        "label": "Hebrew",
        "batch_label": "בצ'ים",
        "ready": "מוכן לעיבוד",
        "no_more": "לא נמצאו שאלות נוספות",
        "process_line": "Alfred — process the following Hebrew questions using the rules below:",
        "language_rule": "Hebrew only — no English, no parentheses with translations",
        "option_rules": """- בדוק מחדש את כל האפשרויות השגויות בכל שאלה שאינה SKIP
- נסה לשנות לפחות אפשרות שגויה אחת בכל שאלה, אבל רק אם זה בטוח וברור לחלוטין
- העדף מסיח סביר מאותו סוג, שברור שהוא שגוי עבור השאלה הזו
- לפני כל שינוי, ודא שההחלפה לא יוצרת תשובה נכונה נוספת ולא הופכת את השאלה לעמומה
- אם שינוי אפשרות עלול לפגוע בנכונות השאלה, השאר את האפשרויות כפי שהן
- עבור שאלות נכון/לא נכון, שמור על מבנה שתי תשובות ואל תמציא מסיחים נוספים
- עבור שאלות outsider / NOT, שמור על מבנה קבוצת-הפנים ואל תכפה שינוי אפשרויות
- עבור שאלות מסוג כל התשובות נכונות / אף תשובה אינה נכונה, העדף לנסח מחדש רק את השאלה עצמה
- לעולם אל תשתמש בתשובה הנכונה כאפשרות שגויה
- הוסף הערה רק על שינוי אפשרות אמיתי: "אופציה שונתה: [old] → [new]" """,
        "safe_none": "🛟 הצעה בטוחה: אין — [specific blocker]",
        "summary": "Hebrew trivia: updated X by consensus, sent Y for review.",
        "choose_line": "לבחור/לתקן את השאלות למעלה? ✅ / ❌",
        "low_score": "⚠️ דירוג נמוך — [short reason]",
        "skip_line": "ID:N — ⚠️ דילוג — שאלה פגומה בבסיס הנתונים",
        "safe_header": "🛟 הצעה בטוחה:",
        "why_safe": "למה זה בטוח:",
        "sources": "מקורות:",
    },
    "en": {
        "label": "English",
        "batch_label": "EN Batch",
        "ready": "ready for review",
        "no_more": "No additional English questions found",
        "process_line": "Alfred — process the following English questions using the rules below:",
        "language_rule": "English only. Keep the wording natural and concise.",
        "option_rules": """- Re-check the wrong options for every non-SKIP question
- Try to change at least one wrong option when it is clearly safe to do so
- Prefer a safe distractor of the same type that is clearly wrong for this exact question
- Before changing an option, verify the replacement does not create a second correct answer or ambiguity
- If changing an option would risk correctness, leave the options unchanged
- For true/false questions, preserve the two-answer structure and do not invent extra options
- For NOT / outsider questions, keep the in-group structure intact and do not force option changes
- For All of the above / None of the above structures, prefer rephrasing only the stem
- Never replace a wrong option with the correct answer
- Add a note for every changed option: "Option changed: [old] → [new]" """,
        "safe_none": "🛟 Safe suggestion: none — [specific blocker]",
        "summary": "English trivia: updated X by consensus, sent Y for review.",
        "choose_line": "Choose/fix the questions above? ✅ / ❌",
        "low_score": "⚠️ Low score — [short reason]",
        "skip_line": "ID:N — ⚠️ SKIP — corrupted source question",
        "safe_header": "🛟 Safe suggestion:",
        "why_safe": "Why safe:",
        "sources": "Sources:",
    },
}


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_credentials() -> tuple[str, str]:
    try:
        creds = load_json(CREDS_PATH)
        return creds["url"], creds["key"]
    except Exception as exc:
        print(f"❌ Error loading credentials from {CREDS_PATH}: {exc}", file=sys.stderr)
        sys.exit(1)


def load_config(lang: str) -> dict:
    config_path = CONFIG_DIR / f"{lang}.json"
    try:
        config = load_json(config_path)
    except Exception as exc:
        print(f"❌ Error loading config {config_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    expected = {
        "he": {
            "raw_table": "raw_questions_he",
            "final_table": "questions_he",
            "tracking_file": "memory/trivia-refiner-processed.json",
            "artifact_dir": "memory/trivia-consensus/he",
        },
        "en": {
            "raw_table": "questions_raw_en",
            "final_table": "questions_en",
            "tracking_file": "memory/trivia-refiner-en-processed.json",
            "artifact_dir": "memory/trivia-consensus/en",
        },
    }[lang]

    if config.get("lang") != lang:
        raise SystemExit(f"❌ Config language mismatch: expected {lang}, got {config.get('lang')}")

    for key, value in expected.items():
        if config.get(key) != value:
            raise SystemExit(f"❌ Unsafe {lang} config: {key} must be {value}, got {config.get(key)}")

    return config


def tracking_path(config: dict) -> Path:
    return WORKSPACE / config["tracking_file"]


def artifact_dir(config: dict) -> Path:
    return WORKSPACE / config["artifact_dir"]


def load_tracking(config: dict) -> dict:
    path = tracking_path(config)
    if not path.exists():
        return {"version": "1", "processed": [], "batch_count": 0}
    return load_json(path)


def save_tracking(config: dict, data: dict) -> None:
    path = tracking_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_batch_count(config: dict) -> int:
    return int(load_tracking(config).get("batch_count", 0))


def increment_batch_count(config: dict) -> None:
    data = load_tracking(config)
    data["batch_count"] = int(data.get("batch_count", 0)) + 1
    save_tracking(config, data)


def request_json(url: str, key: str, *, data: dict | None = None) -> list | dict:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = None if data is None else json.dumps(data).encode("utf-8")
    method = "GET" if data is None else "POST"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def get_last_final_question_id(config: dict, supabase_url: str, supabase_key: str) -> int:
    final_table = config["final_table"]
    url = f"{supabase_url}/rest/v1/{final_table}?select=id&order=id.desc&limit=1"
    try:
        rows = request_json(url, supabase_key)
    except Exception as exc:
        print(f"❌ Error reading latest {final_table} id: {exc}", file=sys.stderr)
        sys.exit(1)
    return rows[0]["id"] if rows else 0


def fetch_questions(config: dict, supabase_url: str, supabase_key: str, start_id: int, limit: int) -> list:
    raw_table = config["raw_table"]
    url = f"{supabase_url}/rest/v1/{raw_table}?id=gte.{start_id}&limit={limit}&order=id.asc"
    try:
        result = request_json(url, supabase_key)
    except Exception as exc:
        print(f"❌ Error fetching {config['lang']} questions from {raw_table}: {exc}", file=sys.stderr)
        return []
    return result if isinstance(result, list) else []


def fetch_categories(config: dict, supabase_url: str, supabase_key: str) -> list:
    url = f"{supabase_url}/rest/v1/rpc/get_all_categories"
    try:
        result = request_json(url, supabase_key, data={"language": config["lang"]})
    except Exception as exc:
        print(f"❌ Error fetching {config['lang']} categories: {exc}", file=sys.stderr)
        return []
    return result if isinstance(result, list) else []


def format_questions(questions: list) -> str:
    lines = []
    for q in questions:
        lines.append(
            "\n".join(
                [
                    f"ID:{q['id']} | {q.get('Question', '')}",
                    (
                        f"OPT1:{q.get('Option 1','')} | OPT2:{q.get('Option 2','')} | "
                        f"OPT3:{q.get('Option 3','')} | OPT4:{q.get('Option 4','')} | "
                        f"CORRECT:{q.get('Correct Answer','')}"
                    ),
                ]
            )
        )
    return "\n\n".join(lines)


def build_prompt(config: dict, questions: list, categories: list) -> str:
    lang = config["lang"]
    profile = LANGUAGE_PROFILES[lang]
    cat_list = ", ".join([f"{c['id']}={c['name']}" for c in categories])
    q_text = format_questions(questions)
    first_id = questions[0]["id"]
    last_id = questions[-1]["id"]
    artifacts = artifact_dir(config)
    proposal_json = artifacts / f"batch-{first_id}-{last_id}-trivia-manager.json"
    submitted_json = artifacts / f"batch-{first_id}-{last_id}-submitted.json"
    submit_script = SKILL_ROOT / "scripts" / "submit_changes.py"
    tracking = tracking_path(config)

    return f"""You are processing {profile['label']} trivia questions in CONSENSUS AUTO mode. Your goal is autonomous high-quality updating, not over-holding. Fix what you can fix safely. This is an execution task, not a text-only formatting task: use tools/commands to save artifacts, request audit, submit approved clean questions, verify the database, and only then return the final concise user-facing output.

FULL QUESTION DATA IS PROVIDED HERE. Do not ask the user to provide it again.
QUESTIONS TO PROCESS:
{q_text}

LANGUAGE CONFIG:
- lang: {config['lang']}
- raw table: {config['raw_table']}
- final table: {config['final_table']}
- tracking file: {tracking}
- artifact dir: {artifacts}

CRITICAL CONSENSUS FLOW — BEFORE ANY DATABASE WRITE:
1. First create your full refined proposal for every question.
2. Save it as JSON under:
   {proposal_json}
   The proposal JSON may contain audit fields, but every item that might be submitted must also include this exact update schema:
   "id", "Question", "Option 1", "Option 2", "Option 3", "Option 4", "Correct Answer", "category_id", "difficulty".
3. Do not hand-write JSON with shell heredocs. Use Python json.dump(..., ensure_ascii=False, indent=2) or another real JSON serializer, then immediately validate the file with Python json.load.
4. If the proposal JSON or submitted-clean JSON does not parse, fix the JSON before audit/submission. Invalid JSON means zero updates and must be reported as failure.
5. Ask Alfred/main agent to audit the original batch plus your proposal BEFORE submitting.
   Do NOT use sessions_send or sessions_history for this audit because that path is asynchronous and may return before Alfred has answered.
   Use a blocking CLI command through the shell, for example:
   /home/ubuntu/.npm-global/bin/openclaw agent --agent main --timeout 600 --message "<audit request>"
   The audit request MUST define Alfred as reviewer only, not a second refiner:
   - Allowed classifications: agree, reject, unresolved.
   - agree means Alfred confirms your exact final update preserves the original meaning, correct answer, and safe options.
   - reject means your proposal changes meaning, adds unsupported facts, has unsafe options, or otherwise should not auto-submit.
   - unresolved means the source/fact problem cannot be safely judged from the provided data.
   - Do NOT ask Alfred for rewrites, improved wording, or replacement update fields.
   - Do NOT allow an alfred_fix path. If Alfred returns a rewrite/fix anyway, treat that question as reject or unresolved; never submit Alfred's rewrite automatically and never show it as an alternate suggestion.
6. If Alfred/main audit fails, is blocked, or does not clearly approve your exact clean final version, do NOT submit and do NOT claim updates for that question.
7. If Alfred agrees with your exact final version, submit automatically only if the final version still meets all auto-submit criteria below.
8. If Alfred rejects or marks a question unresolved, do NOT ask Alfred to fix it. Hold it for Yinon review with your proposal and Alfred's reason.
9. Write submitted clean questions to this exact JSON file containing ONLY the exact update schema required by submit_changes.py:
   {submitted_json}
10. Validate the submitted-clean JSON with Python json.load before running submit_changes.py.
11. Submit approved clean questions with:
   python3 {submit_script} <submitted-clean-json> --lang {lang}
12. After submission, verify that {config['final_table']} contains every submitted ID and that {tracking} advanced accordingly. If verification fails, report the failure instead of success.
13. If the final version after Alfred review is still score <=6, has any warning, or has unresolved truth/meaning risk, do NOT submit it; send it to Yinon for review.
14. Do not use "hold" as the first response to normal fixable issues. Answer-type mismatch, too-close distractor, weak phrasing, or category/difficulty problems should be fixed, then submitted only after Alfred agrees and the final re-score is clean 7+.

TASK 1 — REPHRASE each question AND review its wrong options:
- Rephrasing is MANDATORY for every question.
- {profile['language_rule']}
- The question text itself must be rephrased every time. Changing only the options is not enough.
- Keep the original meaning unless the fact-check shows a narrower wording is required.
- Do not add unsupported facts.
- Keep the correct answer unchanged unless the source question is explicitly inverted and you hold it for review.
- True/false questions are valid when Option 1/2 are the only answers and Option 3/4 are null/empty.
- Mark SKIP only for truly broken source data: gibberish, malformed structure, missing core data, or another concrete source failure.
- If the question is damaged but options and correct answer make a sensible reconstruction possible, flag it, score it low, and hold it for review.

OPTION RULES:
{profile['option_rules']}

TASK 2 — CATEGORIZE each question:
Available categories: {cat_list}
Assign the single most fitting category ID and difficulty (easy/medium/hard).

TASK 3 — SELF-RANK your own work:
- Add a self-score from 1 to 10 for every processed question.
- Any warning, unresolved concern, damaged-source reconstruction, ambiguity, outdated-fact risk, or compromise must score below 5.
- Scores 7+ are only for clean, confident questions with no warning note.

TASK 3.5 — CONSENSUS AUTO DECISION:
- Mark a question internally as CONSENSUS-SUBMIT only if all are true:
  - score is 7+
  - no warning or low-score line
  - not reconstructed from damaged/missing source text
  - not a fragile all-of-the-above / none-of-the-above logic question
  - no factual uncertainty, ambiguity, disputed wording, or outdated-fact risk
  - correct answer is preserved and options are safe
- Questions become DB updates only after Alfred/main agrees with your exact final version, and the final submitted version remains clean.
- Always provide this summary format: "{profile['summary']}"
- X must be the number of questions actually submitted by submit_changes.py and verified in {config['final_table']}. If you did not run submit + verify successfully, X must be 0 and you must report the concrete failure.

TASK 3.6 — SAFE SUGGESTIONS FOR HELD QUESTIONS:
- For every held question, include a safe_suggestion unless no safe version can be made.
- The safe_suggestion must directly address the hold/rejection reason.
- Use web verification for unstable, disputed, current, origin, political, legal, medical, superlative, or celebrity-family facts.
- Include source URLs for every safe_suggestion that used web verification.
- If no safe suggestion can be made, write: "{profile['safe_none']}".
- Never submit a safe_suggestion automatically. It requires Yinon's explicit approval and a later submit_changes.py --lang {lang} run.

TASK 4 — FORMAT USER-FACING OUTPUT AFTER CONSENSUS SUBMISSION:
- Do not show the full batch by default.
- After consensus-submitting eligible questions, output the summary first.
- Then include only rejected/unresolved/held question blocks for Yinon review.
- If no questions need review, output only the summary.

For each held valid question:
ID:N
Original: [original question]
[orig opt1] | [orig opt2] | [orig opt3] | [orig opt4] | correct: [correct answer]
Refined: [rephrased question]
[new opt1] | [new opt2] | [new opt3] | [new opt4] | correct: [correct answer]
Category: [category_id] | difficulty: [difficulty] | score: [score]/10
{profile['safe_header']}
[safe question]
[safe opt1] | [safe opt2] | [safe opt3] | [safe opt4] | correct: [safe correct answer]
{profile['why_safe']} [short reason tied to Alfred's flag/rejection]
{profile['sources']} [URLs, if web verification was used]

If score < 5, add this line directly under the question block:
{profile['low_score']}

For unresolved/SKIP questions:
{profile['skip_line']}

If there are questions for review, end with this line:
{profile['choose_line']}

If there are no review questions, end after the summary line.

Do not return a success summary until after tool/command execution is complete. Final response rules:
- If submit + verification succeeded, return only: "{profile['summary']}" plus any held question blocks.
- If submit or verification failed, return a concise failure summary naming the failed step.
- No markdown code blocks."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=sorted(LANGUAGE_PROFILES), default="he")
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.lang)
    profile = LANGUAGE_PROFILES[args.lang]
    supabase_url, supabase_key = load_credentials()

    batch_count = get_batch_count(config)
    last_id = get_last_final_question_id(config, supabase_url, supabase_key)
    next_id = last_id + 1
    questions = fetch_questions(config, supabase_url, supabase_key, next_id, args.limit)
    if not questions:
        print(f"❌ {profile['no_more']} starting from ID {next_id}")
        return

    artifact_dir(config).mkdir(parents=True, exist_ok=True)
    categories = fetch_categories(config, supabase_url, supabase_key)
    prompt = build_prompt(config, questions, categories)

    print(
        f"📋 **{profile['batch_label']} {batch_count + 1} — "
        f"{len(questions)} questions | IDs {questions[0]['id']}–{questions[-1]['id']}**"
    )
    print()
    print(profile["process_line"])
    print()
    print(prompt)

    increment_batch_count(config)
    print(f"\n✅ {profile['batch_label']} {batch_count + 1} {profile['ready']}.", file=sys.stderr)


if __name__ == "__main__":
    main()
