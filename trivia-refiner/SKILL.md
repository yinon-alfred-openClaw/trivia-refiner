---
name: trivia-refiner
description: "Refine trivia questions by rephrasing with Gemini Flash, reviewing with Sonnet, assigning categories and difficulty levels, and submitting approved changes directly to the Supabase database. Use when you need to: (1) Process a batch of 10 trivia questions at once, (2) Improve Hebrew phrasing and option quality, (3) Auto-categorize questions and assess difficulty, (4) Review all changes before submission, (5) Update questions in the questions database."
---

# Trivia Refiner

Automate the improvement of trivia questions through a multi-stage pipeline: fetch raw questions, rephrase them naturally, regenerate incorrect options, review for quality, categorize, and submit approved changes.

## Quick Start

### 1. Initiate the Refinement Pipeline

```bash
python3 skills/trivia-refiner/scripts/refine_questions.py
```

This will:
- Fetch 10 questions from the database
- Display them with options and categories
- Show available category IDs for reference

### 2. Process with Agents (Parallel)

For each question, spawn two concurrent subagent tasks:

**Task A: Rephrase with Gemini Flash**
- Take the original Hebrew question
- Rephrase it for clarity and naturalness
- Regenerate 2-3 of the incorrect options (keep the correct answer unchanged)

**Task B: Review with Sonnet**
- Check the rephrasing for grammar and naturalness
- Validate that options are plausible and clearly distinguishable
- Flag any issues

**Task C: Categorize with Sonnet**
- Choose the best category ID from `trivia_categories`
- Assign difficulty: "easy", "medium", or "hard"

### 3. Review & Approve

Compile all changes into a single table showing:
- ID | Original Question | Rephrased Question | New Options | Category ID | Difficulty

Present to user with: **"Do you approve these changes? (yes/no)"**

### 4. Submit to Database (If Approved)

If user approves, update each question:
```python
{
  "Question": "rephrased question text",
  "Option 1": "new option",
  "Option 2": "new option",
  "Option 3": "new option",
  "Option 4": "new option",
  "category_id": 27,
  "difficulty": "easy"
}
```

Note: `Category` (original text), `Correct Answer` remain unchanged.

## How It Works

### Stage 1: Fetch
Run the fetch script to pull 10 questions and display them.

### Stage 2: Rephrase (Gemini Flash)
Spawn a subagent with:
```
model: "google/gemini-2.5-flash"
task: "Rephrase this Hebrew trivia question for clarity and naturalness. Regenerate 2-3 incorrect options but keep the correct answer the same."
```

### Stage 3: Review (Sonnet)
Spawn a subagent with:
```
model: "sonnet"
task: "Review the rephrased question. Check: (1) Hebrew grammar/naturalness, (2) Options are plausible, (3) Correct answer is still correct. Suggest any fixes needed."
```

### Stage 4: Categorize (Sonnet)
Spawn a subagent with:
```
model: "sonnet"
task: "Choose the best category ID from the trivia_categories list. Assign difficulty: easy/medium/hard. Explain your choices."
```

### Stage 5: Compile & Display
Format all results into a table and ask for approval.

### Stage 6: Submit
If approved, use `submit_changes.py` to PATCH each question to the database.

## Scripts

### `scripts/refine_questions.py`
Fetch 10 questions and display them with metadata.

**Usage:**
```bash
python3 scripts/refine_questions.py
```

**Output:**
- Lists 10 questions with ID, original text, options, and correct answer
- Shows available categories for reference

### `scripts/submit_changes.py`
Submit approved changes to the database.

**Usage:**
```bash
python3 scripts/submit_changes.py changes.json
```

**Input file format (JSON array):**
```json
[
  {
    "id": 1,
    "Question": "rephrased question",
    "Option 1": "new option",
    "Option 2": "new option",
    "Option 3": "new option",
    "Option 4": "new option",
    "category_id": 27,
    "difficulty": "easy"
  },
  ...
]
```

## Key Details

### Credentials
Reads from: `~/.openclaw/workspace/memory/supabase-creds.json`

Must contain:
```json
{
  "url": "https://xxxx.supabase.co",
  "key": "sb_secret_xxxxx"
}
```

### Categories
Fetched from `trivia_categories` table. Common IDs:
- 9: ידע כללי (General Knowledge)
- 27: בעלי חיים (Animals)
- 22: גאוגרפיה (Geography)
- 23: היסטוריה (History)

See `references/workflow.md` for full category list.

### Database Schema
See `references/workflow.md` for detailed field descriptions and examples.

## Best Practices

1. **Always review before submitting** — The approval step is your safeguard
2. **Check Hebrew quality** — Sonnet should catch awkward phrasing
3. **Validate options** — Ensure wrong options are plausible but clearly incorrect
4. **Consistent difficulty assessment** — Use Sonnet consistently across all 10
5. **Keep correct answers unchanged** — Never modify `Correct Answer` field

## Troubleshooting

**Script fails with credential error:**
- Ensure `memory/supabase-creds.json` exists and is readable
- Check that it contains `url` and `key` fields

**Subagent fails to spawn:**
- Verify model name is correct (`google/gemini-2.5-flash` or `sonnet`)
- Check that the model is available in your OpenClaw config

**Database update fails:**
- Verify question ID exists in the database
- Check that `category_id` matches a real category
- Ensure `difficulty` is one of: "easy", "medium", "hard"

## Workflow Reference

For detailed workflow documentation, see `references/workflow.md`.
