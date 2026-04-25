import sqlite3
conn = sqlite3.connect('data/groww_pulse.db')

print('=' * 50)
print('  ANDROID REVIEWS CHECK')
print('=' * 50)

total   = conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
android = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='android'").fetchone()[0]
ios     = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='ios'").fetchone()[0]

print(f'  Total reviews  : {total}')
print(f'  Android        : {android}')
print(f'  iOS            : {ios}')

print()
print('LATEST 5 ANDROID REVIEWS:')
print('-' * 50)
rows = conn.execute("SELECT rating, date, substr(text,1,100) FROM reviews WHERE store='android' ORDER BY date DESC LIMIT 5").fetchall()

if rows:
    for r in rows:
        print(f'  {r[0]}star | {r[1]}')
        print(f'  {r[2]}...')
        print()
else:
    print('  NO ANDROID REVIEWS FOUND')

conn.close()
