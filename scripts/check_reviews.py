import sys, sqlite3, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

db_path = os.getenv('DB_URL', 'sqlite:///data/groww_pulse.db').replace('sqlite:///', '')
conn = sqlite3.connect(db_path)

total      = conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
ios        = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='ios'").fetchone()[0]
android    = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='android'").fetchone()[0]
english    = conn.execute("SELECT COUNT(*) FROM reviews WHERE language_detected='en'").fetchone()[0]
pii_clean  = conn.execute('SELECT COUNT(*) FROM reviews WHERE pii_stripped=1').fetchone()[0]
dupes      = conn.execute('SELECT COUNT(*) FROM reviews WHERE is_duplicate=1').fetchone()[0]
suspicious = conn.execute('SELECT COUNT(*) FROM reviews WHERE suspicious_review=1').fetchone()[0]
latest     = conn.execute('SELECT date FROM reviews ORDER BY date DESC LIMIT 1').fetchone()
oldest     = conn.execute('SELECT date FROM reviews ORDER BY date ASC LIMIT 1').fetchone()

print()
print('=' * 45)
print('  REVIEW EXTRACTION SUMMARY')
print('=' * 45)
print(f'  Total reviews      : {total}')
print(f'  iOS reviews        : {ios}')
print(f'  Android reviews    : {android}')
print(f'  English only       : {english}')
print(f'  PII stripped       : {pii_clean}')
print(f'  Duplicates removed : {dupes}')
print(f'  Suspicious flagged : {suspicious}')
print(f'  Date range         : {oldest[0] if oldest else "N/A"} to {latest[0] if latest else "N/A"}')
print('=' * 45)

print()
print('RATING DISTRIBUTION')
print('-' * 35)
for store in ['ios', 'android']:
    print(f'\n  {store.upper()}:')
    for stars in [5, 4, 3, 2, 1]:
        count = conn.execute(
            'SELECT COUNT(*) FROM reviews WHERE store=? AND rating=?',
            (store, stars)
        ).fetchone()[0]
        bar = '' * min(count // 3, 30) if count > 0 else ''
        print(f'    {stars} stars  {bar} {count}')

conn.close()
