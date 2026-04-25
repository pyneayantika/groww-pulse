import logging, os, pytz
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger('groww-pulse')

IST = pytz.timezone('Asia/Kolkata')
scheduler = BlockingScheduler(timezone=IST)


# ── JOB 1: Daily scrape at 09:00 IST ─────────────────────────
# Runs every day — scrapes and stores fresh reviews
# No AI pipeline, no report, no email
# Accumulates ~150-200 real reviews per day

@scheduler.scheduled_job(
    CronTrigger(hour=9, minute=0, timezone=IST),
    id='daily_scrape',
    max_instances=1,
    misfire_grace_time=3600
)
def daily_scrape():
    log.info('DAILY SCRAPE STARTED — %s',
             datetime.now(IST).strftime('%Y-%m-%d %H:%M IST'))
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))

        from ingestion.android_scraper import fetch_android_reviews
        from ingestion.language_filter import filter_english
        from ingestion.pii_stripper import strip_pii
        from ingestion.deduplicator import deduplicate
        from storage.db import init_db, session_scope
        from storage.models import Review
        from datetime import datetime as dt

        init_db()
        week_num = dt.now().isocalendar()[1]

        app_id = os.getenv('ANDROID_APP_ID', 'com.nextbillion.groww')
        log.info('Fetching Android reviews for %s...', app_id)
        reviews = fetch_android_reviews(app_id, days_back=1)
        log.info('Fetched %d raw reviews', len(reviews))

        if not reviews:
            log.warning('No reviews fetched today')
            return

        english = filter_english(reviews)
        log.info('English reviews: %d', len(english))

        deduped = deduplicate(english)
        log.info('After dedup: %d', len(deduped))

        cleaned = [strip_pii(r) for r in deduped]

        inserted = 0
        skipped = 0
        with session_scope() as session:
            for r in cleaned:
                try:
                    r['week_number'] = week_num
                    exists = session.query(Review).filter(
                        Review.review_id == r['review_id']
                    ).first()
                    if not exists:
                        session.add(Review(
                            review_id=r.get('review_id', ''),
                            store='android',
                            rating=int(r.get('rating', 0)),
                            title=str(r.get('title', '')),
                            text=str(r.get('text', '')),
                            date=str(r.get('date', '')),
                            app_version=str(r.get('app_version', '')),
                            language_detected='en',
                            language_confidence=float(
                                r.get('language_confidence', 0.95)
                            ),
                            is_duplicate=False,
                            pii_stripped=True,
                            suspicious_review=bool(
                                r.get('suspicious_review', False)
                            ),
                            week_number=week_num
                        ))
                        inserted += 1
                    else:
                        skipped += 1
                except Exception as e:
                    log.warning('Insert error: %s', e)
                    continue

        log.info(
            'DAILY SCRAPE DONE — inserted=%d skipped=%d week=%d',
            inserted, skipped, week_num
        )

    except Exception as e:
        import traceback
        log.error('DAILY SCRAPE FAILED: %s\n%s', e, traceback.format_exc())


# ── JOB 2: Monday full pipeline at 09:05 IST ─────────────────
# Runs every Monday — full AI pipeline + report + email
# 5 min offset so daily scrape finishes first

@scheduler.scheduled_job(
    CronTrigger(day_of_week='mon', hour=9, minute=5, timezone=IST),
    id='weekly_pulse',
    max_instances=1,
    misfire_grace_time=3600
)
def weekly_pipeline():
    log.info('WEEKLY PIPELINE STARTED — %s',
             datetime.now(IST).strftime('%Y-%m-%d %H:%M IST'))
    try:
        from scheduler.orchestrator import run_weekly_pipeline
        result = run_weekly_pipeline()
        log.info(
            'WEEKLY PIPELINE DONE — status=%s',
            result.get('status')
        )
    except Exception as e:
        import traceback
        log.error(
            'WEEKLY PIPELINE FAILED: %s\n%s',
            e, traceback.format_exc()
        )


# ── JOB 3: Weekly CSV export on Sunday 23:00 IST ─────────────
# Auto-generates all weekly CSVs before Monday report

@scheduler.scheduled_job(
    CronTrigger(day_of_week='sun', hour=23, minute=0, timezone=IST),
    id='weekly_csv_export',
    max_instances=1,
    misfire_grace_time=1800
)
def weekly_csv_export():
    log.info('CSV EXPORT STARTED')
    try:
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, 'scripts/generate_all_csvs.py'],
            capture_output=True, text=True
        )
        log.info('CSV EXPORT DONE:\n%s', result.stdout)
        if result.returncode != 0:
            log.error('CSV EXPORT ERROR:\n%s', result.stderr)
    except Exception as e:
        log.error('CSV EXPORT FAILED: %s', e)


# ── STARTUP ───────────────────────────────────────────────────
if __name__ == '__main__':
    log.info('=' * 55)
    log.info('  GROWW PULSE SCHEDULER STARTING')
    log.info('  Timezone: Asia/Kolkata (IST)')
    log.info('=' * 55)
    log.info('')
    log.info('SCHEDULED JOBS:')
    log.info('  1. Daily Scrape     -> Every day    09:00 IST')
    log.info('  2. Weekly Pipeline  -> Every Monday 09:05 IST')
    log.info('  3. CSV Export       -> Every Sunday 23:00 IST')
    log.info('')
    log.info('ACCUMULATION FORECAST:')
    log.info('  Day 1    : ~150 real reviews')
    log.info('  Week 1   : ~1,050 real reviews')
    log.info('  Month 1  : ~4,500 real reviews')
    log.info('  Month 3  : ~13,500 real reviews')
    log.info('')
    log.info('Scheduler running. Press Ctrl+C to stop.')
    log.info('=' * 55)

    try:
        scheduler.start()
    except KeyboardInterrupt:
        log.info('Scheduler stopped by user.')
