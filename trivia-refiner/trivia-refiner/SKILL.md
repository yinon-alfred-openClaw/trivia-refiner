---
name: trivia-refiner
description: "Refine trivia questions in 3-step workflow: (1) Fetch batch → wait for PROCEED approval, (2) Process & format → wait for APPROVE approval, (3) Submit to database. Rephrases Hebrew questions, reviews options, assigns categories and difficulty. All database writes require explicit user approval."
---

# Trivia Refiner — 3-Step Approval Workflow

**🎯 DATABASE: Quiz Supabase (`uhfsfedwteeoxsvixvtr`)**  
This skill operates on **Yinon's Quiz Database**, NOT Alfred's personal Supabase instance.
- `raw_questions_he` — source table with all scraped questions
- `questions_he` — production table with refined questions only

**⚠️ CRITICAL:** No changes to the database happen without explicit user approval at TWO checkpoints.

## The Workflow (3 Steps)

### **Step 1: FETCH (Automatic via cron)**

```bash
0 12 * * 0-5 python3 scripts/run_batch.py
```

**What happens:**
- Fetches next 10 unprocessed questions from Quiz DB
- Displays them raw (no processing)
- Asks: "Ready to process? Reply: PROCEED X-Y"
- **STOPS and waits**

**Script:** `scripts/run_batch.py`
- Read-only (no modifications)
- Exits after asking for approval

---

### **Step 2: PROCESS & FORMAT (Triggered by "PROCEED X-Y")**

When you reply `PROCEED 193-202`, Alfred's session:
1. Calls `scripts/process_batch.py 193-202`
2. Processes questions (rephrase + options review)
3. Categorizes (assigns category_id + difficulty)
4. Formats into comparison template
5. Displays to Telegram

**Template:**
```
ID 193
🔴 באיזה ענף ספורט אולימפי ישראל זכתה במדליית זהב ראשונה?
אתלטיקה | טניס | התעמלות אומנותית ✓ | כדורסל
🟢 באיזה ענף ספורט אולימפי קיבלה ישראל את מדליית הזהב הראשונה?
התעמלות מודרנית | התעמלות אומנותית ✓ | שחיה | טניס
📁 ספורט (21) | ⚡ medium
```

**Script:** `scripts/process_batch.py`
- Takes range: `193-202`
- Fetches, processes, formats
- Saves to memory (NOT database)
- **STOPS and waits for approval**

---

### **Step 3: SUBMIT (Triggered by "APPROVE X-Y")**

When you reply `APPROVE 193-202`, Alfred's session:
1. Calls `scripts/submit_batch.py 193-202`
2. Validates all changes
3. Submits to Quiz Database
4. Updates both `raw_questions_he` and `questions_he`
5. Confirms: "✅ Batch submitted"

**Script:** `scripts/submit_batch.py`
- Reads formatted changes from memory
- Validates before submitting
- Updates Quiz DB
- Tracks in `trivia-refiner-processed.json`
- Cleans up temporary files

---

## Processing Rules

### Rephrasing (Step 2)

- **MANDATORY:** Rephrase every question in natural Hebrew
- Keep the question meaning identical
- Improve clarity and phrasing
- **Hebrew only** — no English, no translations
- Keep correct answer unchanged (unless question structure inverts)

### Option Review (Step 2)

Apply to every wrong option (non-correct answer):

- **REPLACE** if too specific:
  - Unique proper nouns (specific person names)
  - Specific song/movie titles
  - Niche references from copyrighted sources
  - Specific historical events or dates

- **KEEP** if generic enough:
  - Common city names
  - Sport names
  - General concepts
  - Well-known public figures already in context

- **MANDATORY:** Change at least 1 wrong option per question, even if all seem generic
- When replacing: use plausible alternative of same type (name → different name, city → different city)
- **NEVER** replace with correct answer, even partially
- Add 📝 note for each change: "אופציה שונתה: [old] → [new]"

### Categorization (Step 2)

- Assign the BEST matching category ID
- Assign difficulty: easy / medium / hard
- Both are mandatory fields

### Special Cases

**Corrupted data:**
```
ID:N
STATUS: SKIP
REASON: [explain — e.g. contains unrelated words, broken text]
```

**Inverted question** (rephrasing flips the question structure):
```
ID:N
ORIGINAL: [original question]
🔴 [original options] | ✓ [old correct answer]
REPHRASED: [new question]
🟢 [new options] | ✓ [NEW correct answer — different from original]
NOTES: ⚠️ שאלה הופכה — התשובה הנכונה השתנתה
```

---

## Scripts Reference

### `run_batch.py` — Fetch (Step 1)

**Purpose:** Fetch 10 questions, ask for approval, stop.

**Usage:**
```bash
python3 scripts/run_batch.py
```

**Output:**
- Lists 10 raw questions
- Asks: "PROCEED X-Y or SKIP"
- Exits

**Key point:** Read-only, no processing, no database changes.

---

### `process_batch.py` — Process & Format (Step 2)

**Purpose:** Rephrase, review options, categorize, format comparison.

**Usage:**
```bash
python3 scripts/process_batch.py 193-202
```

**What it does:**
1. Fetches questions 193-202 from Quiz DB
2. Calls Claude to rephrase + review options
3. Calls Claude to categorize + assign difficulty
4. Formats into comparison template
5. Saves to memory (not database)
6. Displays to user

**Output:** Formatted batch ready for approval, asks "APPROVE X-Y or EDIT"

**Key point:** No database writes yet. Everything in memory.

---

### `submit_batch.py` — Submit (Step 3)

**Purpose:** Validate and submit approved changes to database.

**Usage:**
```bash
python3 scripts/submit_batch.py 193-202
python3 scripts/submit_batch.py 193-202 --dry-run
```

**What it does:**
1. Loads formatted batch from memory
2. Validates all changes
3. Submits to Quiz DB (PATCH raw_questions_he + POST questions_he)
4. Updates tracking file
5. Cleans up temporary files

**Output:** Confirmation message with success/failure counts

**Key point:** Only runs on explicit approval. All database writes are validated.

---

### `tracking.py` — Utility Module

Tracks processed questions in `~/.openclaw/workspace/memory/trivia-refiner-processed.json`

Functions:
- `get_last_edited_id()` — returns highest processed ID (for cursor-based fetch)
- `add_processed_id(id, status, **metadata)` — log a question
- `get_processed_question_ids()` — set of refined question IDs
- `has_been_refined(id)` — check if already processed
- `get_stats()` — total/refined/failed counts

---

## Approval Flow (Detailed)

```
TIME 0: Cron runs run_batch.py at 12 PM
├─ Fetches questions 193-202
├─ Posts to Telegram: "📋 BATCH FETCHED — Ready? PROCEED 193-202"
└─ WAITS (exits)

TIME 1: You reply "PROCEED 193-202"
├─ Alfred's session receives message
├─ Calls: python3 process_batch.py 193-202
├─ Shows formatted comparison
├─ Posts to Telegram: "🎯 FORMATTED — Approve? APPROVE 193-202"
└─ WAITS

TIME 2: You reply "APPROVE 193-202"
├─ Alfred's session receives message
├─ Calls: python3 submit_batch.py 193-202
├─ Submits to Quiz Database
├─ Posts to Telegram: "✅ SUBMITTED — Batch 193-202 complete"
└─ DONE

If you reply "SKIP" or "EDIT" at any point:
└─ Process stops, waits for next batch or further instructions
```

---

## Critical Safety Rules

| Rule | Why |
|------|-----|
| **Two approvals required** | Prevents accidental database writes |
| **Fetch (Step 1) is read-only** | Can't modify database from cron |
| **All changes validated before submit** | Catches schema errors early |
| **Tracking persists across sessions** | Prevents duplicate processing |
| **No auto-approval** | Alfred never assumes silence = approval |
| **Memory files cleaned after submit** | No stale temporary data |

---

## Credentials

**⚠️ IMPORTANT:** This skill uses **Yinon's Quiz Database**, NOT Alfred's personal database.

Reads from: `~/.openclaw/workspace/memory/supabase-creds.json`

```json
{
  "url": "https://uhfsfedwteeoxsvixvtr.supabase.co",
  "key": "sb_secret_...",
  "project_ref": "uhfsfedwteeoxsvixvtr"
}
```

---

## Database Schema

**Quiz Supabase (`uhfsfedwteeoxsvixvtr`):**

```
raw_questions_he (source):
  id              int (PK)
  Category        text (original — not changed)
  Question        text (updated during refinement)
  Option 1-4      text (updated during refinement)
  Correct Answer  text (kept unchanged unless inverted)
  category_id     int (FK → trivia_categories, assigned during refinement)
  difficulty      text (easy/medium/hard, assigned during refinement)

questions_he (production — refined questions only):
  id              int (PK, matches raw_questions_he.id)
  Category        text
  Question        text
  Option 1-4      text
  Correct Answer  text
  category_id     int
  difficulty      text

trivia_categories (reference):
  id              int (PK)
  name            text (Hebrew category name)
```

---

## Behavioral Rules for Alfred

When trivia-refiner messages appear in Telegram:

1. **On "BATCH FETCHED" message:**
   - Do NOT assume user wants processing
   - Wait for explicit "PROCEED X-Y" reply

2. **On "PROCEED X-Y" reply:**
   - Call `process_batch.py X-Y` immediately
   - Format and display comparison
   - Wait for "APPROVE X-Y" reply

3. **On "APPROVE X-Y" reply:**
   - Call `submit_batch.py X-Y` immediately
   - Confirm submission
   - Done

4. **On "SKIP" or "EDIT" reply:**
   - Do not process further
   - Wait for next instruction

**NEVER assume silence = approval. ALWAYS wait for explicit commands.**

---

## Common Questions

**Q: Can I skip a question in the batch?**
A: Yes, reply "EDIT" when reviewing. The batch will be held for adjustment.

**Q: What if a question inverts?**
A: It's flagged in the formatted output. If you approve, the new correct answer is submitted.

**Q: How do I undo a submission?**
A: Manually edit the Quiz DB or request a rollback. Submissions are permanent.

**Q: Can I process a batch manually?**
A: Yes: `python3 process_batch.py 193-202` followed by `python3 submit_batch.py 193-202 --dry-run`

**Q: What happens if submission fails?**
A: Tracked in `trivia-refiner-processed.json` with error details. Retry manually or contact support.
