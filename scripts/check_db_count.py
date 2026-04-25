import sqlite3, os
from dotenv import load_dotenv
load_dotenv('.env')

db = os.getenv('DB_URL','sqlite:///data/groww_pulse.db').replace('sqlite:///','')
conn = sqlite3.connect(db)

total   = conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
android = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='android'").fetchone()[0]
ios     = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='ios'").fetchone()[0]
real    = conn.execute("SELECT COUNT(*) FROM reviews WHERE date >= '2026-04-21' AND store='android'").fetchone()[0]

print(f'Total reviews : {total:,}')
print(f'Android       : {android:,}')
print(f'iOS           : {ios:,}')
print(f'Real Android  : {real:,}')
print()
print('Dashboard should show these exact numbers after fix.')
conn.close()
