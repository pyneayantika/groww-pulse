import sqlite3
conn = sqlite3.connect('data/groww_pulse.db')

print('=' * 50)
print('  FILTER STATS — Current Database')
print('=' * 50)

total      = conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
english    = conn.execute("SELECT COUNT(*) FROM reviews WHERE language_detected='en'").fetchone()[0]
pii_clean  = conn.execute('SELECT COUNT(*) FROM reviews WHERE pii_stripped=1').fetchone()[0]
no_dupes   = conn.execute('SELECT COUNT(*) FROM reviews WHERE is_duplicate=0').fetchone()[0]
suspicious = conn.execute('SELECT COUNT(*) FROM reviews WHERE suspicious_review=1').fetchone()[0]
ios_count  = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='ios'").fetchone()[0]
android    = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='android'").fetchone()[0]

print(f'  Total in DB        : {total}')
print(f'  English only       : {english}')
print(f'  PII stripped       : {pii_clean}')
print(f'  Duplicates removed : {total - no_dupes}')
print(f'  Suspicious flagged : {suspicious}')
print(f'  iOS reviews        : {ios_count}')
print(f'  Android reviews    : {android}')
print()

print('RATING BREAKDOWN:')
for stars in [5,4,3,2,1]:
    count = conn.execute(
        'SELECT COUNT(*) FROM reviews WHERE rating=?',(stars,)
    ).fetchone()[0]
    bar = '' * min(count//20, 30)
    print(f'  {stars}star  {bar} ({count})')

print()
print('WEEKLY DISTRIBUTION:')
weeks = conn.execute('''
    SELECT week_number, COUNT(*) as cnt
    FROM reviews
    GROUP BY week_number
    ORDER BY week_number
''').fetchall()
for w in weeks:
    print(f'  Week {w[0]:02d}    {w[1]} reviews')

conn.close()
