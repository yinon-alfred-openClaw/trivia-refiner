---
name: trivia-refiner
description: "Refine Hebrew or English trivia questions with a config-driven semi-auto workflow, guarded consensus submission, and explicit held-question review."
---

# Trivia Refiner — Semi-Auto Review Workflow

**🎯 DATABASE: Quiz Supabase (`uhfsfedwteeoxsvixvtr`)**

This skill refines Hebrew and English trivia questions with guarded automation. Yinon has approved semi-auto mode: clean high-confidence questions may be submitted automatically, while risky questions must be held for review.

Language selection is explicit and config-driven. Do not rely on session memory to choose the language:

```bash
python3 scripts/run_batch.py --lang he
python3 scripts/run_batch.py --lang en
python3 scripts/submit_changes.py changes.json --lang he
python3 scripts/submit_changes.py changes.json --lang en
```

Configs:
- `config/he.json`: `raw_questions_he` -> `questions_he`, tracking `memory/trivia-refiner-processed.json`, artifacts `memory/trivia-consensus/he`
- `config/en.json`: `questions_raw_en` -> `questions_en`, tracking `memory/trivia-refiner-en-processed.json`, artifacts `memory/trivia-consensus/en`

Compatibility:
- Hebrew cron wrapper calls `run_batch.py --lang he`
- English cron wrapper calls `run_batch.py --lang en`
- The old English skill wrapper delegates to this unified runner with `--lang en`

**Current mode:** Auto-submit only clean questions with score **7+**. Send all flagged, reconstructed, fragile, or score ≤6 questions to Yinon before any DB write for those held items.

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

### Stage 2: REPHRASE + SEMI-AUTO UPDATE

When you reply `REPHRASE X-Y`:

1. **I pre-fact-check every raw question before rephrasing**
   - Validate the question premise, correct answer, all options, and ambiguity/currentness risk
   - Use internal knowledge for simple stable facts; use web verification when the fact is uncertain, disputed, current/time-sensitive, superlative-based, nickname-based, percentage/date-based, or otherwise suspicious
   - Classify the fact-check as `passed`, `web_verified`, `valid_with_rewording`, `uncertain`, or `failed`
2. **I rephrase** the questions (improve Hebrew phrasing, clarity) using the verified fact-check result
3. **I review options** (replace overly specific ones with plausible alternatives, and ensure no distractor is also correct)
4. **I assign categories & difficulty** (best match from available categories)
5. **I add a self-score (1-10)** for each refined question
6. **I include the fact-check data in the shared review artifact** so Alfred/main review can audit the premise, answer, options, notes, and sources
7. **I classify each question** as AUTO-SUBMIT or HOLD FOR REVIEW
8. **I auto-submit only clean AUTO-SUBMIT questions** with the `update_question` RPC/submit script
9. **I send Yinon only the held questions** plus a daily summary of how many were updated and how many need review
10. **Held questions are updated only after explicit approval/fixes**

**Critical:** Semi-auto approval applies only to clean high-confidence questions. Anything risky is still approval-first.

### Auto-submit eligibility

Auto-submit a question only when **all** are true:
- Final score is **7+** and Alfred/main agrees with the exact proposed final version
- No 🚩 warning
- No ⚠️ low-score line
- Not reconstructed from damaged/missing source text
- Not a fragile “כל התשובות נכונות” / “אף תשובה אינה נכונה” logic question
- No factual uncertainty, ambiguity, disputed wording, or outdated-fact risk
- Fact-check is visible in the batch artifact and is `passed` or `web_verified` with clean premise, correct answer, and option validation
- Correct answer is preserved and the option set is safe
- Alfred/main is a reviewer only. Do not ask Alfred/main for rewrites, improved wording, or replacement update fields; if Alfred/main returns a rewrite anyway, treat that question as rejected/unresolved and hold it for review

Hold for review when **any** are true:
- Final score is **≤6**, including after Alfred/main review
- Any 🚩 or ⚠️ appears
- Question was reconstructed from options/damaged source
- Question has “all/none of the above” fragile logic
- Fact requires external verification or feels uncertain
- Fact-check status is `uncertain` or `failed`, or fact-check data is missing/incomplete
- Any option is ambiguous, duplicated, accidentally correct, outdated, or source-dependent
- Options are weak, ambiguous, duplicated, or may create a second correct answer
- The model is not confident enough to submit unattended
- The refiner ranks it low and Alfred/main agrees the final version remains low/risky

Always send a daily summary, even when nothing is held:
- `Hebrew trivia: updated X questions automatically, held Y for review.`
- If Y > 0, include only the held question blocks for review.

Every held question should include a safe suggested replacement when one can be made without inventing unsupported facts. The suggestion must address the exact flag/rejection reason and include source URLs when web verification was needed.

If no safe suggestion can be made, say so and explain the blocker instead of forcing a weak rewrite.

---

## Step-by-Step Detail

### Fetch Stage

**Script:** `scripts/fetch_batch.py`
- Reads the highest existing ID from `questions_he`
- Fetches the next 10 raw questions from `raw_questions_he`, starting at `max(questions_he.id) + 1`
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
2. **Pre-fact-check each raw question before rephrasing**
   - Check the core premise, the stored correct answer, and every option
   - Confirm that exactly one answer is correct unless the original structure is explicitly `כל התשובות נכונות` / `אף תשובה אינה נכונה`
   - Detect outdated, source-dependent, ambiguous, disputed, exaggerated, or overly broad facts before spending effort on rewriting
   - Use web search/fetch for facts involving nicknames, superlatives, percentages, dates, “first/most/largest”, current facts, geography/history claims that feel uncertain, or anything the model cannot verify confidently from stable knowledge
   - If the fact is valid only with narrower wording, mark `valid_with_rewording` and use that safer wording in the rephrase
   - If the fact cannot be verified confidently, mark `uncertain` or `failed`, keep it out of auto-submit, and hold/skip according to severity
   - Preserve a compact fact-check block in the output/JSON for Alfred/main review; do not keep the evidence hidden inside the trivia manager
3. **Rephrase each question** in natural Hebrew
   - Keep question meaning identical
   - Improve phrasing for clarity
   - Hebrew only (no English, no translations)
   - If the source question is damaged/missing but the options and correct answer exist, flag it and try to reconstruct a sensible question from that context
   - If reconstruction is plausible, include the reconstructed question in the batch with a 🚩 warning and a low confidence score
   - If no good question can be inferred safely, skip it; do not invent a weak question just to fill the batch
   - True/false questions are valid when Option 1/2 are the only answers and Option 3/4 are null/empty; do **not** mark them damaged just because they have only two answers
4. **Review wrong options**
   - Preserve correctness over forced option changes
   - Rephrase the question text itself every time. Changing only the options does not satisfy the task
   - Try to change at least one wrong option per non-SKIP question when a clearly safe replacement exists
   - Use the fact-check result to ensure every distractor is actually wrong for the final wording
   - For true/false questions, preserve the two-answer structure (`נכון`/`לא נכון`) and leave Option 3/4 null/empty; do not invent extra distractors
   - REPLACE if too specific (unique names, niche references, copyrighted content) and the replacement is clearly wrong for this exact question
   - KEEP if generic (common cities, well-known figures, general concepts)
   - Verify the replacement does NOT create a second correct answer and does NOT make the question ambiguous
   - Do not count typo-only or punctuation-only cleanup as a meaningful option refresh
   - For "NOT" / outsider questions, keep the in-group options intact unless an option is clearly broken and must be replaced with another in-group example
   - For "כל התשובות נכונות" / "אף תשובה אינה נכונה" structures, prefer rephrasing only the question stem and keep the options + correct answer unchanged when edits could break the logic
   - NEVER replace with correct answer
5. **Assign category & difficulty**
   - Best matching category ID
   - Difficulty: easy/medium/hard
6. **Add self-score**
   - Score every refined question from 1-10
   - Any 🚩 warning or unresolved concern must score below 5
   - Above 5 = confident, solid result with no warning note
   - If below 5, add a short reason line
7. **Format with template**, including the fact-check block
8. **Final safety check**
   - Re-check that the final wording still matches the verified fact
   - Re-check that the final options have exactly one valid answer, unless the intentional answer is `כל התשובות נכונות` / `אף תשובה אינה נכונה`
   - If the final rewrite changes the factual claim, repeat the relevant fact-check before submission
9. **Auto-submit eligible clean questions; send only held questions for review with a summary**

**Template format:**
```
ID 203
🔴 [original question]
[opt1] | [opt2] | [opt3] | [opt4] | ✓ [correct answer]

🟢 [rephrased question]
[opt1] | [opt2] | [opt3] | [opt4] | ✓ [correct answer]
🔎 Fact-check: [passed/web_verified/valid_with_rewording/uncertain/failed]
Premise: [valid/invalid/ambiguous] | Answer: [verified/unverified] | Options: [all safe / issue]
Note: [short reason; include source URL(s) if web-verified]
📁 Category (ID) | ⚡ difficulty | 🎯 score/10

⚠️ דירוג נמוך — [reason]   # only when score < 5

---

[repeat for all 10 questions]

Summary:
Hebrew trivia: updated X questions automatically, held Y for review.

[If Y > 0, include only held question blocks here]

⏸️ For held questions, reply:
   APPROVE HELD
or:
   FIXES [describe changes needed]
```

### Fact-check block required in review artifacts

Every processed question must include a compact fact-check block in the batch output/JSON so the trivia manager and Alfred/main review see the same evidence:

```json
"fact_check": {
  "status": "passed | web_verified | valid_with_rewording | uncertain | failed",
  "premise": "valid | invalid | ambiguous",
  "correct_answer": "verified | unverified | disputed",
  "options": {
    "Option 1": "wrong | correct | ambiguous",
    "Option 2": "wrong | correct | ambiguous",
    "Option 3": "wrong | correct | ambiguous | null",
    "Option 4": "wrong | correct | ambiguous | null"
  },
  "notes": "Short reason; explain safer wording if status is valid_with_rewording.",
  "sources": ["URL(s) when web-checked"]
}
```

Before auto-submit, run a final safety check against this block:
- The final wording must still match the verified fact
- Exactly one option must be correct unless the intentional structure is `כל התשובות נכונות` / `אף תשובה אינה נכונה`
- If the rewrite changes the factual claim, repeat the relevant fact-check
- If web verification was needed but sources are weak or absent, hold for review

---

### Held-review safe suggestions

When a question is held because Alfred/main rejected it, marked it unresolved, or the refiner scored it low/risky:

- Do not ask Alfred/main to rewrite it. The refiner may create a separate `safe_suggestion` for Yinon after the reject/unresolved decision.
- The `safe_suggestion` must address the original flag:
  - unsafe distractor → replace with clearly wrong distractors of the same type
  - current/source-dependent wording → reframe to a stable verified fact
  - disputed origin/superlative/date → ask a narrower, better-sourced fact
  - damaged premise → reconstruct only if the answer/options make one safe question obvious
- Use web verification for unstable, disputed, current, origin, political, legal, medical, superlative, or celebrity-family facts.
- Include compact evidence with source URLs in the held-review output when web was used.
- Do not submit a `safe_suggestion` automatically. It is for Yinon approval only unless he explicitly approves updating the DB.
- If Yinon approves, submit the approved version through `submit_changes.py --lang he` and verify `questions_he`.

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
| **Auto-submit only clean 7+ questions** | Yinon approved semi-auto mode, but only for low-risk high-confidence items |
| **Hold risky questions for review** | Flags, low scores, reconstruction, fragile logic, or uncertainty still require approval |
| **Always send a daily summary** | Yinon should know how many questions were updated even if none were flagged |
| **Both rephrasing & review happen before sending** | User sees the finished product, not the work-in-progress |
| **Track all changes** | Maintain history in tracking file; do not use it for next-batch selection |
| **Pre-fact-check before rephrasing** | The verified fact should guide the rewrite, not merely block submission at the end |
| **Fact-check premise, answer, and all options** | A question is unsafe if a distractor is also correct, ambiguous, duplicated, outdated, or source-dependent |
| **Share fact-check evidence with Alfred/main review** | The manager must include compact status, notes, option validation, and sources so the review layer can audit it |
| **Use web verification when confidence is not high** | Nicknames, superlatives, percentages, current facts, dates, and disputed claims need external checking before auto-submit |
| **Reserve SKIP for truly broken questions** | Weak, ambiguous, or debatable questions should get a 🚩 note, not automatic SKIP |
| **Try to recover damaged questions from options** | If the stem is missing/corrupt but options + correct answer reveal the likely question, include it with a 🚩 warning and low score; skip only when no good reconstruction is possible |
| **Allow true/false questions** | A question with only `נכון`/`לא נכון` and null/empty Option 3/4 is valid; keep it as two-answer, do not skip or pad with fake options |
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
5. Updates tracking file for audit/history only; the next batch is selected from `questions_he`
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
