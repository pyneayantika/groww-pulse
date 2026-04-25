import sqlite3, csv
from pathlib import Path
from datetime import datetime

conn = sqlite3.connect('data/groww_pulse.db')

print('Exporting all reviews to CSV...')

rows = conn.execute('''
    SELECT
        review_id,
        store,
        rating,
        title,
        text,
        date,
        app_version,
        language_detected,
        language_confidence,
        is_duplicate,
        pii_stripped,
        suspicious_review,
        week_number
    FROM reviews
    ORDER BY date DESC, store ASC
''').fetchall()

columns = [
    'review_id',
    'store',
    'rating',
    'title',
    'text',
    'date',
    'app_version',
    'language_detected',
    'language_confidence',
    'is_duplicate',
    'pii_stripped',
    'suspicious_review',
    'week_number'
]

out = Path('data/archive')
out.mkdir(parents=True, exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
csv_path = out / f'groww_all_reviews_{timestamp}.csv'

with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(columns)
    writer.writerows(rows)

print(f'Total rows exported : {len(rows)}')
print(f'Columns             : {len(columns)}')
print(f'File saved          : {csv_path}')
print()
print('COLUMN DESCRIPTIONS:')
print('-' * 50)
print('  review_id          : Unique SHA-256 hash')
print('  store              : ios / android')
print('  rating             : 1-5 stars')
print('  title              : Review title')
print('  text               : Full review text')
print('  date               : Review date YYYY-MM-DD')
print('  app_version        : Groww app version')
print('  language_detected  : en (English only)')
print('  language_confidence: 0.90 to 1.0')
print('  is_duplicate       : 0=unique 1=duplicate')
print('  pii_stripped       : 1=PII removed')
print('  suspicious_review  : 1=rating mismatch')
print('  week_number        : ISO week number')
print()
print('Opening CSV...')

import subprocess
subprocess.Popen(['explorer', str(csv_path.parent)])

conn.close()
print('DONE')
