import sqlite3
conn = sqlite3.connect('data/groww_pulse.db')
print('LATEST 5 ANDROID REVIEWS:')
print('-' * 50)
rows = conn.execute("SELECT rating, date, text FROM reviews WHERE store='android' ORDER BY date DESC LIMIT 5").fetchall()
for r in rows:
    print(f'{r[0]}star | {r[1]}')
    print(f'{r[2][:120]}')
    print()
conn.close()
