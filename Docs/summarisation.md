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
8. [Phase 6 — MCP Server Integration](#phase-6--mcp-server-integration)
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
└───────────────────────────────────────────────────────────────────┘
```

---

## Phase 0 — Project Setup & Infrastructure

### What Was Built
Complete project scaffold, environment configuration, dependency baseline, and Docker containerisation from scratch.

### Key Deliverables
- Full directory structure: `ingestion/`, `storage/`, `ai/`, `report/`, `mcp/`, `scheduler/`, `dashboard/`, `scripts/`, `tests/`, `data/`, `Docs/`
- `.env` / `.env.example` separation — secrets never committed
- `requirements.txt` with all Python dependencies
- `package.json` for Node.js Android scraper bridge
- `Dockerfile` + `docker-compose.yml` for containerisation
- `.dockerignore` to exclude secrets and local DB from image
- `fly.toml` (v2 format) for Fly.io cloud deployment
- GitHub repository `pyneayantika/groww-pulse` with `.gitignore`
- `scripts/startup.sh` — container entrypoint: creates DB tables on cold start without re-seeding

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
| **fly.toml (TOML v2)** | Fly.io app configuration |

---

## Phase 1 — Data Ingestion

### What Was Built
Dual-platform review scraper pulling reviews from iOS App Store and Google Play, normalised into a unified SQLAlchemy schema and persisted to SQLite.

### Architecture
```
Scheduler Trigger
      │
      ▼
Ingestion Orchestrator
   ├── ios_scraper.py      (RSS feed client)
   ├── android_scraper.py  (Node.js subprocess bridge)
   └── csv_fallback.py     (pandas CSV loader — 3-retry fallback)
      │
      ▼
Unified Review Schema → SQLite (data/groww_pulse.db)
```

### Review Schema (SQLAlchemy ORM — `reviews` table)

| Field | Type | Description |
|-------|------|-------------|
| `review_id` | STRING PK | SHA-256(store + id + date) |
| `store` | STRING | `ios` or `android` |
| `rating` | INT | 1–5 |
| `text` | TEXT | Review body |
| `date` | STRING | Review posted date |
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
| **`app_store_reviews`** (PyPI) | iOS App Store RSS scraping |
| **`google-play-scraper`** (npm) | Google Play review scraping |
| **pandas** | CSV fallback data loading |
| **SQLAlchemy 2.0** | ORM for unified review schema |
| **SQLite** | Embedded relational DB |
| **hashlib SHA-256** | Cross-store deduplication key |

---

## Phase 2 — Noise Management & Preprocessing

### What Was Built
7-stage sequential noise filtering pipeline that cleans raw reviews before any AI processing.

### Pipeline Flow
```
Raw Reviews
    ↓
Language Filter   (langdetect + langid ensemble, conf < 0.90 → discard)
    ↓
Empty Text Filter (len < 20 chars → discard)
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
| **numpy** | Surge volume statistics |

---

## Phase 3 — AI Theme Mapping Engine

### What Was Built
3-step AI pipeline: embed reviews → cluster into topics → label with LLM and score urgency.

### Pipeline Architecture
```
Clean Reviews
    ↓
STEP 1 — EMBEDDING
  Primary:  BAAI/bge-small-en-v1.5  (384-dim vectors)
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
Themed Output → DB (themes table) + Report
```

### Pre-defined Theme Taxonomy

| ID | Label | Sample Keywords |
|----|-------|-----------------|
| T1 | Onboarding & KYC | kyc, verification, account, documents |
| T2 | Payments & Withdrawals | payment, withdrawal, upi, transaction |
| T3 | Portfolio & Performance | portfolio, returns, p&l, holdings |
| T4 | App Stability & UX | crash, slow, login, otp |
| T5 | Customer Support | support, response, ticket, chat |
| T6 | Fraud & Security Concerns | fraud, security, suspicious, unauthorised |

### Tech Stack — Phase 3

| Tool | Purpose |
|------|---------|
| **sentence-transformers** | `BAAI/bge-small-en-v1.5` embeddings |
| **BERTopic 0.16** | Primary topic clustering |
| **scikit-learn K-Means** | Fallback clustering (< 50 reviews) |
| **HDBSCAN** | Density clustering support for BERTopic |
| **UMAP** | Dimensionality reduction for BERTopic |
| **ChromaDB 0.5** | Local vector store (cosine similarity) |
| **Groq API** | Fast Llama 3 inference (`llama3-8b-8192`) |

---

## Phase 4 — Report Generation

### What Was Built
Automated quarterly aggregate report and weekly pulse notes composed from 12 weeks of themed data.

### Report Sections
1. **Executive Summary** — 12-week rating sparkline, total volume, sentiment trajectory
2. **Theme Heatmap** — Week × Theme matrix with urgency-coloured cells
3. **Top Regressions** — Themes worsening 3+ consecutive weeks
4. **Verbatim Quotes Archive** — 3 PII-free quotes per theme (max 15/quarter)
5. **Action Backlog** — LLM-generated recommendations tagged Open/In-Progress/Resolved
6. **Seasonal Observations** — Correlations with IPOs, SEBI events

### Output Artifacts

| File | Description |
|------|-------------|
| `data/archive/groww_week_WW_YYYY_pulse.md` | Weekly markdown report |
| `data/archive/groww_week_WW_YYYY_pulse.html` | Printable HTML report |
| `data/archive/email_drafts/email_draft_week_WW.html` | Email draft HTML |
| `data/archive/groww_qN_YYYY_quarterly_report.md` | 12-week aggregate |
| `data/archive/groww_reviews_qN_YYYY.csv` | Redacted review archive |

### Tech Stack — Phase 4

| Tool | Purpose |
|------|---------|
| **Jinja2 3.1** | HTML/Markdown report templating |
| **pandas** | Data aggregation and CSV export |
| **SQLAlchemy** | 12-week snapshot queries |
| **storage/csv_archive.py** | Rolling quarterly CSV manager |

---

## Phase 5 — Scheduler & Orchestration

### What Was Built
Automated weekly pipeline trigger running every Monday at 09:00 IST with retry logic.

### Orchestration Sequence
```
Monday 09:00 IST (APScheduler CronTrigger)
    ↓
1. Ingest new reviews       (Phase 1)
2. Clean and filter         (Phase 2)
3. Map themes               (Phase 3)
4. Build pulse note         (Phase 4)
5. Push to Google Docs      (Phase 6)
6. Create Gmail draft       (Phase 6)
7. Archive to CSV           (Phase 9)
8. Log run to weekly_runs   (DB)
    ↓ on failure
Exponential backoff: 2s → 4s → 8s (max 3 retries)
Alert + skip to next week
```

### Tech Stack — Phase 5

| Tool | Purpose |
|------|---------|
| **APScheduler 3.10** | `CronTrigger` Monday 09:00 IST |
| **pytz** | `Asia/Kolkata` timezone |
| **click 8.1** | CLI args for `scripts/manual_run.py` |

---

## Phase 6 — MCP Server Integration

### What Was Built
Two MCP client integrations — Google Docs for report publishing and Gmail for draft email delivery — plus a `/api/generate-draft` dashboard route.

### Google Docs Flow
```
LLM Report → OAuth2 auth → Create Doc "Groww Weekly Pulse — Wk WW"
    → Brand colour #00B386 headings
    → Theme table + urgency scores + quotes + action list
    → Set share: view-only link
    → Return doc_url → stored in weekly_runs.gdoc_url
```

### Gmail Draft Flow
```
POST /api/generate-draft
    → Query top 5 themes (GROUP BY label, MAX urgency)
    → Fetch gdoc_url from latest completed run
    → Build inline HTML email:
        - Green header banner
        - Top 3 themes urgency table (colour-coded)
        - User verbatim quotes
        - Recommended actions list
        - "View Full Report →" CTA button
    → create_draft(payload) via Gmail API
    → Returns { success, draft_id, week, themes }
    → Frontend: toast + auto-open Gmail drafts after 1.5s
```

### Tech Stack — Phase 6

| Tool | Purpose |
|------|---------|
| **Google OAuth2** | Auth via `GOOGLE_REFRESH_TOKEN` |
| **Gmail API (MCP)** | Draft creation and controlled send |
| **Google Docs API (MCP)** | Programmatic document creation |
| **httpx 0.24** | Async HTTP client for API calls |

---

## Phase 7 — Edge Case Handling

### What Was Built
Automated detection and graceful handling of 9 failure modes targeting ≥ 95% weekly run success rate.

### Edge Case Matrix

| Edge Case | Detection | Strategy |
|-----------|-----------|----------|
| Zero reviews | `len(reviews) == 0` | Skip AI; send notification email |
| API rate limit 429 | HTTP status | Exponential backoff → CSV fallback |
| All non-English | `english_count < 10` | Alert: insufficient data |
| BERTopic < 3 clusters | `len(topics) < 3` | K-Means k=3; flag in report |
| LLM timeout > 30s | Response timer | Retry once; keyword-based fallback |
| Surge week | Volume > 3× median | Stratified sample 500; `surge_mode=True` |
| Rating-text mismatch | Sentiment delta > 1.5 | Flag `suspicious_review=True` |
| Text too long | `len(text) > 10K` | Truncate to 1K + `[truncated]` marker |
| Duplicate run | Week ID check | Skip or overwrite per config |

### Surge Week — Week 8 (920 reviews, 2026-02-23)
Volume was **2.4× the weekly average**. System applied stratified sampling, set `surge_mode=True`, and correctly identified **Payments & Withdrawals (T2)** as the dominant theme at **9.2/10 urgency**.

### Tech Stack — Phase 7

| Tool | Purpose |
|------|---------|
| **scikit-learn K-Means** | Fallback when BERTopic fails |
| **APScheduler `misfire_grace_time`** | Handles missed cron triggers |
| **Python logging → `run_logs` table** | Per-step audit trail |

---

## Phase 8 — Security Architecture

### What Was Built
7-layer security model covering secrets, PII, prompt injection, and runtime isolation.

### Security Layers

| Layer | Control | Implementation |
|-------|---------|----------------|
| **Scraper Defence** | 1 req/2s rate limit; rotate user-agents | `ingestion/` scrapers |
| **Prompt Injection** | Reviews wrapped in `<review>` XML tags | `ai/llm_labeler.py` |
| **PII Defence** | Pre-LLM regex strip + Post-LLM NER rescan | `ingestion/pii_stripper.py` |
| **Secrets Management** | `.env` gitignored; Fly.io secrets at deploy | `.gitignore`, `fly.toml` |
| **Email Safety** | Default recipient = self only | `RECIPIENT_LIST` + `ENABLE_EXTERNAL_SEND` |
| **Runtime Isolation** | Docker container; no privileged access | `Dockerfile` |
| **Dependency Audit** | `pip-audit` + `npm audit` in CI | `.github/workflows/` |

### Tech Stack — Phase 8

| Tool | Purpose |
|------|---------|
| **spaCy NER** | Post-processing PII rescan |
| **GitHub Secrets** | CI/CD secret injection |
| **Fly.io Secrets** | Production secret management |
| **Docker** | Runtime process isolation |

---

## Phase 9 — Dashboard & Delivery

### What Was Built
Real-time Flask web dashboard with live stats, theme cards, 12-week history, and one-click export/email actions.

### Dashboard Features

| Feature | Description |
|---------|-------------|
| **Live stats bar** | Total reviews, iOS/Android split, weeks tracked, top urgency |
| **Theme cards** | 5 urgency-ranked cards: trend, sentiment, top quote, action idea, per-theme CSV export |
| **12-week history table** | Volume, top theme, urgency heatmap per week |
| **▶ Run Pipeline** | Triggers full pipeline via `POST /api/trigger-run` |
| **↓ All Reviews CSV** | Downloads quarterly CSV archive |
| **📧 Generate Draft** | Creates Gmail draft; auto-opens inbox after 1.5s |
| **📬 View Drafts** | Opens Gmail drafts filtered by "Groww Pulse" |
| **↺ Refresh** | Refreshes all dashboard data |
| **IST clock** | Live Indian Standard Time |
| **Toast notifications** | Success/error feedback for all async actions |

### API Routes (`dashboard/app.py`)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Render dashboard HTML |
| GET | `/api/summary` | Stats + top 5 themes + `gdoc_url` |
| GET | `/api/weekly-history` | 12-week run history (deduplicated) |
| GET | `/api/store-breakdown` | iOS vs Android split |
| GET | `/api/export/quarterly` | Download all reviews CSV |
| GET | `/api/export/theme/<id>` | Download per-theme CSV |
| POST | `/api/trigger-run` | Manually trigger full pipeline |
| POST | `/api/generate-draft` | Create Gmail draft with pulse email |

### DB Seed — `scripts/init_render_db.py`

- Creates all tables via `Base.metadata.create_all()`
- **Idempotent** — skips if reviews already exist
- Seeds 4,605 reviews, 12 `weekly_runs`, 65 themes (T1–T5 weeks 1–7; T1–T6 weeks 8–12)

### Tech Stack — Phase 9

| Tool | Purpose |
|------|---------|
| **Flask 3.0** | Web framework + REST API |
| **SQLAlchemy 2.0** | ORM queries for summary and history |
| **SQLite** | Embedded DB (4,841 reviews, shipped in repo) |
| **Vanilla JS (ES6)** | Fetch API, async/await, DOM updates |
| **CSS custom properties** | Dark theme (`--green:#00C896`, `--card:#0D1626`) |
| **Fly.io** | Cloud hosting (Docker, region `sin`, 512 MB) |
| **Persistent Volume** | `groww_data` at `/app/data` (SQLite persistence) |

---

## Full Tech Stack Summary

### By Layer

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Runtime** | Python | 3.11 | Core language |
| **Runtime** | Node.js | LTS | Android scraper bridge |
| **Web Framework** | Flask | 3.0 | Dashboard + REST API |
| **ORM** | SQLAlchemy | 2.0 | DB models and queries |
| **Database** | SQLite | 3 | Embedded relational DB |
| **Vector Store** | ChromaDB | 0.5 | Embedding similarity search |
| **Embeddings** | BAAI/bge-small-en-v1.5 | — | 384-dim semantic vectors |
| **Clustering** | BERTopic | 0.16 | Topic modelling (primary) |
| **Clustering** | scikit-learn K-Means | 1.3 | Fallback clustering |
| **Dim Reduction** | UMAP | 0.5 | BERTopic preprocessing |
| **Density Cluster** | HDBSCAN | 0.8 | BERTopic preprocessing |
| **LLM** | Llama 3 (`llama3-8b-8192`) | — | Theme labeling + scoring |
| **LLM API** | Groq | 0.9 | Fast Llama 3 inference |
| **Language Detection** | langdetect + langid | 1.0 / 1.1 | Ensemble language ID |
| **NLP / NER** | spaCy `en_core_web_sm` | 3.7 | PII removal |
| **Data Processing** | pandas | 2.0 | CSV handling + aggregation |
| **Numerics** | numpy | 1.24 | Stats and surge detection |
| **Templating** | Jinja2 | 3.1 | Report HTML/Markdown generation |
| **Scheduler** | APScheduler | 3.10 | Monday 09:00 IST cron |
| **Timezone** | pytz | 2024.1 | IST timezone handling |
| **HTTP Client** | httpx | 0.24 | Async API calls |
| **CLI** | click | 8.1 | `manual_run.py` arguments |
| **Email Delivery** | Gmail API (MCP) | OAuth2 | Draft creation |
| **Docs Delivery** | Google Docs API (MCP) | OAuth2 | Report doc creation |
| **Auth** | Google OAuth2 | — | Refresh token flow |
| **iOS Scraping** | `app_store_reviews` | PyPI | App Store RSS client |
| **Android Scraping** | `google-play-scraper` | npm | Google Play reviews |
| **Config** | python-dotenv | 1.0 | `.env` loading |
| **Config** | PyYAML | 6.0 | `config.yaml` parsing |
| **Containerisation** | Docker | — | Image build + runtime |
| **Orchestration** | docker-compose | — | Local multi-service |
| **Cloud Hosting** | Fly.io | — | Production deployment (`sin`) |
| **Secrets (prod)** | Fly.io Secrets | — | `flyctl secrets set` |
| **Secrets (CI)** | GitHub Secrets | — | CI/CD injection |
| **CI/CD** | GitHub Actions | — | Lint, test, audit on push |
| **Testing** | pytest | 7.4 | Unit + integration tests |
| **Frontend** | Vanilla JS ES6 | — | Dashboard async interactions |
| **Styling** | CSS custom properties | — | Dark-green branded theme |

### By Phase

| Phase | Key Technologies |
|-------|-----------------|
| **Phase 0 — Setup** | Python 3.11, Node.js, Docker, Fly.io, GitHub, python-dotenv |
| **Phase 1 — Ingestion** | app_store_reviews, google-play-scraper, pandas, SQLAlchemy, SQLite, hashlib |
| **Phase 2 — Noise** | langdetect, langid, spaCy, regex, numpy |
| **Phase 3 — AI Engine** | sentence-transformers, BERTopic, HDBSCAN, UMAP, K-Means, ChromaDB, Groq Llama 3 |
| **Phase 4 — Reports** | Jinja2, pandas, SQLAlchemy, csv_archive |
| **Phase 5 — Scheduler** | APScheduler, pytz, click |
| **Phase 6 — MCP** | Gmail API, Google Docs API, Google OAuth2, httpx |
| **Phase 7 — Edge Cases** | scikit-learn, APScheduler grace time, Python logging |
| **Phase 8 — Security** | spaCy NER, Docker, GitHub Secrets, Fly.io Secrets |
| **Phase 9 — Dashboard** | Flask 3.0, SQLAlchemy, SQLite, Vanilla JS, CSS, Fly.io, Persistent Volume |

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Total reviews (Q1 2026) | **4,841** |
| Weeks analysed | **12** (Jan–Mar 2026) |
| Themes tracked | **6** (T1–T6) |
| Theme records in DB | **65** |
| Peak surge week | **Week 8 — 920 reviews** |
| Dominant Q1 issue | **Payments & Withdrawals (T2) — 9.2/10 urgency** |
| Python packages | **22** |
| Node packages | **1** (google-play-scraper) |
| API routes | **8** |
| Cloud region | **Singapore (sin)** |
| Deployment platform | **Fly.io** |
| Repository | **pyneayantika/groww-pulse** |

---

*Generated: April 2026 · Groww Pulse Agent v1.0*
