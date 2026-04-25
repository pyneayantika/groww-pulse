import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/groww_pulse.db')
today = datetime.now().strftime('%Y-%m-%d')

print('iOS reviews added TODAY:')
print('-' * 50)
rows = conn.execute('''
    SELECT rating, text FROM reviews
    WHERE store='ios' AND date=?
    ORDER BY rowid DESC LIMIT 10
''', (today,)).fetchall()

for r in rows:
    print(f'{r[0]}star | {r[1][:120]}')
    print()

print(f'Total today: {len(rows)}')
conn.close()
