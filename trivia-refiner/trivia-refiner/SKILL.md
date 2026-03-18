---
name: trivia-refiner
description: "Refine trivia questions by rephrasing with Gemini Flash, reviewing with Sonnet, assigning categories and difficulty levels, and submitting approved changes directly to the Supabase database. Use when you need to: (1) Process a batch of 10 trivia questions at once, (2) Improve Hebrew phrasing and option quality, (3) Auto-categorize questions and assess difficulty, (4) Review all changes before submission, (5) Update questions in the questions database."
---

# Trivia Refiner

**🎯 DATABASE: Quiz Supabase (`uhfsfedwteeoxsvixvtr`)**  
This skill operates on **Yinon's Quiz Database**, NOT Alfred's personal Supabase instance.
- `raw_questions_he` — source table with all scraped questions (read & update)
- `questions_he` — production table with refined questions only (auto-upserted on approval)

Fetch 10 questions, process them silently in the background, then show one clean before/after comparison message. User approves → submit to database.

## Quick Start

```bash
python3 skills/trivia-refiner/scripts/refine_questions.py
```

Then spawn subagents (see below), compile results, present ONE message to user.

---

## Workflow

### Step 1 — Fetch

Run `scripts/refine_questions.py` — it reads the last processed ID from tracking and fetches the next 10 questions. **Do not show output to the user.**

### Step 2 — Process (silent, background)

Spawn a **single Gemini Flash subagent** for ALL 10 questions at once:

- **MANDATORY:** Rephrase every question in natural Hebrew
- **MANDATORY:** Review every wrong option individually — replace if too specific (see Option Rules below)
- Keep the correct answer unchanged (unless the question structure inverts — see Step 3)
- All text must be **Hebrew only** — no English, no parentheses with translations

**Option Rules:**
- **REPLACE** if the option is too specific: unique proper nouns, specific song titles, specific person names, niche references that could only come from a copyrighted quiz source
- **KEEP** if the option is generic enough: common city names, sport names, general concepts, well-known public figures already in the question context
- When replacing, use a plausible alternative of the same type (e.g. song title → different song title, name → different name in the same field)
- **NEVER** replace a wrong option with the correct answer, even partially
- Add a 📝 note for every option changed: "אופציה שונתה: [old] → [new]"

Prompt format (send all 10 in one call):

```
For each question:
1. Rephrase the question (mandatory)
2. Keep correct answer the same
3. Optionally improve weak wrong options

Return format:
ID:N
NEW_Q: [rephrased question]
OPT1: [option]
OPT2: [option]
OPT3: [option]
OPT4: [option]
CORRECT: [correct answer]

If question data is corrupted: write "SKIP" under the ID.
```

### Step 3 — Categorize & Review (silent, background)

Spawn a **single Sonnet subagent** for all valid questions at once:

- Assign the best category ID from `trivia_categories`
- Assign difficulty: easy / medium / hard

Return format:
```
ID:N | CAT:XX | DIFF:easy
```

### Step 4 — Detect Issues (silent, internal)

Before presenting to user, check each question for:

- **Corrupted data** — question text makes no sense (e.g. contains ingredient names instead of a question). Mark as ⚠️ SKIP.
- **Inverted question** — Gemini rephrased the question in a way that the original correct answer no longer appears in the options (meaning the question structure flipped). Flag this explicitly so Alfred can decide whether to update the Correct Answer field too or skip.

### Step 5 — Present ONE message to user

Format ALL questions into a single clean message. Show old vs new side by side. Include the correct answer. Flag any issues. Do NOT send intermediate messages.

**Template:**

```
ID:1
🔴 [original question]
[opt1] | [opt2] | [opt3] | [opt4] | ✓ [correct answer]
🟢 [rephrased question]
[opt1] | [opt2] | [opt3] | [opt4] | ✓ [correct answer]
📁 [category_id] | ⚡ [difficulty]

---

ID:2
🔴 ...
🟢 ...
📁 ... | ⚡ ...

---

ID:5 — ⚠️ דילוג — שאלה פגומה בבסיס הנתונים

---

ID:9 — ⚠️ שאלה הופכה — התשובה הנכונה השתנתה. הוגשה עם תשובה מעודכנת: [new correct answer]

---

האם לאשר ולשלוח את השינויים לבסיס הנתונים? ✅ / ❌
```

### Step 6 — Submit on approval

If user approves:
1. Write all changes to `/tmp/trivia_changes.json`
2. Run `scripts/submit_changes.py /tmp/trivia_changes.json`
3. For inverted questions where Correct Answer changed — submit via direct PATCH (not through submit_changes.py, which preserves the original Correct Answer)
4. Tracking file updates automatically after each successful submission

---

## Key Rules

| Rule | Detail |
|------|--------|
| Rephrasing | MANDATORY for every question |
| Option changes | MANDATORY review — replace specific ones, keep generic ones |
| Language | Hebrew only — no English additions |
| Correct Answer | Keep unchanged unless question structure inverts |
| User messages | ONE message only (the comparison). Everything else is silent. |
| Corrupted data | Flag as ⚠️ SKIP — do not submit |
| Inverted questions | Flag clearly — submit with updated Correct Answer if user approved |
| Fetch cursor | Reads last processed ID from tracking file — always fetches next 10 |

---

## Scripts

### `scripts/refine_questions.py`
Fetches next 10 unprocessed questions using cursor-based pagination (`id > last_edited_id LIMIT 10`).

Returns: list of questions with all fields.

### `scripts/submit_changes.py <changes.json>`
Validates and submits changes. Tracks success/failure in `trivia-refiner-processed.json`.

Supports `--dry-run` flag for testing.

### `scripts/tracking.py`
- `get_last_edited_id()` — returns highest processed ID (cursor for next fetch)
- `add_processed_id(id, status, **meta)` — log a question result
- `get_stats()` — show totals

---

## Credentials

Reads from: `~/.openclaw/workspace/memory/supabase-creds.json`

```json
{
  "url": "https://xxxx.supabase.co",
  "key": "sb_secret_xxxxx"
}
```

---

## Database Schema

```
raw_questions_he table (source — read & fetch from here):
  id            int (PK)
  Category      text (original category string — keep unchanged)
  Question      text ← update
  Option 1-4    text ← update
  Correct Answer text ← keep unchanged (update only if question inverted)
  category_id   int (FK → trivia_categories) ← update
  difficulty    text (easy/medium/hard) ← update

questions_he table (production — write ONLY via update_question RPC):
  Same schema. Direct writes blocked by RLS.
  Only questions approved through the pipeline live here.

trivia_categories (via get_all_categories RPC):
  id    int (PK)
  name  text (Hebrew)
```

### API Endpoints
- **Fetch questions:** `GET /rest/v1/raw_questions_he`
- **Fetch categories:** `POST /rest/v1/rpc/get_all_categories`
- **Submit approved batch:** `POST /rest/v1/rpc/update_question`
  - Params: `p_id`, `p_question`, `p_option_1`–`p_option_4`, `p_correct_answer`, `p_category_id`, `p_difficulty`
  - Atomically updates `raw_questions_he` + upserts into `questions_he`

---

## Subagent Models

| Task | Model |
|------|-------|
| Rephrasing + option improvement | `google/gemini-2.5-flash` |
| Categorization + difficulty | `sonnet` |
