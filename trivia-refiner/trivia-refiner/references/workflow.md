# Trivia Refiner Workflow Reference

## The 2-Stage Flow

### Stage 1: FETCH (Cron-based, read-only)

**When:** Automatic at 12 PM daily (except Saturday/Shabbat)

**Script:** `scripts/fetch_batch.py`

**What happens:**
1. Fetches next 10 unprocessed raw questions from Quiz DB
2. Displays them
3. Asks: "Ready to rephrase? Reply: REPHRASE X-Y"
4. **Waits for user command**

**Database impact:** NONE (read-only)

**Safety:** Safe for cron, no modifications

---

### Stage 2: REPHRASE + FORMAT + REVIEW (Interactive)

**When:** User replies "REPHRASE X-Y"

**Script:** `scripts/rephrase_batch.py X-Y`

**What happens:**
1. Fetches questions X through Y from Quiz DB
2. **REPHRASE:** Improves Hebrew phrasing while keeping meaning identical
3. **REVIEW OPTIONS:** 
   - Changes at least 1 wrong option per question
   - Replaces overly specific options with plausible alternatives
   - Never replaces with correct answer
4. **CATEGORIZE:** Assigns best matching category ID and difficulty
5. **FORMAT:** Creates comparison template (old vs new)
6. **DISPLAY:** Shows formatted batch to user
7. **WAIT:** Asks "APPROVE X-Y or FIXES ..."

**Database impact:** NONE (formatting only, saved to memory)

**What user sees:**
```
ID 193
🔴 [original question]
opt1 | opt2 | opt3 | opt4 | ✓ [correct]

🟢 [rephrased question]  
new_opt1 | new_opt2 | new_opt3 | new_opt4 | ✓ [correct]
📁 Category (ID) | ⚡ difficulty
```

---

### Stage 2B: USER REVIEW + APPROVAL

**When:** User reviews the formatted batch

**User can:**
- Reply "APPROVE X-Y" → proceed to update
- Reply "FIXES [description]" → adjust and show again
- Reply "SKIP" → abandon this batch

**If APPROVE X-Y:**
- Proceeds to Stage 3 (update database)

**If FIXES:**
- Adjusts as requested
- Re-shows formatted batch
- Waits for next reply

---

### Stage 3: UPDATE DATABASE (Only on explicit approval)

**When:** User replies "APPROVE X-Y"

**Script:** `scripts/update_batch.py X-Y`

**What happens:**
1. Loads formatted batch from memory
2. Validates all changes
3. **Calls `update_questions` RPC function** for each question
4. RPC function atomically:
   - Updates `raw_questions_he` (source table)
   - Upserts into `questions_he` (production table)
5. Updates tracking file
6. Confirms to user

**Database impact:** DIRECT (actual changes to Quiz DB)

**Safety:** Only called on explicit "APPROVE" command

---

## Database Function: `update_questions`

**Location:** Quiz Supabase (uhfsfedwteeoxsvixvtr)

**Function signature:**
```sql
update_questions(
  p_id integer,                 -- Question ID
  p_question text,               -- Question text (rephrased)
  p_option_1 text,               -- Option 1 (possibly changed)
  p_option_2 text,               -- Option 2 (possibly changed)
  p_option_3 text,               -- Option 3 (possibly changed)
  p_option_4 text,               -- Option 4 (possibly changed)
  p_correct_answer text,         -- Correct answer (unchanged unless question inverted)
  p_category_id integer,         -- Category ID (newly assigned)
  p_difficulty text              -- Difficulty: easy/medium/hard
)
```

**What it does:**
1. Updates `raw_questions_he` (source table with all questions)
2. Upserts into `questions_he` (production table, refined questions only)
3. Atomic operation (both succeed or both fail)

**Called by:** `scripts/update_batch.py` only, on explicit user approval

**Called by:** Never called automatically, never called without approval

---

## Critical Safety Points

1. **FETCH is safe:** Read-only, can run via cron
2. **REPHRASE is safe:** No database writes, only memory
3. **USER REVIEW is mandatory:** User sees exactly what will change before approval
4. **UPDATE is guarded:** Only runs on explicit "APPROVE" reply
5. **No batch processing:** Each stage waits for explicit user command

---

## Tracking

All processed questions tracked in:
```
~/.openclaw/workspace/memory/trivia-refiner-processed.json
```

**Tracks:**
- Question ID
- Status: pending, formatted, approved, updated, failed
- Timestamps

**Used for:**
- Preventing duplicate processing
- Resuming interrupted batches
- Auditing changes

---

## Examples

### Example 1: Successful Flow

```
[CRON 12 PM]
fetch_batch.py
→ "📋 BATCH (193-202) fetched. REPHRASE 193-202?"

[USER]: "REPHRASE 193-202"

[ALFRED]: 
rephrase_batch.py 193-202
→ [formatted batch displayed]
→ "Ready? APPROVE 193-202 or FIXES..."

[USER]: "APPROVE 193-202"

[ALFRED]:
update_batch.py 193-202
→ ✅ Database updated
→ "✅ Batch 193-202 updated in database"
```

### Example 2: User Requests Fixes

```
[ALFRED]: [formatted batch]
→ "Ready? APPROVE 193-202 or FIXES..."

[USER]: "FIXES ID 193 rephrasing is too formal, make it conversational"

[ALFRED]:
[adjusts rephrasing]
[shows updated batch]
→ "Ready? APPROVE 193-202 or FIXES..."

[USER]: "APPROVE 193-202"

[ALFRED]:
update_batch.py 193-202
→ ✅ Database updated
```

### Example 3: Batch Skipped

```
[ALFRED]: [formatted batch]
→ "Ready? APPROVE 193-202 or FIXES..."

[USER]: "SKIP"

[ALFRED]:
→ No database change
→ Next batch fetches later
```

---

## Decision Tree

```
START (FETCH)
   ↓
User sees raw questions
   ↓
User replies "REPHRASE X-Y"?
   ├─ YES → REPHRASE + FORMAT
   │          ↓
   │          User sees formatted batch
   │          ↓
   │          User replies "APPROVE X-Y"?
   │          ├─ YES → UPDATE DATABASE
   │          │        ✅ (database changed)
   │          └─ FIXES → Adjust & show again
   │                     (loop back)
   │
   └─ SKIP → No processing, wait for next batch
```

---

## Behavioral Rules for Alfred

When working with this skill:

1. **On FETCH message:**
   - Show raw questions
   - Do NOT rephrase automatically
   - Wait for "REPHRASE X-Y" command

2. **On "REPHRASE X-Y" command:**
   - Call rephrase_batch.py X-Y
   - Display formatted batch
   - Wait for "APPROVE X-Y" or "FIXES ..." command

3. **On "APPROVE X-Y" command:**
   - Call update_batch.py X-Y 
   - Update database
   - Confirm to user

4. **On "FIXES ..." command:**
   - Acknowledge the feedback
   - Adjust rephrasing/options
   - Re-display formatted batch
   - Wait for next command

**CRITICAL:** Never process without explicit user command at each stage.

---

## Troubleshooting

**Q: I want to change something after rephrasing but before approval**
A: Reply "FIXES [description]". We'll adjust before touching the database.

**Q: Can I see a question twice (different batches)?**
A: No. Tracking prevents reprocessing.

**Q: What if the update fails partway through?**
A: Failures are tracked. You can retry with the same batch range.

**Q: When exactly does the database get updated?**
A: Only when you reply "APPROVE X-Y". Not before, not automatically.
