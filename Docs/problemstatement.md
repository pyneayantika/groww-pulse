Groww Weekly Review Intelligence System — Quarterly Pulse Engine
Version: 1.0 | Scope: Q1 2025 (Jan–Mar) | Target App: Groww (Stocks, MF & Gold App)
2. Problem Definition
2.1 Stakeholder Pain Map
The table below identifies who is affected, how they suffer today, and what happens without this system:

Stakeholder	Current Pain	Without This System
Product Managers	Manually scroll reviews on weekends	Miss regression signals 2–3 weeks late
Growth Teams	No structured churn signal from reviews	Cannot correlate app ratings to D7/D30 retention
Support Teams	Reactive to escalations only	Repeated issues flagged 100x go unacknowledged
Leadership / C-Suite	No voice-of-customer health metric	App Store rating drops surprise executives

2.2 Scale of the Problem
The following estimates are derived from public App Store data and industry benchmarks for fintech apps of comparable scale:
•	Groww receives approximately 300–900 new reviews per week across both stores
•	Review volume surges during market events: IPO listings, SEBI rule changes, market crashes, app version releases
•	Approximately 65–70% of reviews are in English; the remainder are in Hindi and regional languages (excluded from this scope)
•	Average review-to-action latency without automation: 14–21 days
•	Without a theme taxonomy, individual PMs interpret the same reviews differently, leading to conflicting product priorities

2.3 Root Causes
1.	No ingestion pipeline: Reviews are read manually from App Store Connect and Play Console with no programmatic access
2.	No language filtering: Hindi and English reviews are mixed, making aggregate analysis unreliable
3.	No deduplication: The same user complaint posted on both stores is counted twice
4.	No theme taxonomy: Product teams have no shared vocabulary for classifying review types
5.	No trend tracking: There is no week-over-week view showing whether a problem is improving or worsening
6.	No delivery mechanism: Insights never reach leadership or support teams in a structured, timely format

 
3. Objectives
This system must achieve the following measurable goals by the end of Q1 2025:

#	Objective	Target Metric
1	Reduce review-to-insight latency	21 days → < 2 hours (Monday 09:00 IST run)
2	Zero-manual-effort weekly pulse delivery	0 manual steps after initial setup
3	Structured theme surfacing	≤5 actionable themes per week
4	User voice representation (PII-free)	3 representative quotes per weekly note
5	MCP-based delivery integration	Google Docs + Gmail fully automated
6	12-week rolling quarterly archive	100% English review capture retained
7	Edge case resilience	≥95% weekly run success rate across 12 weeks

 
4. Key Constraints
4.1 Data & Privacy Constraints
•	Public review exports only — no scraping behind authenticated logins
•	No PII in any artifact: no usernames, emails, phone numbers, PAN/Aadhaar numbers
•	All review text must pass through a two-pass PII stripper (regex + NER) before any LLM processing
•	CSV archives must store only pii_stripped = True rows; raw data is git-ignored

4.2 Scope Constraints
•	English-language reviews only (langdetect confidence ≥ 0.90)
•	Maximum 5 themes per weekly report — no exceptions
•	Weekly pulse note body: ≤ 250 words
•	Date window: last 12 weeks (84 days) on initial run; weekly delta on subsequent runs
•	Both iOS App Store and Google Play Store must be included in every run

4.3 Technical Constraints
•	Scheduler must run on Monday 09:00 IST (Asia/Kolkata timezone)
•	LLM calls capped at max_tokens = 1000 per request to control cost
•	Google Docs MCP and Gmail MCP are the only permitted delivery channels
•	No auto-send of email unless AUTO_SEND=true is explicitly set in .env configuration
•	All secrets (API keys, OAuth tokens) stored in .env or GitHub Secrets — never committed to source control

 
5. Implementation Plan
The system is built across nine sequential phases. Each phase has defined inputs, outputs, and acceptance criteria.

Phase 0 — Project Setup & Folder Organization
Establish the project scaffold, environment configuration, and dependency baseline before any code is written.
Key folder structure:
•	ingestion/ — scrapers, language filter, PII stripper, deduplicator
•	storage/ — SQLite/Postgres ORM, vector store client, CSV archive manager
•	ai/ — embedder, clusterer, LLM labeler, urgency scorer, quote selector
•	report/ — pulse builder, email composer, Jinja2 templates
•	mcp/ — Google Docs client, Gmail client
•	scheduler/ — APScheduler cron runner (Monday 09:00 IST)
•	tests/ — ingestion tests, AI pipeline tests, edge case tests, security tests
•	data/ — raw/ (gitignored), processed/, archive/ (12-week rolling)

Phase 1 — Data Ingestion
Ingest reviews from both stores using publicly available, non-authenticated libraries.

Platform	Library	Method	Rate Limit
iOS App Store	app_store_reviews (PyPI)	RSS feed + pagination	~500 reviews/call
Google Play	google-play-scraper (npm)	Unofficial public API	~200 reviews/call
CSV Fallback	pandas read_csv	Manual / Kaggle exports	Unlimited

Each review is stored with a standardized schema: review_id (hash of store+id+date), store, rating, title, text, date, app_version, language_detected, language_confidence, is_duplicate, and pii_stripped flags.
Date range logic: Collect reviews from today minus 84 days on initial run. Subsequent Monday runs collect from last_run_date to now and merge into the rolling archive.

Phase 2 — Noise Management
Noise management is where most naive implementations fail. Groww’s review ecosystem has specific noise patterns that must be handled before any AI processing.

Noise Type	Example	Filter Strategy
Language noise	Non-English review posted with English words	langdetect confidence > 0.90 for English
Rating without text	3 stars, no body text	Drop if len(text) < 20 characters
Spam / bot reviews	Repeated phrase pattern	Repetition ratio > 0.4 → flag and discard
Duplicate cross-store	Same review on iOS and Android	SHA-256 hash of normalized text
Version-specific noise	Old bug already fixed	Tag app_version, weight by recency
Rating-text mismatch	5 stars with ‘terrible’ text	Flag suspicious_review = True
Surge week	300% review spike on crash day	Sample 500 reviews stratified by rating

Phase 3 — AI Theme Mapping Engine
The theme mapping engine uses a three-step hybrid approach: embedding, clustering, then LLM labeling. This is more reproducible, explainable, and cost-efficient than a pure-LLM approach.

Step 1 — Embedding
Model	Pros	Cons	Role
BAAI/bge-small-en-v1.5	Free, local, 384-dim, strong fintech relevance	Requires local GPU/CPU inference	Primary
all-MiniLM-L6-v2	Fast, free, lightweight	Lower domain specificity	Fallback

Step 2 — Clustering (Theme Discovery)
Primary algorithm: BERTopic. It is the correct choice for this domain because it automatically determines meaningful topic count (bounded to 5 via nr_topics=5), uses c-TF-IDF which preserves fintech vocabulary (KYC, SIP, portfolio, withdrawal), produces human-readable keyword representations per cluster, and handles the class imbalance common in app reviews.
Fallback: K-Means (k=5) on embeddings when BERTopic produces degenerate clusters, which occurs with fewer than 50 reviews per week.

Step 3 — LLM Labeling & Scoring
After clustering, the top 15 reviews per cluster are passed to groq LLM with a structured prompt requesting theme label, urgency score (1–10), sentiment score (-1 to +1), volume count, a representative anonymized quote, and trend direction. Output is constrained to JSON schema only.

Pre-defined Theme Taxonomy for Groww
ID	Label	Sample Keywords
T1	Onboarding & KYC	account creation, verification failed, documents, stuck, waiting
T2	Payments & Withdrawals	money stuck, transaction failed, bank not linked, UPI error
T3	Portfolio & Performance	returns wrong, P&L incorrect, graph broken, holdings missing
T4	App Stability & UX	crash, slow, login loop, OTP not received, black screen
T5	Customer Support	no response, chat useless, ticket ignored, refund not given

Phase 4 — Quarterly Report Structure (12-Week View)
Unlike a single weekly pulse, the quarterly report aggregates 12 weekly snapshots to reveal trends, regressions, and seasonal patterns. This is what makes it genuinely valuable for leadership-level consumption.
Quarterly report sections:
7.	Executive Summary — App Store rating trend (12-week sparkline), total review volume, overall sentiment trajectory
8.	Theme Heatmap — Week × theme matrix colored by urgency score; shows which themes dominated each week
9.	Top Regressions — Themes that worsened week-over-week for 3 or more consecutive weeks
10.	Verbatim Quotes Archive — 3 representative PII-free quotes per theme per quarter (up to 15 total)
11.	Action Backlog — All generated action ideas tagged as Open, In-Progress, or Resolved
12.	Seasonal Observations — Correlation with external market events such as IPO weeks and SEBI announcements

Phase 5 — Scheduler Design
The scheduler uses APScheduler with CronTrigger configured for Monday 09:00 IST (Asia/Kolkata timezone). The run sequence is: ingest new reviews, clean and filter, map themes, build the pulse note, push to Google Docs via MCP, send the email via Gmail MCP, archive to CSV, and log run metadata.
On failure, the system triggers an alert via Slack webhook or email fallback. Retry logic: exponential backoff (2s, 4s, 8s) with a maximum of 3 retries per external API call.

Phase 6 — MCP Server Integration
Google Docs MCP Workflow
13.	Authenticate via OAuth2 service account
14.	Create a new document titled: Groww Weekly Pulse — Week of YYYY-MM-DD
15.	Apply structured formatting: H1 title, H2 sections (Themes, Quotes, Actions)
16.	Apply Groww brand color #00B386 to heading styles via Docs API
17.	Insert theme table (rank, theme, volume, urgency, trend direction)
18.	Insert quote callout blocks styled as block-quotes
19.	Insert action ideas as a numbered list
20.	Set sharing to view-only link (no public auto-share)
21.	Return document URL for embedding in the email

Gmail MCP Workflow
22.	Compose email with subject: Groww App Pulse — Week WW, YYYY
23.	Recipients: configurable via RECIPIENT_LIST in .env (default: self/alias only)
24.	Body: HTML-formatted pulse note, scannable inline
25.	Attachment: link to Google Doc (not PDF, to avoid attachment size limits)
26.	Create as DRAFT first — human review step before sending
27.	Auto-send only if AUTO_SEND=true is explicitly set in .env

 
Phase 7 — Edge Case Handling
The following edge cases have been identified and must be handled gracefully by the system:

Edge Case	Detection Method	Handling Strategy
Zero new reviews this week	len(reviews) == 0	Skip AI pipeline; send a ‘No new reviews’ notification email
App Store API rate limit (429)	HTTP status code check	Exponential backoff; fallback to CSV after 3 retries
All reviews non-English	english_count < 10	Alert: Insufficient English reviews for theme analysis
BERTopic < 3 clusters	len(topics) < 3	Fall back to K-Means k=3; flag in report
LLM API timeout (>30s)	Response time check	Retry once; use keyword-based fallback labeling
Duplicate Google Doc creation	Week ID already exists	Check before creating; skip or overwrite on re-run
Review text >10,000 chars	len(text) check	Truncate to first 1,000 chars + [truncated] marker
Market crash surge week	Volume > 3x weekly median	Surge mode: stratified sample of 500 reviews by rating
Rating-text mismatch	Sentiment vs. rating delta > 1.5	Flag suspicious_review = True; include in noise log

Phase 8 — Security Testing

Attack Surface	Risk	Mitigation
App Store scraper IP block	Scraper detected and banned	Rotate user-agents; rate-limit to 1 request per 2 seconds
LLM prompt injection via reviews	Malicious review hijacks prompt	Wrap review text in XML tags; never concatenate raw text into system prompt
PII leakage in output	User phone or email in report	Double-pass PII check: pre-LLM (regex) + post-LLM (regex rescan)
Google OAuth token exposure	.env committed to git	.env in .gitignore; use GitHub Secrets / AWS Secrets Manager
Email sent to wrong recipient	Misconfigured .env	Default recipient = self/alias only; team list requires explicit flag
Scheduler privilege escalation	Cron job running as root	Run as dedicated groww-pulse Linux user with no sudo
Dependency vulnerabilities	Outdated packages	pip-audit + npm audit in CI/CD; weekly Dependabot PRs

Phase 9 — Quarterly Deliverables
After 12 successful weekly runs, the system automatically generates the following deliverables:

•	groww_q1_2025_pulse_report.md — Full 12-week aggregate (themes, trend lines, all quotes, all action ideas)
•	groww_reviews_q1_2025.csv — Redacted reviews archive with columns: review_id, store, rating, title_clean, text_clean, date, week_number, theme_assigned, urgency_score
•	email_draft_week_N.html — Weekly email draft screenshots or text (12 files total)
•	README.md — Full re-run instructions for any subsequent quarter

 
6. Recommended Technology Stack

Layer	Technology	Rationale
Language	Python 3.11	Rich ML and scraping ecosystem
iOS Ingestion	app_store_reviews (PyPI)	Simple, maintained, no login required
Android Ingestion	google-play-scraper (npm)	Most reliable unofficial Play Store API
Language Detection	langdetect + langid ensemble	Higher accuracy than any single model
PII Removal	spaCy en_core_web_sm + regex	Fast, lightweight, covers named entities
Embeddings	BAAI/bge-small-en-v1.5	Best fintech-domain quality at scale
Clustering	BERTopic	Topic coherence + keyword transparency; max k=5
LLM Labeling	Llama 3/ Groq model	Structured JSON, reliable instruction-following
Vector DB	ChromaDB	Local-first, no infrastructure overhead
Relational DB	SQLite (dev) / Postgres (prod)	Familiar, portable, simple schema
Scheduler	APScheduler	Python-native, timezone-aware cron support
Docs Delivery	Google Docs MCP (drivemcp.googleapis.com)	Native GDoc creation and formatting
Email Delivery	Gmail MCP (gmailmcp.googleapis.com)	Draft creation and controlled send
Containerization	Docker + docker-compose	Reproducible environment across machines
CI/CD	GitHub Actions	Lint, test, pip-audit on every push
Secrets Management	.env (local) / GitHub Secrets (CI)	Standard, auditable, never committed
