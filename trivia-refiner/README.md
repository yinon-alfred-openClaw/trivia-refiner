# trivia-refiner

An [OpenClaw](https://openclaw.ai) skill for refining Hebrew trivia questions from a Supabase quiz database, with user approval before any database updates.

## What it does now

The current workflow is:

1. Fetch a batch of questions from `raw_questions_he`
2. Fetch available categories from Supabase
3. Build a detailed prompt with rephrasing, option-review, categorization, and formatting rules
4. Print that prompt for Alfred to handle in the current session
5. Wait for user review and approval
6. Submit approved changes back to the database
7. Track processed question IDs locally

## Important model note

This skill does **not currently call a hardcoded model directly** from `run_batch.py`.

Instead, `run_batch.py` prints the prompt and the actual refinement work is done by **Alfred in the current OpenClaw session**.

So the effective model is simply:
- **whatever model Alfred is currently running**

## Main scripts

### `scripts/run_batch.py`
Main entrypoint.

- No args: fetch next 10 questions after the highest tracked ID
- With a range like `193-202`: fetch that exact range
- Fetches categories
- Prints the full prompt for Alfred to process in-session
- Does **not** directly update the database

### `scripts/submit_changes.py`
Writes approved changes back to Supabase.

- Validates required fields
- Updates `raw_questions_he`
- Upserts into `questions_he`
- Records success/failure in tracking

### `scripts/tracking.py`
Manages local runtime tracking.

Tracking file:

```bash
~/.openclaw/workspace/memory/trivia-refiner-processed.json
```

Used for:
- processed IDs
- refined/failed status
- highest processed ID
- batch count

## How to run it

### Automatic / next batch

```bash
python3 scripts/run_batch.py
```

### Specific range

```bash
python3 scripts/run_batch.py 193-202
```

### Submit approved changes

```bash
python3 scripts/submit_changes.py changes.json
```

### Dry run submission

```bash
python3 scripts/submit_changes.py changes.json --dry-run
```

## What someone should know before using it

- It is an **approval-based workflow** — database writes should only happen after explicit approval
- The refinement logic currently happens **in the Alfred session**, not inside a hardcoded Gemini/Claude pipeline
- It depends on Supabase credentials stored at:

```bash
~/.openclaw/workspace/memory/supabase-creds.json
```

Expected format:

```json
{
  "url": "https://xxxx.supabase.co",
  "key": "your-service-role-key"
}
```

- It updates two tables when submitting approved changes:
  - `raw_questions_he`
  - `questions_he`

## In one sentence

This skill is currently a **prompt-driven, human-approved trivia refinement workflow** that uses Alfred’s current session model for the actual question processing.

## License

MIT
