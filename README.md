# trivia-refiner

An [OpenClaw](https://openclaw.ai) agent skill that automates the improvement of Hebrew trivia questions through a multi-stage AI pipeline.

## What it does

1. **Fetches** a batch of raw questions from a Supabase database
2. **Rephrases** them in natural Hebrew using Gemini Flash
3. **Reviews** the rephrasing and validates options with Claude Sonnet
4. **Categorises** questions and assigns difficulty (easy / medium / hard)
5. **Presents** all changes to the user for approval
6. **Submits** approved changes back to the database
7. **Tracks** which question IDs have already been refined — no double-processing

## Folder structure

```
trivia-refiner/          ← skill root (this repo)
├── trivia-refiner/      ← OpenClaw skill package
│   ├── SKILL.md         ← skill descriptor (picked up by OpenClaw)
│   ├── scripts/
│   │   ├── refine_questions.py   ← fetch & display questions
│   │   ├── submit_changes.py     ← PATCH approved changes to DB
│   │   └── tracking.py           ← processed-ID tracker
│   └── references/
│       └── workflow.md           ← category list, DB schema notes
├── README.md            ← you are here
├── .gitignore
└── LICENSE
```

## Setup

### 1. Clone

```bash
git clone https://github.com/yinon-alfred-openClaw/trivia-refiner.git
# Place the inner trivia-refiner/ folder inside your OpenClaw skills directory:
# ~/.openclaw/workspace/skills/trivia-refiner/
```

### 2. Credentials

Create `~/.openclaw/workspace/memory/supabase-creds.json`:

```json
{
  "url": "https://xxxx.supabase.co",
  "key": "your-service-role-key"
}
```

### 3. Run

```bash
python3 skills/trivia-refiner/scripts/refine_questions.py
```

Or just ask Alfred: **"refine trivia questions"**.

## Tracking

Processed question IDs are stored in:

```
~/.openclaw/workspace/memory/trivia-refiner-processed.json
```

This file is **gitignored** (it's local runtime state, not part of the skill code).

Check status anytime:

```bash
python3 skills/trivia-refiner/scripts/tracking.py
```

## Requirements

- Python 3.8+
- OpenClaw with access to `google/gemini-2.5-flash` and `claude-sonnet`
- Supabase project with `Questions` and `trivia_categories` tables

## License

MIT
