import sys, os, sqlite3, json
from pathlib import Path

sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

print('=' * 60)
print('  DASHBOARD DATA VERIFICATION')
print('  Checking if dashboard shows correct review numbers')
print('=' * 60)

DB_PATH = os.getenv('DB_URL','sqlite:///data/groww_pulse.db').replace('sqlite:///','')
conn = sqlite3.connect(DB_PATH)

#  What DB actually has 
print('\n[1] ACTUAL DATABASE COUNTS')
print('-' * 40)

total_reviews = conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
android = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='android'").fetchone()[0]
ios = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='ios'").fetchone()[0]
total_runs = conn.execute("SELECT COUNT(*) FROM weekly_runs WHERE status='completed'").fetchone()[0]
total_themes = conn.execute('SELECT COUNT(*) FROM themes').fetchone()[0]

print(f'  Total reviews      : {total_reviews:,}')
print(f'  Android reviews    : {android:,}')
print(f'  iOS reviews        : {ios:,}')
print(f'  Completed runs     : {total_runs}')
print(f'  Theme records      : {total_themes}')

#  What dashboard API returns 
print('\n[2] WHAT DASHBOARD API RETURNS')
print('-' * 40)

import httpx, threading, time
from dashboard.app import app

server_started = threading.Event()

def run_server():
    app.run(port=5001, debug=False, use_reloader=False)

t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(2)

try:
    summary = httpx.get('http://localhost:5001/api/summary', timeout=10).json()
    history = httpx.get('http://localhost:5001/api/weekly-history', timeout=10).json()

    print(f'  API total_reviews  : {summary.get("total_reviews", "N/A"):,}')
    print(f'  API total_weeks    : {summary.get("total_weeks", "N/A")}')
    print(f'  API themes_found   : {summary.get("themes_found", "N/A")}')
    print(f'  API top_urgency    : {summary.get("top_urgency", "N/A")}')
    print(f'  API history rows   : {len(history)}')

    print('\n[3] WEEKLY BREAKDOWN (DB vs API)')
    print('-' * 40)
    print(f'  {"Week":<8} {"DB Reviews":>12} {"API Reviews":>12} {"Match":>8}')
    print(f'  {"-"*8} {"-"*12} {"-"*12} {"-"*8}')

    for row in history:
        wk = row.get('week_number')
        api_count = row.get('reviews_kept', 0)
        db_count = conn.execute(
            'SELECT reviews_kept FROM weekly_runs WHERE week_number=? AND status="completed" ORDER BY reviews_kept DESC LIMIT 1',
            (wk,)
        ).fetchone()
        db_val = db_count[0] if db_count else 0
        match = '' if api_count == db_val else ''
        print(f'  Week {wk:<3}  {db_val:>12,}  {api_count:>12,}  {match:>8}')

    print('\n[4] THEME VERIFICATION')
    print('-' * 40)
    themes = summary.get('themes', [])
    if themes:
        for t in themes:
            print(f'  {t["theme_id"]} | {t["label"]:<30} | urgency={t["urgency_score"]} | volume={t["volume"]}')
    else:
        print('  No themes returned by API')

    print('\n[5] FINAL VERDICT')
    print('-' * 40)

    db_total = total_reviews
    api_total = summary.get('total_reviews', 0)

    if db_total == api_total:
        print(f'   Review count MATCHES: DB={db_total:,} API={api_total:,}')
    else:
        print(f'   MISMATCH: DB={db_total:,} vs API={api_total:,}')
        print(f'  Gap: {abs(db_total - api_total):,} reviews difference')

    if len(history) == total_runs:
        print(f'   Weekly history MATCHES: {len(history)} rows')
    else:
        print(f'    History rows: API={len(history)} DB={total_runs}')

    if themes:
        print(f'   Themes showing: {len(themes)} themes in dashboard')
    else:
        print(f'   No themes showing in dashboard')

except Exception as e:
    print(f'  Error calling API: {e}')
    print('  Make sure dashboard/app.py has no syntax errors')

conn.close()
print('\n' + '=' * 60)
