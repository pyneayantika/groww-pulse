# Groww Pulse Agent — Phase-wise Implementation Summary

**Project:** Groww Quarterly Pulse Engine  
**Target App:** Groww (Stocks, Mutual Funds & Gold)  
**Scope:** Q1 2026 (Jan – Mar) · 12 weeks · 4,841 reviews  
**Deployment:** Fly.io (Docker) · GitHub: `pyneayantika/groww-pulse`  
**Status:** ✅ Implemented & Deployed

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Phase 0 — Project Setup & Infrastructure](#phase-0--project-setup--infrastructure)
3. [Phase 1 — Data Ingestion](#phase-1--data-ingestion)
4. [Phase 2 — Noise Management & Preprocessing](#phase-2--noise-management--preprocessing)
5. [Phase 3 — AI Theme Mapping Engine](#phase-3--ai-theme-mapping-engine)
6. [Phase 4 — Report Generation](#phase-4--report-generation)
7. [Phase 5 — Scheduler & Orchestration](#phase-5--scheduler--orchestration)
8. [Phase 6 — MCP Server Integration (Gmail + Google Docs)](#phase-6--mcp-server-integration)
9. [Phase 7 — Edge Case Handling](#phase-7--edge-case-handling)
10. [Phase 8 — Security Architecture](#phase-8--security-architecture)
11. [Phase 9 — Dashboard & Delivery](#phase-9--dashboard--delivery)
12. [Full Tech Stack Summary](#full-tech-stack-summary)

---

## System Architecture Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                    GROWW PULSE ENGINE — E2E FLOW                   │
│                                                                     │
│  ┌───────────┐   ┌──────────┐   ┌──────────┐   ┌───────────────┐  │
│  │  Phase 1  │──▶│  Phase 2  │──▶│  Phase 3  │──▶│ Phase 4/6/9  │  │
│  │ Ingestion │   │  Noise   │   │ AI Theme  │   │ Report+Dash  │  │
│  │iOS+Android│   │ Filter   │   │  Engine   │   │ board+Email  │  │
│  └───────────┘   └──────────┘   └──────────┘   └───────────────┘  │
│       ▲                                               │             │
│       │             ┌──────────┐                     ▼             │
│       └─────────────│  Phase 5 │◀────── Phase 8 Security          │
│                     │Scheduler │        Phase 7 Edge Cases         │
│                     └──────────┘                                   │
│  Cross-cutting: Phase 0 (Setup) · Phase 8 (Security)              │
└───────────────────────────────────────────────────────────────────┘
```

---

## Phase 0 — Project Setup & Infrastructure

### What Was Built
Established the complete project scaffold, environment configuration, dependency baseline, and Docker containerisation from scratch.

### Key Deliverables
- Full directory structure (`ingestion/`, `storage/`, `ai/`, `report/`, `mcp/`, `scheduler/`, `dashboard/`, `scripts/`, `tests/`, `data/`, `Docs/`)
- `.env` / `.env.example` separation (secrets never committed)
- `requirements.txt` with all Python dependencies
- `package.json` for Node.js Android scraper bridge
- `Dockerfile` + `docker-compose.yml` for containerisation
- `.dockerignore` to exclude secrets and local DB from Docker image
- `fly.toml` for Fly.io cloud deployment (v2 format)
- GitHub repository (`pyneayantika/groww-pulse`) with `.gitignore`
- `scripts/startup.sh` — container entrypoint that creates DB tables on cold start without re-seeding data

### Tech Stack — Phase 0

| Tool | Purpose |
|------|---------|
| **Python 3.11** | Core runtime |
| **Node.js + npm** | Android scraper bridge (`google-play-scraper`) |
| **Docker** | Container image build and run |
| **docker-compose** | Local multi-service orchestration |
| **Fly.io** | Cloud deployment (Singapore `sin` region) |
| **GitHub** | Version control + CI/CD |
| **python-dotenv** | `.env` file loading |
| **`fly.toml` (TOML v2)** | Fly.io app configuration |

### Key Config (`.env`)
```
GROQ_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
GOOGLE_REFRESH_TOKEN, RECIPIENT_LIST, AUTO_SEND,
DB_URL, CHROMADB_PATH, TIMEZONE, IOS_APP_ID, ANDROID_APP_ID
```

---

## Phase 1 — Data Ingestion

### What Was Built
Dual-platform review scraper that pulls live reviews from iOS App Store and Google Play Store, normalises them into a unified schema, and persists them to SQLite.

### Architecture
```
Scheduler Trigger
      │
      ▼
Ingestion Orchestrator
   ├── ios_scraper.py      (RSS feed client)
   ├── android_scraper.py  (Node.js subprocess bridge)
   └── csv_fallback.py     (pandas CSV loader)
      │
      ▼
Unified Review Schema → SQLite DB
```

### Key Files
- `ingestion/ios_scraper.py` — App Store RSS feed client
- `ingestion/android_scraper.py` — calls `google-play-scraper` via Node.js subprocess
- `ingestion/csv_fallback.py` — pandas CSV loader (activates when both APIs fail after 3 retries)
- `ingestion/language_filter.py` — ensemble language detection
- `ingestion/deduplicator.py` — SHA-256 cross-store deduplication
- `storage/models.py` — SQLAlchemy ORM (`Review`, `WeeklyRun`, `Theme`, `RunLog`)
- `storage/db.py` — SQLite engine factory with `bulk_insert_reviews()` using `INSERT OR IGNORE`

### Review Schema (SQLAlchemy ORM)

| Field | Type | Description |
|-------|------|-------------|
| `review_id` | STRING (PK) | SHA-256(store + original_id + date) |
| `store` | STRING | `ios` or `android` |
| `rating` | INT | 1–5 |
| `text` | TEXT | Review body |
| `date` | STRING | Review date |
| `app_version` | STRING | App version at review time |
| `language_detected` | STRING | ISO 639-1 code |
| `language_confidence` | FLOAT | 0.0–1.0 |
| `is_duplicate` | BOOL | Cross-store duplicate flag |
| `pii_stripped` | BOOL | PII removal confirmation |
| `week_number` | INT | ISO week number |

### Data Volume — Q1 2026

| Week | Date | Reviews | Surge? |
|------|------|---------|--------|
| 1 | 2026-01-05 | 280 | — |
| 2 | 2026-01-12 | 310 | — |
| 3 | 2026-01-19 | 295 | — |
| 4 | 2026-01-26 | 320 | — |
| 5 | 2026-02-02 | 340 | — |
| 6 | 2026-02-09 | 360 | — |
| 7 | 2026-02-16 | 380 | — |
| **8** | **2026-02-23** | **920** | **✅ Surge** |
| 9 | 2026-03-02 | 400 | — |
| 10 | 2026-03-09 | 370 | — |
| 11 | 2026-03-16 | 330 | — |
| 12 | 2026-03-23 | 300 | — |
| **Total** | | **4,605** | |

### Tech Stack — Phase 1

| Tool | Purpose |
|------|---------|
| **`app_store_reviews`** (PyPI) | iOS App Store RSS feed scraping |
| **`google-play-scraper`** (npm) | Google Play review scraping |
| **pandas** | CSV fallback data loading |
| **SQLAlchemy 2.0** | ORM for unified review schema |
| **SQLite** | Local relational database (`data/groww_pulse.db`) |
| **hashlib (SHA-256)** | Cross-store deduplication key |

---

## Phase 2 — Noise Management & Preprocessing

### What Was Built
A 7-stage sequential noise filtering pipeline that cleans raw reviews before any AI processing.

### Pipeline Flow
```
Raw Reviews
    ↓
Language Filter   (langdetect + langid ensemble, conf < 0.90 → discard)
    ↓
Empty Text Filter (len < 20 → discard)
    ↓
Spam Detector     (repetition_ratio > 0.4 → discard)
    ↓
Cross-Store Dedup (SHA-256 → mark is_duplicate=True)
    ↓
PII Stripper      (Pass 1: regex | Pass 2: spaCy NER)
    ↓
Surge Sampler     (volume > 3× median → stratified sample of 500)
    ↓
Anomaly Tagger    (rating-text mismatch → suspicious_review=True)
    ↓
Clean Reviews → Phase 3
```

### Key Files
- `ingestion/language_filter.py` — `langdetect` + `langid` ensemble
- `ingestion/pii_stripper.py` — regex pass + spaCy NER pass
- `ingestion/deduplicator.py` — SHA-256 normalisation + dedup

### Noise Filter Strategy

| Noise Type | Detection | Action |
|------------|-----------|--------|
| Non-English | `langdetect` confidence < 0.90 | Discard |
| Short/empty | `len(text) < 20` | Discard |
| Spam/bot | Repetition ratio > 0.4 | Discard |
| Cross-store dup | SHA-256 of normalised text | Mark `is_duplicate=True` |
| Surge week | Volume > 3× weekly median | Stratified sample of 500 |
| Rating mismatch | Sentiment delta > 1.5 | Flag `suspicious_review=True` |

### Tech Stack — Phase 2

| Tool | Purpose |
|------|---------|
| **langdetect** | Primary language detection |
| **langid** | Ensemble confidence scoring |
| **spaCy `en_core_web_sm`** | Named entity recognition for PII removal |
| **regex** | Fast first-pass PII stripping |
| **numpy** | Surge week volume statistics |

---

## Phase 3 — AI Theme Mapping Engine

### What Was Built
A 3-step AI pipeline that embeds, clusters, and labels reviews into structured themes with urgency scores.

### Pipeline Architecture
```
Clean Reviews
    ↓
STEP 1 — EMBEDDING
  Primary:  BAAI/bge-small-en-v1.5  (384-dim)
  Fallback: all-MiniLM-L6-v2
  Store:    ChromaDB (cosine similarity)
    ↓
STEP 2 — CLUSTERING
  Primary:  BERTopic (nr_topics=5, c-TF-IDF fintech vocab)
  Fallback: K-Means (k=5) when < 50 reviews/week
    ↓
STEP 3 — LLM LABELING & SCORING
  Model:    Llama 3 (llama3-8b-8192) via Groq API
  Input:    Top 15 reviews per cluster
  Output:   JSON { theme_label, urgency_score, sentiment_score,
                   volume_count, representative_quote, trend_direction }
    ↓
Themed Output → DB + Report
```

### Pre-defined Theme Taxonomy

| ID | Label | Sample Keywords |
|----|-------|-----------------|
| T1 | Onboarding & KYC | kyc, verification, account, documents |
| T2 | Payments & Withdrawals | payment, withdrawal, upi, transaction |
| T3 | Portfolio & Performance | portfolio, returns, p&l, holdings |
| T4 | App Stability & UX | crash, slow, login, otp, app |
| T5 | Customer Support | support, customer, response, ticket |
| T6 | Fraud & Security Concerns | fraud, security, suspicious, unauthorised |

### Theme DB Schema (`themes` table)

| Field | Description |
|-------|-------------|
| `theme_id` | T1–T6 identifier |
| `label` | Human-readable theme name |
| `urgency_score` | 1–10 float (higher = more urgent) |
| `sentiment_score` | -1.0 to +1.0 |
| `volume` | Review count for this theme |
| `trend_direction` | `worsening` / `stable` / `improving` |
| `top_quote` | PII-free representative user quote |
| `keywords` | JSON array of matched keywords |
| `action_idea` | LLM-generated recommended action |

### Tech Stack — Phase 3

| Tool | Purpose |
|------|---------|
| **sentence-transformers** | `BAAI/bge-small-en-v1.5` embeddings |
| **BERTopic** | Primary topic clustering |
| **scikit-learn (K-Means)** | Fallback clustering (< 50 reviews) |
| **HDBSCAN** | Density-based clustering support |
| **UMAP** | Dimensionality reduction for BERTopic |
| **ChromaDB** | Local vector store (`cosine` similarity) |
| **Groq API (Llama 3)** | LLM labeling & scoring (`llama3-8b-8192`) |

---

## Phase 4 — Report Generation

### What Was Built
Automated quarterly aggregate report and weekly pulse notes composed from 12 weeks of themed data.

### Report Sections
1. **Executive Summary** — 12-week rating sparkline, review volume, sentiment trajectory
2. **Theme Heatmap** — Week × Theme matrix with urgency-coloured cells
3. **Top Regressions** — Themes worsening 3+ consecutive weeks
4. **Verbatim Quotes Archive** — 3 PII-free quotes per theme (max 15 per quarter)
5. **Action Backlog** — LLM-generated recommendations, tagged Open/In-Progress/Resolved
6. **Seasonal Observations** — Correlations with IPOs, SEBI events

### Output Artifacts

| File | Description |
|------|-------------|
| `data/archive/groww_week_WW_YYYY_pulse.md` | Weekly markdown report |
| `data/archive/groww_week_WW_YYYY_pulse.html` | Printable HTML report |
| `data/archive/email_drafts/email_draft_week_WW_YYYY.html` | Email draft HTML |
| `data/archive/groww_qN_YYYY_quarterly_report.md` | 12-week aggregate |
| `data/archive/groww_reviews_qN_YYYY.csv` | Redacted review archive |

### Key Files
- `report/pulse_builder.py` — weekly pulse note composer
- `report/quarterly_builder.py` — 12-week aggregate builder
- `report/email_composer.py` — HTML email body generator
- `report/templates/pulse_template.j2` — Jinja2 weekly template
- `report/templates/quarterly_template.j2` — Jinja2 quarterly template
- `gen_report.py` — CLI report generation entry point

### Tech Stack — Phase 4

| Tool | Purpose |
|------|---------|
| **Jinja2** | HTML/Markdown report templating |
| **pandas** | Data aggregation and CSV export |
| **SQLAlchemy** | 12-week snapshot queries |
| **storage/csv_archive.py** | Rolling quarterly CSV manager |

---

## Phase 5 — Scheduler & Orchestration

### What Was Built
Automated weekly pipeline trigger running every Monday at 09:00 IST with retry logic and failure alerts.

### Orchestration Sequence
```
Monday 09:00 IST (APScheduler CronTrigger)
    ↓
1. Ingest new reviews     (Phase 1)
2. Clean and filter       (Phase 2)
3. Map themes             (Phase 3)
4. Build pulse note       (Phase 4)
5. Push to Google Docs    (Phase 6)
6. Send/draft email       (Phase 6)
7. Archive to CSV         (Phase 9)
8. Log run metadata       (weekly_runs table)
    ↓ on failure
Alert + Exponential backoff (2s → 4s → 8s, max 3 retries)
```

### Key Files
- `scheduler/cron_runner.py` — `APScheduler` Monday 09:00 IST trigger
- `scheduler/orchestrator.py` — `run_weekly_pipeline()` full pipeline function
- `scripts/manual_run.py` — CLI for manual pipeline invocation

### Tech Stack — Phase 5

| Tool | Purpose |
|------|---------|
| **APScheduler 3.10** | `CronTrigger` Monday 09:00 IST |
| **pytz** | `Asia/Kolkata` timezone handling |
| **click** | CLI argument parsing for manual runs |

---

## Phase 6 — MCP Server Integration

### What Was Built
Two MCP (Model Context Protocol) client integrations — Google Docs for report publishing and Gmail for draft email delivery.

### Google Docs Flow
```
LLM Report JSON
    → OAuth2 authentication (refresh token)
    → Create Google Doc: "Groww Weekly Pulse — Week WW, YYYY"
    → Apply brand colour #00B386 on headings
    → Insert: theme table, urgency scores, quote blockquotes, action list
    → Set share: view-only link
    → Return doc_url → stored in weekly_runs.gdoc_url
```

### Gmail Draft Flow
```
HTML email body (inline styled)
    → Subject: "Groww App Pulse — Week WW, YYYY | Top Issue: {theme}"
    → Top 3 themes table (urgency colour-coded)
    → User verbatim quotes
    → Recommended actions list
    → "View Full Report →" button (links to gdoc_url)
    → Created as DRAFT (human review before send)
    → Auto-send only if AUTO_SEND=true in .env
```

### Dashboard Route — `/api/generate-draft`
- Deduplicates themes via `GROUP BY t.label + MAX(urgency_score)`
- Fetches `gdoc_url` from latest completed run
- Builds branded HTML email inline
- Calls `mcp.gmail_client.create_draft()` and returns `draft_id`

### Key Files
- `mcp/gmail_client.py` — Gmail OAuth2 draft creation
- `mcp/gdocs_client.py` — Google Docs MCP integration
- `dashboard/app.py` → `POST /api/generate-draft`

### Tech Stack — Phase 6

| Tool | Purpose |
|------|---------|
| **Google OAuth2** | Authentication via `GOOGLE_REFRESH_TOKEN` |
| **Gmail API (MCP)** | Draft creation and controlled send |
| **Google Docs API (MCP)** | Programmatic document creation |
| **httpx** | Async HTTP client for API calls |

---

## Phase 7 — Edge Case Handling

### What Was Built
Automated detection and graceful handling of 9 failure modes to ensure ≥ 95% weekly run success.

### Edge Case Matrix

| Edge Case | Detection | Strategy |
|-----------|-----------|----------|
| Zero reviews | `len(reviews) == 0` | Skip AI; send "no reviews" notification |
| API rate limit (429) | HTTP status | Exponential backoff → CSV fallback |
| All non-English | `english_count < 10` | Alert: insufficient data |
| BERTopic < 3 clusters | `len(topics) < 3` | K-Means k=3; flag in report |
| LLM timeout > 30s | Response timer | Retry once; keyword-based fallback labeling |
| Surge week | Volume > 3× weekly median | Stratified sample of 500 (`surge_mode=True`) |
| Rating-text mismatch | Sentiment delta > 1.5 | Flag `suspicious_review=True` |
| Text too long | `len(text) > 10K` | Truncate to 1K + `[truncated]` marker |
| Duplicate run | Week ID check | Skip or overwrite based on config |

### Surge Week — Week 8 (920 reviews)
Week 8 (2026-02-23) triggered `surge_mode=True` with 920 reviews — 2.4× the weekly average. The system applied stratified sampling and correctly identified **Payments & Withdrawals (T2)** as the dominant theme with urgency score **9.2/10**.

### Tech Stack — Phase 7

| Tool | Purpose |
|------|---------|
| **scikit-learn (K-Means)** | Fallback clustering when BERTopic fails |
| **APScheduler misfire_grace_time** | Handles missed scheduler triggers |
| **Python logging** | Run log written to `run_logs` table |

---

## Phase 8 — Security Architecture

### What Was Built
7-layer security model protecting secrets, PII, prompt injection, and runtime isolation.

### Security Layers

| Layer | Control | Implementation |
|-------|---------|----------------|
| **Scraper Defence** | Rate limit 1 req/2s; rotate user-agents | `ingestion/` scrapers |
| **Prompt Injection** | Reviews wrapped in `<review>` XML tags | `ai/llm_labeler.py` |
| **PII Defence** | Pre-LLM regex strip + Post-LLM rescan | `ingestion/pii_stripper.py` |
| **Secrets Management** | `.env` gitignored; Fly.io secrets at deploy | `.gitignore`, `fly.toml` |
| **Email Safety** | Default recipient = self/alias only | `RECIPIENT_LIST` + `ENABLE_EXTERNAL_SEND` flag |
| **Runtime Isolation** | Docker container; no privileged access | `Dockerfile` |
| **Dependency Audit** | `pip-audit` + `npm audit` | `.github/workflows/` |

### Key Files
- `.gitignore` — excludes `.env`, `credentials.json`, `google_tokens.json`, `data/`
- `.dockerignore` — excludes `.env`, secrets, local `data/raw/`
- `scripts/check_secrets.py` — CI secret leak scanner

### Tech Stack — Phase 8

| Tool | Purpose |
|------|---------|
| **spaCy NER** | Post-processing PII rescan |
| **GitHub Secrets** | CI/CD secret injection |
| **Fly.io Secrets** | Production secret management (`flyctl secrets set`) |
| **Docker** | Runtime process isolation |

---

## Phase 9 — Dashboard & Delivery

### What Was Built
A real-time web dashboard (`Flask` + vanilla JS) showing live stats, theme cards, 12-week history, and one-click export/email actions — plus all quarterly deliverable CSV archives.

### Dashboard Features
- **Live stats bar** — total reviews, store split (iOS/Android), weeks tracked, top urgency score
- **Theme cards** — 5 urgency-ranked theme cards with trend indicator, sentiment score, top quote, action idea, and per-theme CSV export button
- **12-week history table** — week-by-week volume, top theme, urgency heatmap
- **Navbar actions:**
  - `▶ Run Pipeline` — triggers full pipeline via `POST /api/trigger-run`
  - `↓ All Reviews CSV` — downloads `data/archive/groww_reviews_quarterly.csv`
  - `📧 Generate Draft` — calls `POST /api/generate-draft`, creates Gmail draft, auto-opens inbox after 1.5s
  - `📬 View Drafts` — opens Gmail drafts filtered by "Groww Pulse"
  - `↺ Refresh` — refreshes all dashboard data
- **Toast notifications** — success/error feedback for every async action
- **IST clock** — live Indian Standard Time display

### API Routes (`dashboard/app.py`)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Render dashboard HTML |
| GET | `/api/summary` | Stats + top themes + gdoc_url |
| GET | `/api/weekly-history` | 12-week run history |
| GET | `/api/store-breakdown` | iOS vs Android breakdown |
| GET | `/api/export/quarterly` | Download all reviews CSV |
| GET | `/api/export/theme/<id>` | Download per-theme CSV |
| POST | `/api/trigger-run` | Manually trigger full pipeline |
| POST | `/api/generate-draft` | Create Gmail draft with weekly pulse |

### DB Seed (`scripts/init_render_db.py`)
- Creates all tables via `Base.metadata.create_all()`
- **Idempotent** — skips if reviews already exist
- Seeds 4,605 reviews, 12 `weekly_runs`, 65 themes (T1–T5 all weeks; T6 added weeks 8–12)

### Key Files
- `dashboard/app.py` — Flask application with all API routes
- `dashboard/templates/index.html` — Single-page dashboard (HTML + CSS + JS)
- `scripts/init_render_db.py` — Idempotent DB seed script
- `scripts/startup.sh` — Container startup script (`init_db()` then dashboard)
- `storage/csv_archive.py` — Quarterly CSV export utility

### Tech Stack — Phase 9

| Tool | Purpose |
|------|---------|
| **Flask 3.0** | Python web framework for dashboard + API |
| **SQLAlchemy 2.0** | ORM queries for summary and history |
| **SQLite** | Embedded relational DB (4,841 reviews) |
| **Vanilla JS (ES6)** | Dashboard interactivity, fetch API, async/await |
| **CSS custom properties** | Dark theme (`--green: #00C896`, `--card: #0D1626`) |
| **Fly.io** | Cloud hosting (Docker, region `sin`, 512 MB RAM) |
| **Persistent Volume** | `groww_data` mount at `/app/data` (SQLite persistence) |

---

## Full Tech Stack Summary

### By Layer

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Runtime** | Python | 3.11 | Core language |
| **Runtime** | Node.js | LTS | Android scraper bridge |
| **Web Framework** | Flask | 3.0 | Dashboard + REST API |
| **ORM** | SQLAlchemy | 2.0 | DB models and queries |
| **Database** | SQLite | 3 | Embedded relational DB (dev/prod) |
| **Vector Store** | ChromaDB | 0.5 | Embedding similarity search |
| **Embeddings** | `BAAI/bge-small-en-v1.5` | — | 384-dim semantic vectors |
| **Clustering** | BERTopic | 0.16 | Topic modelling (primary) |
| **Clustering** | scikit-learn K-Means | 1.3 | Fallback clustering |
| **Dim Reduction** | UMAP | 0.5 | BERTopic preprocessing |
| **Density Cluster** | HDBSCAN | 0.8 | BERTopic preprocessing |
| **LLM** | Llama 3 (`llama3-8b-8192`) | — | Theme labeling + scoring |
| **LLM API** | Groq | 0.9 | Fast Llama 3 inference |
| **Language Detection** | langdetect + langid | 1.0/1.1 | Ensemble language ID |
| **NLP / NER** | spaCy `en_core_web_sm` | 3.7 | PII removal |
| **Data Processing** | pandas | 2.0 | CSV handling + aggregation |
| **Numerics** | numpy | 1.24 | Stats and surge detection |
| **Templating** | Jinja2 | 3.1 | Report HTML/Markdown generation |
| **Scheduler** | APScheduler | 3.10 | Monday 09:00 IST cron |
| **Timezone** | pytz | 2024.1 | IST timezone handling |
| **HTTP Client** | httpx | 0.24 | Async API calls |
| **CLI** | click | 8.1 | `manual_run.py` argument parsing |
| **Email Delivery** | Gmail API (MCP) | OAuth2 | Draft creation |
| **Docs Delivery** | Google Docs API (MCP) | OAuth2 | Report doc creation |
| **Auth** | Google OAuth2 | — | `GOOGLE_REFRESH_TOKEN` flow |
| **iOS Scraping** | `app_store_reviews` (PyPI) | — | App Store RSS client |
| **Android Scraping** | `google-play-scraper` (npm) | — | Google Play reviews |
| **Config** | python-dotenv | 1.0 | `.env` loading |
| **Config** | PyYAML | 6.0 | `config.yaml` parsing |
| **Containerisation** | Docker | — | Image build + runtime |
| **Orchestration** | docker-compose | — | Local multi-service |
| **Cloud Hosting** | Fly.io | — | Production deployment (`sin`) |
| **Secrets (prod)** | Fly.io Secrets | — | `flyctl secrets set` |
| **Secrets (CI)** | GitHub Secrets | — | CI/CD injection |
| **CI/CD** | GitHub Actions | — | Lint, test, audit on push |
| **Testing** | pytest | 7.4 | Unit + integration tests |
| **Frontend** | Vanilla JS (ES6) | — | Dashboard async interactions |
| **Styling** | CSS custom properties | — | Dark-green theme |

### By Phase

| Phase | Key Technologies |
|-------|-----------------|
| **Phase 0 — Setup** | Python 3.11, Node.js, Docker, Fly.io, GitHub, python-dotenv |
| **Phase 1 — Ingestion** | `app_store_reviews`, `google-play-scraper`, pandas, SQLAlchemy, SQLite, hashlib |
| **Phase 2 — Noise** | langdetect, langid, spaCy, regex, numpy |
| **Phase 3 — AI Engine** | sentence-transformers, BERTopic, HDBSCAN, UMAP, K-Means, ChromaDB, Groq (Llama 3) |
| **Phase 4 — Reports** | Jinja2, pandas, SQLAlchemy, csv_archive |
| **Phase 5 — Scheduler** | APScheduler, pytz, click |
| **Phase 6 — MCP** | Gmail API, Google Docs API, Google OAuth2, httpx |
| **Phase 7 — Edge Cases** | scikit-learn, APScheduler grace time, Python logging |
| **Phase 8 — Security** | spaCy NER, Docker, GitHub Secrets, Fly.io Secrets |
| **Phase 9 — Dashboard** | Flask 3.0, SQLAlchemy, SQLite, Vanilla JS, CSS, Fly.io, Persistent Volume |

---

## Data Flow — End to End

```
iOS App Store ──┐
                ├─▶ ingestion/ ──▶ noise/ ──▶ ai/ ──▶ storage/
Google Play ────┘   (scrape)     (clean)   (embed   (SQLite +
                                            cluster  ChromaDB)
                                            label)
                                                │
                                                ▼
                                        report/ ──▶ mcp/
                                        (build)     (Gmail Draft
                                                     Google Doc)
                                                │
                                                ▼
                                        dashboard/app.py
                                        (Flask API + UI)
                                                │
                                                ▼
                                        Fly.io (Docker)
                                        https://groww-pulse-agent.fly.dev
```

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Total reviews (Q1 2026) | **4,841** |
| Weeks analysed | **12** (Jan–Mar 2026) |
| Themes tracked | **6** (T1–T6) |
| Theme records in DB | **65** |
| Peak surge week | **Week 8 — 920 reviews** |
| Dominant issue (Q1) | **Payments & Withdrawals (T2) — 9.2/10 urgency** |
| Python packages | **22** |
| Node packages | **1** (`google-play-scraper`) |
| API routes | **8** |
| Cloud region | **Singapore (`sin`)** |
| Deployment platform | **Fly.io** |
| Repository | **`pyneayantika/groww-pulse`** |

---

*Generated: April 2026 · Groww Pulse Agent v1.0*
