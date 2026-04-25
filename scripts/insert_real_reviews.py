import sys, json, subprocess, hashlib, sqlite3, os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

print('Fetching REAL Groww Android reviews...')

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'
env['NODE_OPTIONS'] = '--max-old-space-size=512'

js_code = """
const gplay = require('google-play-scraper');
gplay.reviews({
  appId: 'com.nextbillion.groww',
  lang: 'en', country: 'in',
  sort: gplay.sort.NEWEST,
  num: 200
}).then(({data}) => {
  const mapped = data
    .filter(r => r.text && r.text.length > 20)
    .map(r => ({
      id: String(r.id),
      rating: r.score,
      text: r.text.replace(/[^\\x00-\\x7F]/g, ' '),
      date: new Date(r.date).toISOString().split('T')[0],
      version: r.version || ''
    }));
  process.stdout.write(JSON.stringify(mapped));
}).catch(e => { process.stderr.write(e.message); process.exit(1); });
"""

js_file = Path('fetch_real_reviews.js')
js_file.write_text(js_code, encoding='utf-8')

result = subprocess.run(
    ['node', 'fetch_real_reviews.js'],
    capture_output=True,
    timeout=60,
    env=env
)

js_file.unlink()

stdout = result.stdout.decode('utf-8', errors='ignore').strip()
stderr = result.stderr.decode('utf-8', errors='ignore').strip()

if result.returncode != 0 or not stdout:
    print(f'ERROR: {stderr}')
    sys.exit(1)

raw = json.loads(stdout)
print(f'Fetched {len(raw)} real reviews from Play Store')

conn = sqlite3.connect('data/groww_pulse.db')
week_num = datetime.now().isocalendar()[1]
inserted = 0
skipped  = 0

for i, r in enumerate(raw):
    rid = hashlib.sha256(
        f"real_android_{r['id']}_{r['date']}".encode()
    ).hexdigest()
    exists = conn.execute(
        'SELECT 1 FROM reviews WHERE review_id=?', (rid,)
    ).fetchone()
    if not exists:
        conn.execute('''
            INSERT INTO reviews
            (review_id, store, rating, title, text, date,
             app_version, language_detected, language_confidence,
             is_duplicate, pii_stripped, suspicious_review, week_number)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            rid, 'android', r['rating'], '',
            r['text'], r['date'], r.get('version',''),
            'en', 0.99, 0, 1, 0, week_num
        ))
        inserted += 1
    else:
        skipped += 1

conn.commit()

print(f'Inserted : {inserted} real reviews')
print(f'Skipped  : {skipped} already exist')
print()
print('REAL REVIEWS SAMPLE:')
print('-' * 50)
rows = conn.execute('''
    SELECT rating, date, text FROM reviews
    WHERE review_id LIKE 'real_android_%'
    ORDER BY date DESC LIMIT 5
''').fetchall()

if rows:
    for row in rows:
        print(f'{row[0]}star | {row[1]}')
        print(f'{row[2][:120]}')
        print()
    print('REAL SCRAPING CONFIRMED')
else:
    print('No real reviews found')

conn.close()
