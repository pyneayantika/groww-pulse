import sqlite3
conn = sqlite3.connect('data/groww_pulse.db')

total = conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
android = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='android'").fetchone()[0]

print(f'Total reviews : {total}')
print(f'Android       : {android}')
print()
print('LATEST 5 ANDROID REVIEWS (most recent date):')
print('-' * 50)
rows = conn.execute('''
    SELECT rating, date, text FROM reviews
    WHERE store='android'
    ORDER BY date DESC, rowid DESC
    LIMIT 5
''').fetchall()

for row in rows:
    print(f'{row[0]}star | {row[1]}')
    print(f'{row[2][:120]}')
    print()

conn.close()
