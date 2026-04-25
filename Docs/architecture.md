# Groww Weekly Review Intelligence System — Architecture Document

**Version:** 1.0 | **Derived from:** problemstatement.md

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    GROWW PULSE ENGINE — E2E FLOW                    │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────┐ │
│  │  Phase 1  │──▶│  Phase 2  │──▶│  Phase 3  │──▶│  Phase 4 / 6    │ │
│  │ Ingestion │   │  Noise    │   │ AI Theme  │   │ Report + MCP    │ │
│  │           │   │  Mgmt     │   │  Engine   │   │ Delivery        │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────────┘ │
│       ▲                                              │              │
│       │              ┌──────────┐                    ▼              │
│       └──────────────│  Phase 5  │◀───────── Phase 9 Quarterly     │
│                      │ Scheduler │           Deliverables           │
│                      └──────────┘                                   │
│  Cross-cutting: Phase 0 (Setup) │ Phase 7 (Edge Cases) │           │
│                 Phase 8 (Security)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 0 — Project Setup & Folder Organization

### Purpose
Establish the project scaffold, environment configuration, and dependency baseline.

### Directory Architecture

```
groww-pulse/
├── ingestion/
│   ├── __init__.py
│   ├── ios_scraper.py          # app_store_reviews RSS feed client
│   ├── android_scraper.py      # google-play-scraper Node bridge
│   ├── csv_fallback.py         # pandas CSV loader
│   ├── language_filter.py      # langdetect + langid ensemble
│   ├── pii_stripper.py         # regex pass + spaCy NER pass
│   └── deduplicator.py         # SHA-256 cross-store dedup
│
├── storage/
│   ├── __init__.py
│   ├── models.py               # SQLAlchemy ORM (Review, RunLog)
│   ├── db.py                   # SQLite (dev) / Postgres (prod) engine
│   ├── vector_store.py         # ChromaDB client wrapper
│   └── csv_archive.py          # 12-week rolling CSV manager
│
├── ai/
│   ├── __init__.py
│   ├── embedder.py             # BAAI/bge-small-en-v1.5 (primary)
│   ├── clusterer.py            # BERTopic + K-Means fallback
│   ├── llm_labeler.py          # Groq API (Llama 3) structured JSON
│   ├── urgency_scorer.py       # Urgency 1–10 from LLM output
│   └── quote_selector.py       # PII-free representative quotes
│
├── report/
│   ├── __init__.py
│   ├── pulse_builder.py        # Weekly pulse note composer
│   ├── quarterly_builder.py    # 12-week aggregate report
│   ├── email_composer.py       # HTML email body generator
│   └── templates/
│       ├── pulse_template.j2
│       └── quarterly_template.j2
│
├── mcp/
│   ├── __init__.py
│   ├── gdocs_client.py         # Google Docs MCP integration
│   └── gmail_client.py         # Gmail MCP integration
│
├── scheduler/
│   ├── __init__.py
│   └── cron_runner.py          # APScheduler Monday 09:00 IST
│
├── tests/
│   ├── test_ingestion.py
│   ├── test_noise.py
│   ├── test_ai_pipeline.py
│   ├── test_edge_cases.py
│   └── test_security.py
│
├── data/
│   ├── raw/                    # .gitignored — transient store
│   ├── processed/              # Cleaned, PII-stripped reviews
│   └── archive/                # 12-week rolling CSV snapshots
│
├── .env.example                # Template (never real secrets)
├── .gitignore                  # raw/, .env, __pycache__
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

### Key Configuration (.env)

```env
GROQ_API_KEY=<key>
GOOGLE_OAUTH_CREDENTIALS=<path>
RECIPIENT_LIST=self@example.com
AUTO_SEND=false
DB_URL=sqlite:///data/groww_pulse.db
CHROMADB_PATH=./data/chroma
TIMEZONE=Asia/Kolkata
MAX_TOKENS=1000
```

### Acceptance Criteria
- All directories created and importable
- `.env.example` committed; `.env` gitignored
- `pip install -r requirements.txt` completes without errors
- Docker build succeeds

---

## Phase 1 — Data Ingestion

### Architecture

```
                    ┌─────────────────┐
                    │  Scheduler Trigger│
                    └────────┬────────┘
                             ▼
              ┌──────────────────────────┐
              │    Ingestion Orchestrator  │
              └──┬──────────┬──────────┬─┘
                 ▼          ▼          ▼
         ┌──────────┐ ┌──────────┐ ┌──────────┐
         │iOS Scraper│ │Android   │ │CSV       │
         │(RSS Feed) │ │Scraper   │ │Fallback  │
         └─────┬────┘ └─────┬────┘ └─────┬────┘
               └────────────┼────────────┘
                            ▼
                ┌────────────────────────┐
                │  Unified Review Schema  │
                │  → SQLite / Postgres    │
                └────────────────────────┘
```

### Review Schema

| Field | Type | Description |
|-------|------|-------------|
| `review_id` | STRING (PK) | SHA-256(store + original_id + date) |
| `store` | ENUM | `ios` or `android` |
| `rating` | INT | 1–5 |
| `title` | TEXT | Review title (nullable) |
| `text` | TEXT | Review body |
| `date` | DATETIME | Review posted date |
| `app_version` | STRING | App version at review time |
| `language_detected` | STRING | ISO 639-1 code |
| `language_confidence` | FLOAT | 0.0–1.0 |
| `is_duplicate` | BOOL | Cross-store duplicate flag |
| `pii_stripped` | BOOL | PII removal confirmation |

### Data Sources

| Platform | Library | Rate Limit |
|----------|---------|------------|
| iOS App Store | `app_store_reviews` (PyPI) | ~500 reviews/call |
| Google Play | `google-play-scraper` (npm via subprocess) | ~200 reviews/call |
| CSV Fallback | `pandas.read_csv` | Unlimited |

### Date Range Logic
- **Initial run:** `today - 84 days` (12 weeks)
- **Subsequent runs:** `last_run_date` → `now` (weekly delta merge)

### Acceptance Criteria
- Both stores return reviews into unified schema
- CSV fallback activates when API fails after 3 retries
- `last_run_date` persisted in `run_log` table

---

## Phase 2 — Noise Management

### Pipeline Flow

```
Raw Reviews
    │
    ▼
┌────────────────────┐
│ Language Filter     │ ── langdetect conf < 0.90 → DISCARD
└────────┬───────────┘
         ▼
┌────────────────────┐
│ Empty Text Filter   │ ── len(text) < 20 → DISCARD
└────────┬───────────┘
         ▼
┌────────────────────┐
│ Spam Detector       │ ── repetition_ratio > 0.4 → DISCARD
└────────┬───────────┘
         ▼
┌────────────────────┐
│ Cross-Store Dedup   │ ── SHA-256 match → MARK is_duplicate=True
└────────┬───────────┘
         ▼
┌────────────────────┐
│ PII Stripper        │ ── Pass 1: regex  →  Pass 2: spaCy NER
└────────┬───────────┘
         ▼
┌────────────────────┐
│ Surge Sampler       │ ── volume > 3x median → stratified sample 500
└────────┬───────────┘
         ▼
┌────────────────────┐
│ Anomaly Tagger      │ ── rating-text mismatch → suspicious_review=True
└────────┬───────────┘
         ▼
  Clean Reviews (→ Phase 3)
```

### Filter Strategies

| Noise Type | Detection | Action |
|------------|-----------|--------|
| Non-English | `langdetect` confidence < 0.90 | Discard |
| No text body | `len(text) < 20` | Discard |
| Spam/bot | Repetition ratio > 0.4 | Discard |
| Cross-store dup | SHA-256 of normalized text | Mark `is_duplicate=True` |
| Old bugs | Tag `app_version`, weight by recency | Down-weight |
| Rating mismatch | Sentiment vs rating delta > 1.5 | Flag `suspicious_review=True` |
| Surge week | Volume > 3× weekly median | Stratified sample of 500 |

### Acceptance Criteria
- All 7 noise filters execute in sequence
- PII stripper runs two passes (regex + NER) before any downstream processing
- Noise log written to `data/processed/noise_log.csv`

---

## Phase 3 — AI Theme Mapping Engine

### Three-Step Architecture

```
Clean Reviews
    │
    ▼
┌──────────────────────────────────────┐
│ STEP 1: EMBEDDING                     │
│ Primary: BAAI/bge-small-en-v1.5      │
│ Fallback: all-MiniLM-L6-v2           │
│ Output: 384-dim vectors → ChromaDB   │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│ STEP 2: CLUSTERING                    │
│ Primary: BERTopic (nr_topics=5)      │
│ Fallback: K-Means (k=5)             │
│   triggers when < 50 reviews/week    │
│ Uses c-TF-IDF for fintech vocab      │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│ STEP 3: LLM LABELING & SCORING       │
│ Model: Llama 3 via Groq API          │
│ Input: Top 15 reviews per cluster    │
│ Output (JSON):                       │
│   - theme_label                      │
│   - urgency_score (1–10)             │
│   - sentiment_score (-1 to +1)       │
│   - volume_count                     │
│   - representative_quote (PII-free)  │
│   - trend_direction (↑ ↓ →)          │
│ Constraint: max_tokens=1000          │
└──────────────┬───────────────────────┘
               ▼
         Themed Output (→ Phase 4)
```

### Pre-defined Theme Taxonomy

| ID | Label | Sample Keywords |
|----|-------|-----------------|
| T1 | Onboarding & KYC | account creation, verification failed, documents |
| T2 | Payments & Withdrawals | money stuck, transaction failed, UPI error |
| T3 | Portfolio & Performance | returns wrong, P&L incorrect, holdings missing |
| T4 | App Stability & UX | crash, slow, login loop, OTP not received |
| T5 | Customer Support | no response, chat useless, ticket ignored |

### Vector Store (ChromaDB)

```python
# Collection schema
collection = chroma_client.get_or_create_collection(
    name="groww_reviews",
    metadata={"hnsw:space": "cosine"}
)
# Each document stored with metadata:
# { review_id, store, rating, date, week_number, app_version }
```

### Acceptance Criteria
- Embeddings generated and stored in ChromaDB
- BERTopic produces ≤ 5 clusters; falls back to K-Means when < 50 reviews
- LLM output is valid JSON conforming to the schema
- Groq calls respect `max_tokens=1000`

---

## Phase 4 — Quarterly Report Structure

### Report Architecture

```
12 Weekly Snapshots
        │
        ▼
┌───────────────────────────────────────────┐
│          QUARTERLY REPORT BUILDER          │
├───────────────────────────────────────────┤
│ Section 1: Executive Summary              │
│   - 12-week rating sparkline              │
│   - Total review volume                   │
│   - Overall sentiment trajectory          │
├───────────────────────────────────────────┤
│ Section 2: Theme Heatmap                  │
│   - Week × Theme matrix (urgency-colored) │
├───────────────────────────────────────────┤
│ Section 3: Top Regressions                │
│   - Themes worsening 3+ consecutive weeks │
├───────────────────────────────────────────┤
│ Section 4: Verbatim Quotes Archive        │
│   - 3 quotes/theme/quarter (max 15)       │
├───────────────────────────────────────────┤
│ Section 5: Action Backlog                 │
│   - Open / In-Progress / Resolved tags    │
├───────────────────────────────────────────┤
│ Section 6: Seasonal Observations          │
│   - Correlation with IPOs, SEBI events    │
└───────────────────────────────────────────┘
```

### Data Flow

```python
# Quarterly aggregation logic
weekly_snapshots = db.query(WeeklyPulse).filter(
    WeeklyPulse.date >= quarter_start,
    WeeklyPulse.date <= quarter_end
).order_by(WeeklyPulse.week_number).all()

# Regression detection
for theme in themes:
    consecutive_worsening = count_consecutive_decline(theme.urgency_history)
    if consecutive_worsening >= 3:
        flag_as_regression(theme)
```

### Acceptance Criteria
- Report aggregates exactly 12 weekly snapshots
- Heatmap renders with urgency-colored cells
- Regressions correctly flagged at ≥ 3 consecutive weeks of decline

---

## Phase 5 — Scheduler Design

### Orchestration Sequence

```
Monday 09:00 IST (APScheduler CronTrigger)
    │
    ▼
┌─────────────────────────────────┐
│ 1. Ingest new reviews (Phase 1) │
├─────────────────────────────────┤
│ 2. Clean and filter (Phase 2)   │
├─────────────────────────────────┤
│ 3. Map themes (Phase 3)         │
├─────────────────────────────────┤
│ 4. Build pulse note (Phase 4)   │
├─────────────────────────────────┤
│ 5. Push to Google Docs (Phase 6)│
├─────────────────────────────────┤
│ 6. Send email via Gmail (Ph. 6) │
├─────────────────────────────────┤
│ 7. Archive to CSV               │
├─────────────────────────────────┤
│ 8. Log run metadata             │
└─────────────────────────────────┘
    │
    ▼ on failure
┌─────────────────────────────────┐
│ Alert: Slack webhook / email    │
│ Retry: 2s → 4s → 8s (max 3)   │
└─────────────────────────────────┘
```

### Scheduler Configuration

```python
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

scheduler = BlockingScheduler()
scheduler.add_job(
    run_weekly_pulse,
    CronTrigger(
        day_of_week='mon',
        hour=9,
        minute=0,
        timezone=pytz.timezone('Asia/Kolkata')
    ),
    id='weekly_pulse',
    max_instances=1,
    misfire_grace_time=3600
)
```

### Retry Logic
- External API calls: exponential backoff (2s, 4s, 8s)
- Max 3 retries per call
- On total failure: alert + skip to next week

### Acceptance Criteria
- Cron fires at Monday 09:00 IST
- Full pipeline completes end-to-end
- Failures trigger alerts and do not crash the scheduler

---

## Phase 6 — MCP Server Integration

### Google Docs MCP Flow

```
┌──────────────────────────────────────────┐
│           GOOGLE DOCS MCP                 │
├──────────────────────────────────────────┤
│ 1. OAuth2 service account auth           │
│ 2. Create doc: "Groww Weekly Pulse —     │
│    Week of YYYY-MM-DD"                   │
│ 3. Apply H1 title, H2 sections          │
│ 4. Brand color #00B386 on headings       │
│ 5. Insert theme table                    │
│    (rank, theme, volume, urgency, trend) │
│ 6. Insert quote block-quotes             │
│ 7. Insert action items (numbered list)   │
│ 8. Set sharing: view-only link           │
│ 9. Return document URL                   │
└──────────────────┬───────────────────────┘
                   ▼
              doc_url → Gmail MCP
```

### Gmail MCP Flow

```
┌──────────────────────────────────────────┐
│             GMAIL MCP                     │
├──────────────────────────────────────────┤
│ 1. Subject: "Groww App Pulse — Wk WW"   │
│ 2. Recipients: from RECIPIENT_LIST .env  │
│ 3. Body: HTML-formatted pulse (inline)   │
│ 4. Attachment: Google Doc link           │
│ 5. Create as DRAFT (human review)        │
│ 6. Auto-send ONLY if AUTO_SEND=true      │
└──────────────────────────────────────────┘
```

### Acceptance Criteria
- Google Doc created with correct formatting and brand colors
- Email draft created with correct subject line format
- No auto-send unless `AUTO_SEND=true` in `.env`

---

## Phase 7 — Edge Case Handling

### Decision Matrix

```
                    ┌──────────────────┐
                    │ Edge Case Router  │
                    └────────┬─────────┘
         ┌──────────┬───────┼───────┬──────────┐
         ▼          ▼       ▼       ▼          ▼
    Zero Reviews  Rate   Low      BERTopic   LLM
    This Week     Limit  English  < 3 Clust  Timeout
         │          │       │       │          │
         ▼          ▼       ▼       ▼          ▼
    Skip AI;     Backoff; Alert;  K-Means    Retry 1x;
    Send "No     CSV     "Insuf-  k=3;      keyword
    reviews"     fallback ficient" flag in   fallback
    email                         report     labeling
```

| Edge Case | Detection | Strategy |
|-----------|-----------|----------|
| Zero reviews | `len(reviews) == 0` | Skip AI; send notification |
| API 429 | HTTP status | Backoff → CSV fallback |
| All non-English | `english_count < 10` | Alert: insufficient data |
| BERTopic < 3 clusters | `len(topics) < 3` | K-Means k=3; flag |
| LLM timeout > 30s | Response timer | Retry once; keyword fallback |
| Duplicate Doc | Week ID check | Skip or overwrite |
| Text > 10K chars | `len(text)` check | Truncate to 1K + marker |
| Surge week | Volume > 3× median | Stratified sample of 500 |
| Rating mismatch | Sentiment delta > 1.5 | Flag `suspicious_review` |

### Acceptance Criteria
- Each edge case has automated detection and handling
- System achieves ≥ 95% weekly run success over 12 weeks
- Edge case occurrences are logged

---

## Phase 8 — Security Architecture

### Threat Model

```
┌───────────────────────────────────────────────────┐
│               SECURITY LAYERS                      │
├───────────────────────────────────────────────────┤
│ Layer 1: SCRAPER DEFENSE                          │
│   - Rotate user-agents per request                │
│   - Rate limit: 1 request / 2 seconds             │
├───────────────────────────────────────────────────┤
│ Layer 2: PROMPT INJECTION DEFENSE                 │
│   - Review text wrapped in <review> XML tags      │
│   - Never concatenate raw text into system prompt │
├───────────────────────────────────────────────────┤
│ Layer 3: PII DEFENSE                              │
│   - Pre-LLM: regex strip                          │
│   - Post-LLM: regex rescan of output              │
├───────────────────────────────────────────────────┤
│ Layer 4: SECRETS MANAGEMENT                       │
│   - .env in .gitignore                            │
│   - CI/CD: GitHub Secrets / AWS Secrets Manager   │
├───────────────────────────────────────────────────┤
│ Layer 5: EMAIL SAFETY                             │
│   - Default recipient: self/alias only            │
│   - Team distribution requires explicit flag      │
├───────────────────────────────────────────────────┤
│ Layer 6: RUNTIME ISOLATION                        │
│   - Dedicated groww-pulse Linux user (no sudo)    │
│   - Docker container isolation                    │
├───────────────────────────────────────────────────┤
│ Layer 7: DEPENDENCY AUDIT                         │
│   - pip-audit + npm audit in CI/CD                │
│   - Weekly Dependabot PRs                         │
└───────────────────────────────────────────────────┘
```

### Acceptance Criteria
- No PII in any output artifact (verified by post-processing rescan)
- Secrets never in source control
- CI pipeline includes `pip-audit` and `npm audit`

---

## Phase 9 — Quarterly Deliverables

### Output Artifacts

```
data/archive/
├── groww_q1_2025_pulse_report.md    # 12-week aggregate report
├── groww_reviews_q1_2025.csv        # Redacted review archive
├── email_drafts/
│   ├── email_draft_week_01.html
│   ├── email_draft_week_02.html
│   └── ... (12 files total)
└── README.md                        # Re-run instructions
```

### CSV Archive Schema

| Column | Type | Description |
|--------|------|-------------|
| `review_id` | STRING | Unique hash |
| `store` | STRING | ios / android |
| `rating` | INT | 1–5 |
| `title_clean` | TEXT | PII-stripped title |
| `text_clean` | TEXT | PII-stripped body |
| `date` | DATE | Review date |
| `week_number` | INT | ISO week |
| `theme_assigned` | STRING | T1–T5 label |
| `urgency_score` | FLOAT | 1–10 |

### Acceptance Criteria
- All 4 deliverables generated after 12 successful weekly runs
- CSV contains only `pii_stripped=True` rows
- README enables full re-run for subsequent quarters

---

## Technology Stack Summary

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Language | Python 3.11 | Rich ML/scraping ecosystem |
| iOS Ingestion | `app_store_reviews` (PyPI) | Simple, no login required |
| Android Ingestion | `google-play-scraper` (npm) | Most reliable unofficial API |
| Language Detection | `langdetect` + `langid` | Ensemble for higher accuracy |
| PII Removal | spaCy `en_core_web_sm` + regex | Fast, covers named entities |
| Embeddings | BAAI/bge-small-en-v1.5 | Free, local, strong fintech relevance |
| Clustering | BERTopic | Topic coherence + keyword transparency |
| LLM Labeling | Llama 3 via Groq | Structured JSON, fast inference |
| Vector DB | ChromaDB | Local-first, zero infrastructure |
| Relational DB | SQLite (dev) / Postgres (prod) | Portable, simple schema |
| Scheduler | APScheduler | Python-native, timezone-aware |
| Docs Delivery | Google Docs MCP | Native GDoc creation |
| Email Delivery | Gmail MCP | Draft creation + controlled send |
| Containerization | Docker + docker-compose | Reproducible environments |
| CI/CD | GitHub Actions | Lint, test, audit on every push |
| Secrets | `.env` / GitHub Secrets | Standard, never committed |
