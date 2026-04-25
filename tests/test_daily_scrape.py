import sys, os, sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

print('Testing daily scrape manually...')
print()

from ingestion.android_scraper import fetch_android_reviews
from ingestion.language_filter import filter_english
from ingestion.pii_stripper import strip_pii
from ingestion.deduplicator import deduplicate
from storage.db import init_db, session_scope
from storage.models import Review
from datetime import datetime

init_db()
week_num = datetime.now().isocalendar()[1]

app_id = os.getenv('ANDROID_APP_ID', 'com.nextbillion.groww')
print(f'Fetching from: {app_id}')

reviews = fetch_android_reviews(app_id, days_back=1)
print(f'Raw fetched    : {len(reviews)}')

english = filter_english(reviews)
print(f'English kept   : {len(english)}')

deduped = deduplicate(english)
print(f'After dedup    : {len(deduped)}')

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
        except Exception:
            continue

db = os.getenv(
    'DB_URL', 'sqlite:///data/groww_pulse.db'
).replace('sqlite:///', '')
conn = sqlite3.connect(db)
total = conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
android = conn.execute(
    "SELECT COUNT(*) FROM reviews WHERE store='android'"
).fetchone()[0]
conn.close()

print()
print('RESULT:')
print(f'  Inserted today : {inserted} new reviews')
print(f'  Skipped (dupes): {skipped}')
print(f'  Total in DB    : {total:,}')
print(f'  Android total  : {android:,}')
print()

if inserted > 0:
    print('DAILY SCRAPE TEST PASSED')
    print(f'Running daily will accumulate ~{inserted}/day')
    print(f'After 30 days = ~{inserted * 30} real reviews')
else:
    print('0 new reviews today')
    print('Reviews may already be in DB from earlier today')
    print(f'Existing Android reviews: {android:,}')
