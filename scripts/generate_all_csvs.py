import sqlite3, csv, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv('.env')

db = os.getenv(
    'DB_URL', 'sqlite:///data/groww_pulse.db'
).replace('sqlite:///', '')
conn = sqlite3.connect(db)

archive = Path('data/archive')
archive.mkdir(exist_ok=True)

columns = [
    'review_id', 'store', 'rating', 'title', 'text',
    'date', 'app_version', 'language_detected',
    'pii_stripped', 'suspicious_review', 'week_number'
]

HEADERS = [
    'Review ID', 'Store', 'Rating (1-5)', 'Title',
    'Review Text', 'Date', 'App Version',
    'Language', 'PII Stripped', 'Suspicious', 'Week Number'
]

weeks = conn.execute(
    'SELECT DISTINCT week_number FROM reviews WHERE week_number IS NOT NULL ORDER BY week_number'
).fetchall()

print(f'Generating CSVs for {len(weeks)} weeks...')
print()

generated = []
for (wk,) in weeks:
    rows = conn.execute(f'''
        SELECT {",".join(columns)}
        FROM reviews WHERE week_number=?
        ORDER BY rating ASC, date DESC
    ''', (wk,)).fetchall()

    csv_path = archive / f'week_{wk:02d}_2026.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(rows)

    size_kb = round(csv_path.stat().st_size / 1024, 1)
    print(f'  Week {wk:02d} -> {csv_path.name} | {len(rows)} reviews | {size_kb} KB')
    generated.append(csv_path)

print()

# Quarterly master CSV
all_rows = conn.execute(f'''
    SELECT {",".join(columns)}
    FROM reviews
    ORDER BY week_number ASC, date DESC
''').fetchall()

q_path = archive / 'groww_q1_2026_quarterly_reviews.csv'
with open(q_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(HEADERS)
    writer.writerows(all_rows)

size_kb = round(q_path.stat().st_size / 1024, 1)
print(f'Quarterly -> {q_path.name} | {len(all_rows)} reviews | {size_kb} KB')

# Theme summary CSV
themes = conn.execute('''
    SELECT t.theme_id, t.label, t.urgency_score,
           t.sentiment_score, t.volume,
           t.trend_direction, t.top_quote,
           t.action_idea, w.week_number, w.year
    FROM themes t
    JOIN weekly_runs w ON t.run_id = w.id
    WHERE w.status = "completed"
    ORDER BY w.week_number ASC, t.urgency_score DESC
''').fetchall()

theme_path = archive / 'groww_q1_2026_themes_summary.csv'
with open(theme_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Week Number', 'Year', 'Theme ID', 'Theme Label',
        'Urgency Score', 'Sentiment Score', 'Volume',
        'Trend Direction', 'Top Quote', 'Action Idea'
    ])
    for row in themes:
        writer.writerow([
            row[8], row[9], row[0], row[1],
            row[2], row[3], row[4],
            row[5], row[6], row[7]
        ])

size_kb = round(theme_path.stat().st_size / 1024, 1)
print(f'Themes   -> {theme_path.name} | {len(themes)} records | {size_kb} KB')

conn.close()
print()
print('ALL CSV FILES:')
print('-' * 60)
for f in sorted(archive.glob('*.csv')):
    size_kb = round(f.stat().st_size / 1024, 1)
    print(f'  {f.name:<50} {size_kb:>8} KB')

print()
print('CSV GENERATION COMPLETE')
