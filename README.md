# Groww Pulse Agent 🟢

> Autonomous AI agent that ingests Groww app reviews weekly and delivers
> a structured pulse report every Monday at 09:00 IST.

## What It Does

1. **Ingests** English reviews from iOS App Store + Google Play Store
2. **Cleans** reviews — language filter, PII strip, dedup, noise removal
3. **Clusters** into max 5 themes using BERTopic + Groq Llama 3
4. **Generates** a Weekly Pulse Report (Markdown + HTML, ≤250 words)
5. **Delivers** via Google Docs MCP + Gmail MCP every Monday 09:00 IST
6. **Archives** into a 12-week rolling quarterly store

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.13 (Windows compatible) |
| Embeddings | BAAI/bge-small-en-v1.5 → all-MiniLM-L6-v2 → paraphrase-MiniLM-L3-v2 |
| Clustering | BERTopic (≥50 reviews) / K-Means fallback |
| LLM Labeling | Groq Llama 3 (llama3-8b-8192) |
| Vector Store | ChromaDB (local, persistent) |
| Database | SQLite (dev) / Postgres (prod) |
| Scheduler | APScheduler — Monday 09:00 IST |
| Docs | Google Docs MCP (drivemcp.googleapis.com) |
| Email | Gmail MCP (gmailmcp.googleapis.com) |
| Dashboard | Flask + vanilla JS (http://localhost:5000) |

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 2. Install Node dependencies (for Android scraper)
npm install

# 3. Copy and fill environment variables
copy .env.example .env
# Edit .env with your API keys

# 4. Initialize database + ChromaDB
python scripts/setup_db.py

# 5. Verify environment
python scripts/check_env.py

# 6. Run the full pipeline once
python scripts/manual_run.py full

# 7. Start the dashboard
python dashboard/app.py
# Open http://localhost:5000
```

## How to Generate Reports

```bash
# Generate weekly report (latest run)
python scripts/manual_run.py weekly-report

# Generate weekly report for specific week
python scripts/manual_run.py weekly-report --week 17 --year 2025

# Generate quarterly report (all 12 weeks)
python scripts/manual_run.py quarterly

# Ingest reviews only (no AI)
python scripts/manual_run.py ingest --days 7

# Run full pipeline manually
python scripts/manual_run.py full
```

## Report Outputs

| File | Description |
|------|-------------|
| data/archive/groww_week_WW_YYYY_pulse.md | Weekly report (Markdown) |
| data/archive/groww_week_WW_YYYY_pulse.html | Weekly report (HTML, printable) |
| data/archive/email_drafts/email_draft_week_WW_YYYY.html | Email draft HTML |
| data/archive/groww_qN_YYYY_quarterly_report.md | 12-week aggregate |
| data/archive/groww_reviews_qN_YYYY.csv | Redacted review archive |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| GROQ_API_KEY | ✅ | Free at console.groq.com |
| GOOGLE_CLIENT_ID | ✅ | Google OAuth client ID |
| GOOGLE_CLIENT_SECRET | ✅ | Google OAuth client secret |
| GOOGLE_REFRESH_TOKEN | ✅ | Google OAuth refresh token |
| RECIPIENT_LIST | ✅ | Email recipients (comma-separated) |
| AUTO_SEND | ❌ | true to auto-send (default: false) |
| ENABLE_EXTERNAL_SEND | ❌ | true for external domains (default: false) |
| DB_URL | ❌ | Database URL (default: sqlite:///data/groww_pulse.db) |
| CHROMADB_PATH | ❌ | ChromaDB path (default: ./data/chroma) |

## How to Re-run for a New Week

```bash
# The scheduler runs automatically every Monday 09:00 IST.
# To start the scheduler:
python scheduler/cron_runner.py

# To trigger manually any time:
python scripts/manual_run.py full

# After pipeline runs, generate the report:
python scripts/manual_run.py weekly-report
```

## Scheduler (Auto Mode)

```bash
# Start on Windows (keep PowerShell open)
python scheduler/cron_runner.py

# Or run in background
Start-Process python -ArgumentList "scheduler/cron_runner.py" -WindowStyle Hidden
```

## Dashboard

```bash
python dashboard/app.py
```

Open http://localhost:5000 — shows:
- Live run status and stats
- Theme cards with urgency scores
- 12-week history table
- Download Report button
- Trigger New Run button

## Running Tests

```bash
python -m pytest tests/ -v --tb=short
python scripts/check_secrets.py
python scripts/check_env.py
```

## Project Structure
