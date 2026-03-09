# Trivia Refiner

AI-powered trivia question refinement skill for OpenClaw. Automatically rephrase questions, regenerate options, review quality, assign categories, and update Supabase.

## Features

- **Rephrase with Gemini 2.5 Flash** — Natural Hebrew phrasing and option regeneration
- **Review with Claude Sonnet** — Grammar checking, option quality validation, difficulty assessment
- **Categorize automatically** — Match to 24+ trivia categories by ID
- **Track processed questions** — Local tracking prevents re-processing the same questions
- **Human approval gate** — Review and approve all changes before updating database
- **Validation & error handling** — Field validation, dry-run mode, error tracking

## Quick Start

### 1. Prerequisites

- OpenClaw installed and configured
- Access to Supabase database with `Questions` and `trivia_categories` tables
- Supabase credentials file at `~/.openclaw/workspace/memory/supabase-creds.json`:

```json
{
  "url": "https://xxxx.supabase.co",
  "key": "sb_secret_xxxxx"
}
```

### 2. Clone Repository

```bash
git clone https://github.com/yinon-alfred-openClaw/trivia-refiner.git
cd trivia-refiner
```

### 3. Fetch Unprocessed Questions

```bash
python3 scripts/refine_questions.py
```

This will:
- Display tracking stats (how many questions already refined)
- Fetch 10 unprocessed questions starting from last edited ID + 1 (cursor-based)
- Show all questions with options and available categories

**How cursor-based fetching works:**
- First run: Fetches questions starting from ID 1
- After editing 1-10: Next run fetches questions starting from ID 11
- Efficient: Only fetches new questions, no API waste

### 4. Process & Approve

(Implementation: Orchestration script coming soon)

Workflow will:
1. Spawn Gemini Flash subagent to rephrase each question
2. Spawn Sonnet subagent to review quality
3. Spawn Sonnet subagent to assign category ID and difficulty
4. Compile results into an approval table
5. Prompt for user approval

### 5. Submit Approved Changes

```bash
python3 scripts/submit_changes.py changes.json
```

Or with dry-run:
```bash
python3 scripts/submit_changes.py changes.json --dry-run
```

## File Structure

```
trivia-refiner/
├── README.md                    # This file
├── SKILL.md                     # OpenClaw skill documentation
├── .gitignore                   # Git ignore rules
├── scripts/
│   ├── refine_questions.py      # Fetch unprocessed questions
│   ├── submit_changes.py        # Submit approved changes to DB
│   ├── tracking.py              # Track processed question IDs
│   └── process_questions.py     # [TODO] Orchestrate pipeline
├── references/
│   └── workflow.md              # Detailed workflow documentation
└── examples/
    └── sample_changes.json      # Example input format
```

## Cursor-Based Fetching

Instead of fetching questions 1-30 every run and filtering, this skill uses **cursor-based pagination**:

### How it works

1. **Read cursor:** Get the last edited ID from the tracking file
2. **Fetch:** Query `SELECT * FROM Questions WHERE id > {last_edited_id} LIMIT 10`
3. **Process:** Work on the 10 new questions
4. **Update cursor:** Log the highest ID processed in the tracking file

### Examples

| Run | Last Edited ID | Fetches | Result |
|-----|---|---|---|
| 1st | 0 (none) | `id > 0 LIMIT 10` | Questions 1-10 |
| 2nd | 10 | `id > 10 LIMIT 10` | Questions 11-20 |
| 3rd | 20 | `id > 20 LIMIT 10` | Questions 21-30 |
| 100th | 990 | `id > 990 LIMIT 10` | Questions 991-1000 |

### Benefits

✅ **Efficient:** Only 1 API call per run, fetches exactly what's needed
✅ **No waste:** Never re-fetches old questions
✅ **Linear:** Natural progression through the database
✅ **Scalable:** Works the same whether you have 100 or 10,000 questions

---

## Tracking System

Questions are tracked locally in `~/.openclaw/workspace/memory/trivia-refiner-processed.json`:

**Status values:**
- `"refined"` — Successfully updated in database
- `"failed"` — Attempted but encountered an error

**Example tracking file:**
```json
{
  "last_updated": "2026-03-08T10:10:00Z",
  "version": "1",
  "processed": [
    {
      "id": 1,
      "refined_at": "2026-03-08T09:53:12Z",
      "status": "refined",
      "difficulty": "easy",
      "category_id": 27
    },
    {
      "id": 2,
      "refined_at": "2026-03-08T10:02:45Z",
      "status": "failed",
      "error": "Invalid category_id"
    }
  ]
}
```

Processed questions are automatically skipped on the next run.

## Workflow

### Multi-Stage Pipeline

1. **Fetch** (manual, cursor-based)
   ```bash
   python3 scripts/refine_questions.py
   ```
   - Reads last edited ID from tracking file
   - Fetches next 10 questions using `id > last_edited_id`
   - Displays unprocessed questions and available categories
   - Efficient: No API waste, no re-fetching old questions

2. **Rephrase** (automated, Gemini Flash)
   - Rephrase question naturally in Hebrew
   - Regenerate 2-3 incorrect options (keep correct answer)

3. **Review** (automated, Sonnet)
   - Check Hebrew grammar and naturalness
   - Validate options are plausible and distinguishable
   - Flag issues if needed

4. **Categorize** (automated, Sonnet)
   - Choose best category ID from `trivia_categories`
   - Assign difficulty: `"easy"`, `"medium"`, or `"hard"`

5. **Approve** (manual)
   - Review compiled changes in table format
   - Approve or reject all changes

6. **Submit** (manual)
   ```bash
   python3 scripts/submit_changes.py changes.json
   ```
   - Validates all fields
   - Updates database
   - Tracks success/failure locally

## Configuration

| Setting | Location | Required |
|---------|----------|----------|
| Supabase URL | `~/.openclaw/workspace/memory/supabase-creds.json` | Yes |
| Supabase Key | `~/.openclaw/workspace/memory/supabase-creds.json` | Yes |
| Tracking File | `~/.openclaw/workspace/memory/trivia-refiner-processed.json` | Auto-created |

## Data Validation

`submit_changes.py` validates each change before submission:

✅ **Required fields:**
- `id` (question ID)
- `Question` (rephrased question text)
- `Option 1`, `Option 2`, `Option 3`, `Option 4` (all 4 options)
- `category_id` (positive integer, must match a real category)
- `difficulty` (one of: `"easy"`, `"medium"`, `"hard"`)

✅ **Preserved fields (not updated):**
- `Category` (original category text)
- `Correct Answer` (kept unchanged)

## Database Schema

### Questions Table

```json
{
  "id": 1,
  "Category": "כלבים",
  "Question": "מהי ארץ המקור של כלב הגולדן רטריבר?",
  "Option 1": "צ'ילה",
  "Option 2": "צרפת",
  "Option 3": "סקוטלנד",
  "Option 4": "נורווגיה",
  "Correct Answer": "סקוטלנד",
  "category_id": 27,
  "difficulty": "easy"
}
```

### Categories Table

```json
{
  "id": 27,
  "name": "בעלי חיים"
}
```

Common categories:
- 9: ידע כללי (General Knowledge)
- 27: בעלי חיים (Animals)
- 22: גאוגרפיה (Geography)
- 23: היסטוריה (History)

## Usage Examples

### Fetch and check what would be processed

```bash
python3 scripts/refine_questions.py
```

Output shows:
- How many questions already refined
- 10 unprocessed questions with all details
- Available category IDs

### Dry-run submission

```bash
python3 scripts/submit_changes.py changes.json --dry-run
```

Shows what would be updated without actually touching the database.

### Check processing stats

Create a simple script:
```python
from scripts.tracking import get_stats
stats = get_stats()
print(f"Refined: {stats['refined']}, Failed: {stats['failed']}")
```

## Error Handling

**Validation errors:**
- Missing required fields → Listed before any updates
- Invalid difficulty → Must be "easy", "medium", "hard"
- Invalid category_id → Must be positive integer

**Database errors:**
- Connection failures → Exception message displayed
- RLS violations → Error details logged to tracking file
- Partial failures → Successful updates are tracked separately

**Tracking:**
- All successes logged with timestamp and metadata
- All failures logged with error message and details
- Check `trivia-refiner-processed.json` for audit trail

## Development

### Project Structure

This skill follows OpenClaw skill guidelines:

- **SKILL.md** — Skill documentation for OpenClaw system
- **scripts/** — Executable Python modules (deterministic, reusable)
- **references/** — Detailed documentation (loaded as-needed)
- **examples/** — Sample data and usage patterns

### Adding Features

1. Keep scripts focused and reusable
2. Update `tracking.py` if adding new processing stages
3. Test with `--dry-run` before production use
4. Document changes in SKILL.md and references/

## Future Enhancements

- [ ] `process_questions.py` — Master orchestration script
- [ ] Parallel subagent spawning for 10 questions
- [ ] Web UI for approval workflow
- [ ] Confidence scoring from reviewers
- [ ] CSV export before approval
- [ ] Rollback capability for failed submissions
- [ ] Multi-language support (not just Hebrew)

## Troubleshooting

### "Error loading credentials"
- Ensure `~/.openclaw/workspace/memory/supabase-creds.json` exists
- Check file contains valid `url` and `key` fields
- Verify file is readable: `cat ~/.openclaw/workspace/memory/supabase-creds.json`

### "No questions found"
- Verify Questions table exists in Supabase
- Check Supabase credentials have read access to the table
- Run a manual query: `curl -H "Authorization: Bearer <key>" https://<url>/rest/v1/Questions?limit=1`

### "All fetched questions have already been refined"
- Check `~/.openclaw/workspace/memory/trivia-refiner-processed.json`
- View the tracking file to see what's been processed
- This is normal behavior — the system prevents re-processing

### Submission fails with "Invalid category_id"
- Verify the category_id exists in `trivia_categories` table
- Fetch available categories: Run `python3 scripts/refine_questions.py` to see the list

## License

MIT

## Author

Alfred (Yinon's AI Assistant)
Built with OpenClaw
