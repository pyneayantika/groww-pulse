# Groww Pulse Agent — Runbook

This document contains operational procedures, troubleshooting guides, and maintenance tasks for the Groww Pulse Agent system.

## Table of Contents

1. [System Overview](#system-overview)
2. [Daily Operations](#daily-operations)
3. [Weekly Operations](#weekly-operations)
4. [Report Generation](#report-generation)
5. [Troubleshooting](#troubleshooting)
6. [Maintenance](#maintenance)
7. [Emergency Procedures](#emergency-procedures)

---

## System Overview

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Weekly Scheduler (cron_runner.py)          │
│                         │                              │
│    ┌────────────────┴─────────────────┐    │
│    │  Ingestion     │  AI Processing     │  │
│    │  (iOS/Android) │  (Clustering+LLM)   │  │
│    │                  │  (Themes+Quotes)   │  │
│    └─────────────────┬─────────────────┘    │
│                         │                              │
│    ┌────────────────┴─────────────────┐    │
│  Database & Vector Store           │  Email & Docs Delivery      │
│  (SQLite + ChromaDB)            │  (Gmail + Google Docs)        │
│    └─────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

- **Scheduler**: APScheduler running Monday 09:00 IST
- **Ingestion**: iOS App Store + Google Play Store scrapers
- **AI Pipeline**: BERTopic clustering + Groq Llama 3 labeling
- **Vector Store**: ChromaDB for semantic search
- **Report Generation**: Weekly pulse reports (Markdown + HTML)
- **Delivery**: Gmail MCP + Google Docs MCP
- **Dashboard**: Flask web interface for monitoring

### Data Flow

1. **Reviews** → **Ingestion** → **Database** → **AI Processing** → **Reports**
2. **PII Protection**: Automatic stripping at ingestion + double-pass post-LLM
3. **Security**: Prompt injection prevention + system prompt hash guard
4. **Archiving**: 12-week rolling store with quarterly aggregation

---

## Daily Operations

### Morning Health Check (Daily 08:00 IST)

```bash
# Check system health
python scripts/health_check.py

# Expected output:
# ✓ Database connection: OK
# ✓ Vector store: OK  
# ✓ API keys: Valid
# ✓ Disk space: Available
# ✓ Scheduler: Running
```

### Monitor Logs (Daily 09:30, 13:30, 17:30 IST)

```bash
# Check recent pipeline logs
tail -f data/logs/groww_pulse.log

# Filter for errors
grep "ERROR\|FAIL" data/logs/groww_pulse.log --since="1 hour ago"

# Check scheduler status
python -c "from scheduler.cron_runner import get_scheduler_status; print(get_scheduler_status())"
```

### Review Weekly Status (Daily 18:00 IST)

```bash
# Check if weekly report was generated
python -c "
from storage.db import get_session
from storage.models import WeeklyRun
from datetime import datetime, timedelta

session = get_session()
last_week = session.query(WeeklyRun).filter(
    WeeklyRun.run_date >= datetime.now() - timedelta(days=7)
).order_by(WeeklyRun.run_date.desc()).first()

if last_week:
    print(f'Last run: Week {last_week.week_number} ({last_week.run_date})')
    print(f'Status: {last_week.status}')
    print(f'Themes: {last_week.themes_found}')
    print(f'Reviews: {last_week.reviews_kept}')
else:
    print('No completed runs in last 7 days')
session.close()
"
```

---

## Weekly Operations

### Pipeline Execution

#### Manual Full Pipeline

```bash
# Run complete pipeline
python scripts/manual_run.py full

# Monitor progress
tail -f data/logs/groww_pulse.log

# Expected phases:
# 1. Ingestion (5-10 min)
# 2. AI Processing (10-15 min)  
# 3. Report Generation (2-5 min)
# 4. Email Delivery (1-3 min)
```

#### Report Generation Only

```bash
# Generate weekly report for latest run
python scripts/manual_run.py weekly-report

# Generate for specific week
python scripts/manual_run.py weekly-report --week 17 --year 2025

# Generate quarterly report
python scripts/manual_run.py quarterly

# Generate different formats
python scripts/manual_run.py weekly-report --format html    # HTML only
python scripts/manual_run.py weekly-report --format md      # Markdown only
```

#### Ingestion Only

```bash
# Ingest reviews without AI processing
python scripts/manual_run.py ingest --days 7

# With custom CSV
python scripts/manual_run.py ingest --csv /path/to/reviews.csv
```

### Report Distribution

#### Automatic Delivery

- **Monday 09:00 IST**: Scheduler triggers automatically
- **Email Draft**: Created in Gmail drafts
- **Google Doc**: Generated with rich formatting
- **Archive**: Saved to `data/archive/`

#### Manual Distribution

```bash
# Send weekly report manually
python -c "
from mcp.gmail_client import send_draft
from report.weekly_report_generator import save_weekly_reports

# Generate and send
result = save_weekly_reports()
if 'draft_id' in result:
    send_draft(result['draft_id'])
    print('Weekly report sent via Gmail')
"
```

---

## Report Generation

### Weekly Report Formats

#### Markdown (`.md`)

- **Purpose**: Google Docs integration and version control
- **Size**: ≤250 words (enforced)
- **Sections**: Header, Stats, Themes, Quotes, Actions
- **Location**: `data/archive/groww_week_WW_YYYY_pulse.md`

#### HTML (`.html`)

- **Purpose**: Email delivery and web preview
- **Features**: Responsive design, print-friendly CSS
- **Interactive**: Theme cards, download buttons
- **Location**: `data/archive/groww_week_WW_YYYY_pulse.html`

#### Email Draft

- **Purpose**: Gmail integration
- **Location**: `data/archive/email_drafts/email_draft_week_WW_YYYY.html`
- **Format**: Same as HTML report

### Quarterly Report

- **Scope**: 12 weeks of data aggregation
- **Features**: Heatmap, regressions, quotes archive, action backlog
- **Location**: `data/archive/groww_qN_YYYY_quarterly_report.md`

---

## Troubleshooting

### Common Issues

#### Pipeline Failures

**Symptoms**: Pipeline stops without completion
**Causes**: 
- API key issues
- Database connection problems
- Network timeouts
- Insufficient reviews (<10 English reviews)

**Diagnostics**:
```bash
# Check API keys
python scripts/check_env.py

# Check database
python scripts/check_db.py

# Check recent logs
grep "ERROR\|FAIL" data/logs/groww_pulse.log --since="1 hour ago"

# Test individual components
python scripts/manual_run.py test
```

**Resolution Steps**:
1. Verify API keys in `.env`
2. Check database connectivity
3. Ensure minimum 10 English reviews
4. Run component tests individually

#### Report Generation Issues

**Symptoms**: Reports not generated or incomplete
**Causes**:
- Database connection issues
- Missing theme data
- Template rendering errors
- File permission problems

**Diagnostics**:
```bash
# Test report generator directly
python -c "
from report.weekly_report_generator import build_weekly_report
data = build_weekly_report(week_number=1, year=2025)
print('Data keys:', list(data.keys()))
print('Top themes:', len(data.get('top_themes', [])))
"

# Test rendering
python -c "
from report.weekly_report_generator import render_weekly_markdown, render_weekly_html
test_data = {'week_number': 1, 'year': 2025, 'top_themes': []}
md = render_weekly_markdown(test_data)
html = render_weekly_html(test_data)
print('Markdown length:', len(md.split()))
print('HTML generated successfully:', bool(html))
"
```

**Resolution Steps**:
1. Check database for completed runs
2. Verify theme data exists
3. Test template rendering separately
4. Check file permissions on archive directory

#### Performance Issues

**Symptoms**: Slow processing or timeouts
**Causes**:
- Large review volumes (>1000/week)
- Embedding model loading delays
- Vector store indexing issues

**Optimizations**:
- Use secondary embedding models
- Implement review sampling limits
- Optimize ChromaDB queries

### Error Codes Reference

| Code | Component | Description | Action |
|------|-----------|------------|--------|---------|---------|
| E001 | Ingestion | No reviews found | Check app store status |
| E002 | Ingestion | CSV parse error | Validate CSV format |
| E003 | Database | Connection failed | Check DB_URL |
| E004 | AI | LLM timeout | Check GROQ_API_KEY |
| E005 | AI | Clustering failed | Check review volume |
| E006 | Reports | File permission error | Check data/archive perms |
| E007 | MCP | Gmail auth failed | Check Google OAuth |
| E008 | MCP | Google Docs error | Check permissions |

---

## Maintenance

### Weekly Tasks (Every Monday)

#### Database Maintenance

```bash
# Clean old archives (older than 12 weeks)
python -c "
from storage.csv_archive import rotate_archive
deleted = rotate_archive()
print(f'Deleted {deleted} old archive files')
"

# Optimize database
python -c "
from storage.db import get_session
from storage.models import WeeklyRun
import sqlite3

session = get_session()
conn = session.bind.raw_connection()
cursor = conn.cursor()

# Vacuum database
cursor.execute('VACUUM')
conn.commit()

# Update statistics
cursor.execute('ANALYZE')
conn.commit()

print('Database optimization completed')
session.close()
"
```

#### Vector Store Maintenance

```bash
# Rebuild ChromaDB index
python -c "
from storage.vector_store import init_collection
init_collection(rebuild=True)
print('ChromaDB index rebuilt')
"
```

#### Log Rotation

```bash
# Rotate logs (keep last 30 days)
find data/logs/ -name "*.log" -mtime +30 -delete
print('Log rotation completed')
```

### Monthly Tasks

#### Security Scans

```bash
# Check for exposed secrets
python scripts/check_secrets.py

# Update dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip audit --requirement requirements.txt
npm audit --audit-level=high
```

#### Performance Monitoring

```bash
# Generate performance report
python scripts/performance_report.py

# Expected output:
# Average processing time: 12.5 minutes
# Peak memory usage: 512MB
# Success rate: 98.2%
```

---

## Emergency Procedures

### Pipeline Recovery

#### Complete System Failure

```bash
# Emergency manual run with force flag
python scripts/manual_run.py full --force

# Clear any stuck scheduler locks
python -c "
from scheduler.cron_runner import clear_scheduler_locks
clear_scheduler_locks()
print('Scheduler locks cleared')
"
```

#### Data Recovery

```bash
# Restore from most recent good state
python scripts/restore_from_backup.py

# Rebuild from archive
python scripts/rebuild_from_archive.py
```

### Service Restoration

#### Gmail MCP Issues

```bash
# Test Gmail connection
python -c "
from mcp.gmail_client import test_connection
success = test_connection()
print(f'Gmail MCP status: {"OK" if success else "FAILED"}')
"

# Re-authenticate if needed
python scripts/reauthenticate_gmail.py
```

#### Google Docs MCP Issues

```bash
# Test Google Docs connection  
python -c "
from mcp.gdocs_client import test_permissions
success = test_permissions()
print(f'Google Docs MCP status: {"OK" if success else "FAILED"}')
"
```

---

## Contact Information

### Primary Contacts

- **System Administrator**: For infrastructure issues
- **Development Team**: For code bugs and feature requests
- **Operations Team**: For daily operational issues

### Escalation Matrix

| Severity | Response Time | Escalation Path |
|----------|----------------|------------------|
| Critical | 1 hour | System Administrator |
| High | 4 hours | Development Team |
| Medium | 24 hours | Development Team |
| Low | 72 hours | Operations Team |

### Incident Reporting

When reporting issues, include:
1. **Timestamp**: ISO 8601 format
2. **Error Code**: From reference table
3. **System State**: Current scheduler status
4. **Steps Taken**: Troubleshooting actions performed
5. **Expected Resolution**: Timeline for fix

---

## Monitoring and Alerting

### Key Metrics

- **Pipeline Success Rate**: Target >95%
- **Average Processing Time**: Target <15 minutes
- **Report Generation Time**: Target <5 minutes
- **System Availability**: Target >99%

### Alert Thresholds

- **Pipeline Failure**: Immediate alert via email
- **Performance Degradation**: Warning at >20 minutes processing
- **Storage Capacity**: Warning at >80% disk usage
- **API Rate Limits**: Warning at >80% usage

### Dashboard Monitoring

Access `http://localhost:5000` for:
- Real-time pipeline status
- Historical performance metrics
- System health indicators
- Manual trigger capabilities

---

## Security Procedures

### Access Control

- **API Keys**: Stored in `.env` with restricted file permissions
- **Database**: Local SQLite with encryption at rest
- **Email**: Domain restrictions enabled by default
- **Services**: Internal network only for external connections

### Backup Procedures

#### Daily Backups

```bash
# Backup database and archives
python scripts/daily_backup.py

# Targets:
# - data/groww_pulse.db
# - data/archive/
# - .chroma/
```

#### Weekly Backups

```bash
# Create weekly backup snapshot
python scripts/weekly_backup.py
```

### Change Management

#### Software Updates

1. **Test Environment**: Staging deployment first
2. **Rolling Updates**: One component at a time
3. **Rollback Plan**: Previous version preservation
4. **Communication**: 48-hour advance notice for changes

---

## Version Information

- **Current Version**: 1.0.0
- **Last Updated**: 2025-04-25
- **Compatibility**: Python 3.11+, Node.js 18+
- **Dependencies**: See `requirements.txt` and `package.json`

---

*This runbook is maintained alongside the codebase. Update procedures when adding new features or modifying existing workflows.*
