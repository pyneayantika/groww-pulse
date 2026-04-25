import sqlite3

conn = sqlite3.connect('data/groww_pulse.db')

# Remove obvious noise patterns
noise_patterns = [
    'Copyright',
    'Apple Inc',
    'accessibility',
    'privacy practices',
    'developer',
    'Learn More',
    'Terms of Use',
    'Privacy Policy',
    'App Store',
    'indicated that',
    'track you across',
    'following data'
]

removed = 0
rows = conn.execute(
    "SELECT review_id, text FROM reviews WHERE store='ios'"
).fetchall()

for review_id, text in rows:
    if any(noise in text for noise in noise_patterns):
        conn.execute(
            'DELETE FROM reviews WHERE review_id=?', (review_id,)
        )
        removed += 1

conn.commit()

remaining = conn.execute(
    "SELECT COUNT(*) FROM reviews WHERE store='ios'"
).fetchone()[0]
android = conn.execute(
    "SELECT COUNT(*) FROM reviews WHERE store='android'"
).fetchone()[0]

print(f'Removed noise  : {removed} records')
print(f'iOS remaining  : {remaining}')
print(f'Android total  : {android}')
print()
print('CLEAN iOS REVIEWS:')
print('-' * 50)
rows = conn.execute('''
    SELECT rating, date, text FROM reviews
    WHERE store='ios'
    ORDER BY rowid DESC LIMIT 5
''').fetchall()
for r in rows:
    print(f'{r[0]}star | {r[1]}')
    print(f'{r[2][:120]}')
    print()

conn.close()
