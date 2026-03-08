# Trivia Refiner Workflow

## Overview

The Trivia Refiner skill processes trivia questions in a multi-stage pipeline:

1. **Fetch** — Pull 10 unprocessed questions from the database
2. **Rephrase** — Use Gemini Flash to rephrase questions and regenerate incorrect options
3. **Review** — Use Sonnet to review the changes for quality and correctness
4. **Categorize** — Assign proper category ID and difficulty level
5. **Approve** — Show all changes to the user for approval
6. **Submit** — If approved, update the database directly

## Stage Details

### Stage 1: Fetch Questions

```bash
python3 scripts/refine_questions.py
```

This fetches 10 questions and displays:
- Original question text (Hebrew)
- Original category
- All 4 options
- Correct answer
- Available categories list for reference

### Stage 2: Rephrase (Gemini Flash)

For each question, spawn a Gemini Flash subagent to:
- **Rephrase the question** for clarity and naturalness in Hebrew
- **Keep options 1-4 but regenerate 2-3 of the incorrect options** (not the correct one)

Input to Gemini:
```
Original question: [Hebrew text]
Original options: [all 4 with correct answer marked]
Task: Rephrase the question naturally. Keep the correct answer the same, but regenerate 2-3 of the wrong options to be plausible alternatives.
```

Output: Rephrased question + new options

### Stage 3: Review (Sonnet)

For each rephrased question, spawn a Sonnet subagent to:
- **Check Hebrew grammar and naturalness** — does the rephrase sound natural?
- **Validate options** — are the wrong options plausible? Are they still clearly wrong to someone who knows the answer?
- **Flag any issues** — suggest fixes if needed
- **Approve or suggest changes**

### Stage 4: Categorize & Assign Difficulty

Use Sonnet (same agent or fresh) to:
- **Choose the best category** from `trivia_categories` table (by ID)
- **Assign difficulty** — easy, medium, or hard based on question complexity

### Stage 5: Display for Approval

Format all changes as a table:

| ID | Original Question | Rephrased Question | Options | Category ID | Difficulty |
|----|---|---|---|---|---|
| 1 | ... | ... | 1. ... 2. ... 3. ... 4. ... | 27 | medium |
| 2 | ... | ... | ... | 15 | easy |
| ... | ... | ... | ... | ... | ... |

Ask: **"Approve all changes? (yes/no)"**

### Stage 6: Submit to Database

If approved, for each question, PATCH the database with:
- `Question` ← rephrased question text
- `Option 1`, `Option 2`, `Option 3`, `Option 4` ← updated options
- `category_id` ← category ID
- `difficulty` ← difficulty level
- `Category` ← original category (keep unchanged)
- `Correct Answer` ← correct answer (keep unchanged)

## Data Structure

### Questions Table

```
{
  "id": 1,
  "Category": "כלבים",  // Original category text (keep unchanged)
  "Question": "מהי ארץ המקור של כלב הגולדן רטריבר?",
  "Option 1": "צ'ילה",
  "Option 2": "צרפת",
  "Option 3": "סקוטלנד",
  "Option 4": "נורווגיה",
  "Correct Answer": "סקוטלנד",
  "category_id": 27,  // Foreign key to trivia_categories
  "difficulty": "easy"
}
```

### Categories Table

Fetch from `trivia_categories`:

```
{
  "id": 27,
  "name": "בעלי חיים"  // Animals in Hebrew
}
```

## Environment & Credentials

**Supabase credentials** are read from:
```
~/.openclaw/workspace/memory/supabase-creds.json
```

Format:
```json
{
  "url": "https://xxxx.supabase.co",
  "key": "sb_secret_xxxxx"
}
```

## Subagent Spawning

Use `sessions_spawn` with:

**Gemini Flash (rephrasing):**
```
runtime: "subagent"
model: "google/gemini-2.5-flash"
mode: "run"
```

**Sonnet (review & categorization):**
```
runtime: "subagent"
model: "sonnet"  // or "anthropic/claude-sonnet-4-6"
mode: "run"
```

Collect all responses, format them, and present for approval before submitting.

## Error Handling

- If any question fails Gemini rephrasing → Skip it, continue with others
- If any question fails Sonnet review → Show as "REVIEW REQUIRED" in approval table
- If user rejects changes → Display rejected questions and stop (no DB submission)
- If submission fails → Report which questions failed, allow retry
