---
name: trivia-refiner
description: "Refine Hebrew trivia questions through a 2-stage workflow: (1) Fetch batch → User approves rephrasing, (2) Rephrase + format → User reviews + approves → Update database. Rephrases questions, reviews options, assigns categories and difficulty. Database is NEVER updated until user explicitly approves the formatted batch."
---

# Trivia Refiner — User-Approved Workflow

**🎯 DATABASE: Quiz Supabase (`uhfsfedwteeoxsvixvtr`)**

This skill refines Hebrew trivia questions with strict user oversight. **No database changes happen without explicit user approval.**

---

## The Workflow

### Stage 1: FETCH (Automatic via cron)

```bash
0 12 * * 0-5 python3 scripts/fetch_batch.py
```

**What happens:**
- Fetches next 10 unprocessed questions from Quiz DB
- Shows raw questions
- Asks: "Ready to rephrase? Reply: REPHRASE X-Y"
- **STOPS and waits**

**What it does NOT do:**
- No processing
- No database changes
- No assumptions

---

### Stage 2: REPHRASE + REVIEW + UPDATE (Interactive)

When you reply `REPHRASE X-Y`:

1. **I rephrase** the questions (improve Hebrew phrasing, clarity)
2. **I review options** (replace overly specific ones with plausible alternatives)
3. **I assign categories & difficulty** (best match from available categories)
4. **I format with template** and send to you for review
5. **WAIT for your review**
6. **You send back approval** with any fixes you want
7. **Only then I update** the database using the update_question RPC function

**This is the critical part: NO database write until you approve.**

---

## Step-by-Step Detail

### Fetch Stage

**Script:** `scripts/fetch_batch.py`
- Reads last processed ID from tracking
- Fetches next 10 raw questions
- Prints them for user review
- Exits and waits

Example output:
```
📋 BATCH FETCHED — 10 questions (IDs 203–212)

ID 203 | Hebrew question text...
ID 204 | Hebrew question text...
...

⏸️ Ready to rephrase? Reply:
   REPHRASE 203-212
```

---

### Rephrase + Review Stage

**When you reply:** `REPHRASE 203-212`

**What I do:**

1. **Fetch questions 203-212** from Quiz DB
2. **Rephrase each question** in natural Hebrew
   - Keep question meaning identical
   - Improve phrasing for clarity
   - Hebrew only (no English, no translations)
3. **Review wrong options**
   - Preserve correctness over forced option changes
   - Rephrase the question text itself every time. Changing only the options does not satisfy the task
   - Try to change at least one wrong option per non-SKIP question when a clearly safe replacement exists
   - REPLACE if too specific (unique names, niche references, copyrighted content) and the replacement is clearly wrong for this exact question
   - KEEP if generic (common cities, well-known figures, general concepts)
   - Verify the replacement does NOT create a second correct answer and does NOT make the question ambiguous
   - Do not count typo-only or punctuation-only cleanup as a meaningful option refresh
   - For "NOT" / outsider questions, keep the in-group options intact unless an option is clearly broken and must be replaced with another in-group example
   - For "כל התשובות נכונות" / "אף תשובה אינה נכונה" structures, prefer rephrasing only the question stem and keep the options + correct answer unchanged when edits could break the logic
   - NEVER replace with correct answer
4. **Assign category & difficulty**
   - Best matching category ID
   - Difficulty: easy/medium/hard
5. **Format with template**
6. **Send to you for review**

**Template format:**
```
ID 203
🔴 [original question]
[opt1] | [opt2] | [opt3] | [opt4] | ✓ [correct answer]

🟢 [rephrased question]
[opt1] | [opt2] | [opt3] | [opt4] | ✓ [correct answer]
📁 Category (ID) | ⚡ difficulty

---

[repeat for all 10 questions]

⏸️ Ready to update? Review above, then reply:
   APPROVE 203-212
or:
   FIXES [describe changes needed]
```

---

### Your Review + Approval

**When you reply:** `APPROVE 203-212` (or `FIXES ...`)

**If you reply APPROVE:**
- I call the `update_question` RPC function for each question
- Database is updated with rephrased questions + categories + difficulty
- Confirmation sent

**If you reply FIXES:**
- Tell me what needs changing
- I adjust and resend the formatted batch
- Wait for your next reply

---

## Critical Rules

| Rule | Why |
|------|-----|
| **Never update DB without user approval** | Prevents accidental changes to production |
| **Always format for review first** | User sees exactly what will be changed |
| **Wait for explicit "APPROVE" or "FIXES"** | No assumptions about user intent |
| **Both rephrasing & review happen before sending** | User sees the finished product, not the work-in-progress |
| **Track all changes** | Maintain history in tracking file |
| **Reserve SKIP for truly broken questions** | Weak, ambiguous, or debatable questions should get a 🚩 note, not automatic SKIP |
| **Rephrase the question, not just the options** | A batch is wrong if the green question text stayed effectively unchanged |
| **Treat "כל התשובות נכונות" as a special case** | Usually rephrase only the stem and avoid touching options if that risks breaking the logic |

---

## Scripts

### `fetch_batch.py`

**Purpose:** Fetch next 10 questions, ask for rephrase approval.

**Usage:**
```bash
python3 scripts/fetch_batch.py
```

**Output:**
- Lists 10 raw questions
- Asks: "REPHRASE X-Y"
- Exits

**Safety:** Read-only (safe for cron)

---

### `rephrase_batch.py`

**Purpose:** Rephrase + format batch for user review.

**Usage:**
```bash
python3 scripts/rephrase_batch.py 203-212
```

**What it does:**
1. Fetches questions 203-212
2. Calls Claude to rephrase + review options
3. Calls Claude to categorize + assign difficulty
4. Formats with template
5. Saves to memory (NOT database)
6. Displays formatted batch
7. Asks: "APPROVE 203-212 or FIXES ..."

**Safety:** No database writes

---

### `update_batch.py`

**Purpose:** Update database ONLY after user approval.

**Usage:**
```bash
python3 scripts/update_batch.py 203-212
```

**What it does:**
1. Loads formatted batch from memory
2. Validates all changes
3. Calls `update_question` RPC function for each question
4. Updates raw_questions_he + questions_he (both tables)
5. Updates tracking file
6. Confirms to user

**Safety:** Only runs on explicit "APPROVE" command

---

## Behavioral Rules for Alfred

When trivia-refiner messages appear:

1. **On FETCH message:**
   - Show raw questions
   - Do NOT rephrase automatically
   - Wait for "REPHRASE X-Y"

2. **On "REPHRASE X-Y" reply:**
   - Call rephrase_batch.py X-Y
   - Format and display comparison
   - Wait for "APPROVE X-Y" or "FIXES ..."

3. **On "APPROVE X-Y" reply:**
   - Call update_batch.py X-Y
   - Confirm update

4. **On "FIXES ..." reply:**
   - Adjust as requested
   - Resend formatted batch
   - Wait for next reply

**CRITICAL: Never process without explicit user command at each step.**

---

## Database Function: `update_question`

The RPC function that updates a single question:

```sql
update_question(
  p_id integer,                 -- Question ID
  p_question text,               -- New question text
  p_option_1 text,               -- New option 1
  p_option_2 text,               -- New option 2
  p_option_3 text,               -- New option 3
  p_option_4 text,               -- New option 4
  p_correct_answer text,         -- Correct answer (unchanged unless inverted)
  p_category_id integer,         -- Category ID
  p_difficulty text              -- Difficulty (easy/medium/hard)
)
```

This RPC function atomically:
- Updates `raw_questions_he` (source table)
- Upserts into `questions_he` (production table)

**Called by:** `update_batch.py` on explicit user approval (once per question)

---

## Example: Full Flow

```
[CRON: 12 PM]
fetch_batch.py
→ Telegram: "📋 BATCH 1 (IDs 193-202) fetched. Ready? REPHRASE 193-202"

[YOU]: "REPHRASE 193-202"

[ALFRED]:
rephrase_batch.py 193-202
→ Telegram: "[Formatted batch with old vs new]"
→ Telegram: "Ready to update? APPROVE 193-202 or FIXES ..."

[YOU]: "APPROVE 193-202"

[ALFRED]:
update_batch.py 193-202
→ Updates database
→ Telegram: "✅ Batch 193-202 updated in database"
```

---

## Examples

### Bad vs right: unchanged question

**Bad:** leave the green question text the same and only refresh an option.

**Right:** rewrite the question text itself, even if option changes are minimal or unnecessary.

### Bad vs right: "כל התשובות נכונות"

**Bad:** invert the question, swap options, or change the correct answer when the original structure can be preserved.

**Right:** rephrase only the question stem and keep the options plus `כל התשובות נכונות` unchanged when option edits could damage the logic.

## Troubleshooting

**Q: I want to change something before updating**
A: Reply "FIXES [description]". I'll adjust and show you again.

**Q: Can I skip a batch?**
A: Yes, reply "SKIP". Next batch will fetch later.

**Q: What if rephrasing is wrong?**
A: Tell me in "FIXES" reply. I'll adjust before we update the database.

**Q: When is the database updated?**
A: Only after you reply "APPROVE X-Y". Not before.

---

## Tracking

All processed questions tracked in:
```
~/.openclaw/workspace/memory/trivia-refiner-processed.json
```

Stores:
- Question ID
- Status: pending, formatted, approved, updated, failed
- Metadata: category_id, difficulty

Used to prevent duplicate processing and track progress.
