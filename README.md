# trivia-refiner

An [OpenClaw](https://openclaw.ai) skill/repo for refining Hebrew trivia questions from a Supabase quiz database, with explicit user approval before any database writes.

## Current behavior

The current live flow is simpler than the older docs implied:

1. **Fetches** the next batch of raw questions from `raw_questions_he`
2. **Fetches** available categories via the `get_all_categories` RPC
3. **Builds a large instruction prompt** containing:
   - the raw questions
   - option-review rules
   - category and difficulty assignment rules
   - formatting instructions
4. **Prints that prompt for Alfred to process in-session**
5. **Waits for explicit user approval** before any submission step
6. **Submits approved changes** back to Supabase using `submit_changes.py`
7. **Tracks processed IDs** in a local JSON file to avoid duplicate work

## Important correction: model usage

Older docs and comments mention a multi-model pipeline such as:
- Gemini Flash for rephrasing
- Claude Sonnet for review/categorization

That is **not how the active `scripts/run_batch.py` currently works**.

### What actually happens now

- `scripts/run_batch.py` does **not** call Gemini or Sonnet directly.
- Its `call_sonnet()` function is currently a passthrough that returns `None`.
- Instead, the script prints the assembled prompt and expects **Alfred in the current OpenClaw session** to do the rephrasing/review work.

So the effective model is:
- **whatever model Alfred is currently running on in that session**

If Alfred is running on `openai-codex/gpt-5.4`, then that is the model doing the work.

## Active scripts

These are the top-level scripts currently present and relevant in this repo:

- `scripts/run_batch.py`
  - Main current batch runner
  - Auto mode: picks the next 10 questions after the highest tracked ID
  - Manual mode: accepts a range like `193-202`
  - Fetches categories
  - Builds and prints the full prompt for Alfred
  - In auto mode, increments `batch_count` in the tracking file

- `scripts/submit_changes.py`
  - Submits approved changes to Supabase
  - Updates **two tables**:
    - `raw_questions_he`
    - `questions_he`
  - Marks success/failure in the tracking file

- `scripts/tracking.py`
  - Reads/writes `~/.openclaw/workspace/memory/trivia-refiner-processed.json`
  - Tracks processed IDs, statuses, and metadata

- `scripts/process_batch.py`
  - Utility that fetches questions and categories and prints raw data
  - Useful for inspection/debugging
  - Not the main live runner

- `scripts/refine_questions.py`
  - Older fetch/display utility
  - Still present, but appears to be an earlier workflow helper rather than the main entrypoint

- `scripts/assess_quality.py`
  - Heuristic quality checker for a prepared JSON batch of changes
  - Not part of the main live automation path

## Current workflow in practice

### Automatic / cron-oriented path

Run:

```bash
python3 scripts/run_batch.py
```

What it does:
- reads credentials from `~/.openclaw/workspace/memory/supabase-creds.json`
- reads tracking from `~/.openclaw/workspace/memory/trivia-refiner-processed.json`
- fetches the next 10 questions after the highest processed ID
- fetches category IDs/names from Supabase
- prints a structured prompt for Alfred to process manually/in-session
- increments `batch_count`

What it does **not** do:
- it does not directly call Gemini
- it does not directly call Claude Sonnet
- it does not automatically write changes to the database

### Manual range path

Run:

```bash
python3 scripts/run_batch.py 193-202
```

What it does:
- fetches exactly that ID range
- fetches categories
- prints the prompt for Alfred to process in-session
- does **not** enforce the auto batch limit

### Submission path

After a reviewed/approved JSON changes file exists:

```bash
python3 scripts/submit_changes.py changes.json
```

Optional dry run:

```bash
python3 scripts/submit_changes.py changes.json --dry-run
```

Submission behavior:
- validates required fields
- PATCHes `raw_questions_he`
- inserts/upserts into `questions_he`
- records status in tracking

## Data files

### Credentials

Expected at:

```bash
~/.openclaw/workspace/memory/supabase-creds.json
```

Format:

```json
{
  "url": "https://xxxx.supabase.co",
  "key": "your-service-role-key"
}
```

### Tracking file

Stored at:

```bash
~/.openclaw/workspace/memory/trivia-refiner-processed.json
```

Used for:
- highest processed ID
- processed/refined/failed entries
- batch count in the current auto workflow

## Repo layout notes

This repository currently contains **older nested copies** of the skill/package structure, including:

- `trivia-refiner/SKILL.md`
- `trivia-refiner/scripts/fetch_batch.py`
- `trivia-refiner/scripts/rephrase_batch.py`
- `trivia-refiner/scripts/update_batch.py`

Those files describe an older staged workflow and some older model assumptions.

For understanding the **current active behavior**, treat these top-level files as primary:
- `SKILL.md`
- `scripts/run_batch.py`
- `scripts/submit_changes.py`
- `scripts/tracking.py`

## Current folder structure

```text
trivia-refiner/
├── README.md
├── SKILL.md
├── scripts/
│   ├── assess_quality.py
│   ├── process_batch.py
│   ├── refine_questions.py
│   ├── run_batch.py
│   ├── submit_changes.py
│   └── tracking.py
└── trivia-refiner/
    ├── SKILL.md
    ├── references/
    │   └── workflow.md
    └── scripts/
        ├── fetch_batch.py
        ├── rephrase_batch.py
        └── update_batch.py
```

## Requirements

- Python 3.8+
- OpenClaw / Alfred session access
- Supabase service-role credentials for the quiz database

## Recommended way to think about this skill today

This is currently **a prompt-orchestration + approval + submission workflow**, not a self-contained multi-model automation pipeline.

The heavy lifting happens in the active Alfred session after `run_batch.py` prints the prompt.

## License

MIT
