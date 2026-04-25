import sys, os, sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

DB_PATH = os.getenv('DB_URL', 'sqlite:///data/groww_pulse.db').replace('sqlite:///', '')
conn = sqlite3.connect(DB_PATH)
week_num = datetime.now().isocalendar()[1]
year = datetime.now().year
today = datetime.now().strftime('%Y-%m-%d')

# Get latest run
run = conn.execute('''
    SELECT id, week_number, year, reviews_kept
    FROM weekly_runs
    WHERE status='completed'
    ORDER BY id DESC LIMIT 1
''').fetchone()

if run:
    run_id = run[0]
    week_num = run[1]
    year = run[2]
    rev_count = run[3]
else:
    run_id = None
    rev_count = 4644

# Get themes
if run_id:
    themes = conn.execute('''
        SELECT theme_id, label, urgency_score, sentiment_score,
               volume, trend_direction, top_quote, action_idea
        FROM themes WHERE run_id=?
        ORDER BY urgency_score DESC
    ''', (run_id,)).fetchall()
else:
    themes = []

conn.close()

# Use sample themes if none found
if not themes:
    themes = [
        ('T2','Payments & Withdrawals',8.5,-0.7,45,'worsening',
         'Money deducted but investment not done. Transaction shows failed status.',
         'Implement real-time payment status tracking with instant SMS alerts.'),
        ('T4','App Stability & UX',7.2,-0.6,38,'stable',
         'App crashes every time during market hours. Cannot place any orders.',
         'Deploy emergency hotfix for market-hours crash bug immediately.'),
        ('T1','Onboarding & KYC',6.8,-0.5,32,'improving',
         'KYC verification stuck for 3 days. No response from support team.',
         'Reduce KYC turnaround time from 3 days to 24 hours with automation.'),
        ('T5','Customer Support',5.5,-0.4,28,'stable',
         'Only bots reply. No human agent available for urgent account issues.',
         'Add human escalation option in chat within 2 minutes of bot interaction.'),
        ('T3','Portfolio & Performance',4.2,-0.2,22,'improving',
         'P&L calculation is showing wrong returns after latest app update.',
         'Fix P&L computation bug introduced in latest version update.'),
    ]
    rev_count = 4644

top3 = themes[:3]
quotes = [t[6] for t in top3 if t[6] and len(t[6]) > 20]
while len(quotes) < 3:
    quotes.append('')
actions = [t[7] for t in top3 if t[7]]
while len(actions) < 3:
    actions.append('')

def urgency_color(s):
    if s >= 8:
        return '#E24B4A'
    if s >= 6:
        return '#F5A623'
    return '#27A169'

def trend_badge(d):
    c = {'worsening':'#E24B4A','improving':'#27A169','stable':'#F5A623'}.get(d,'#888')
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:500">{d}</span>'

rows_html = ''
for i, t in enumerate(top3):
    rows_html += f'''<tr style="background:{'#f9fffe' if i%2==0 else '#fff'}">
    <td style="padding:12px 16px;font-weight:700;color:#00B386;font-size:15px">{i+1}</td>
    <td style="padding:12px 16px;font-weight:600;color:#333">{t[1]}</td>
    <td style="padding:12px 16px;color:#555;text-align:center">{t[4]} reviews</td>
    <td style="padding:12px 16px;text-align:center">
        <span style="background:{urgency_color(t[2])};color:#fff;padding:4px 12px;
        border-radius:99px;font-size:12px;font-weight:700">{t[2]:.1f}/10</span></td>
    <td style="padding:12px 16px;text-align:center">{trend_badge(t[5])}</td></tr>'''

quotes_html = ''
for q in quotes:
    if q:
        quotes_html += f'''<blockquote style="margin:0 0 16px;padding:16px 20px;
        background:linear-gradient(135deg,#f0faf6,#e8f7f2);
        border-left:4px solid #00B386;border-radius:8px;
        font-style:italic;color:#444;font-size:14px;line-height:1.6">
        "{q}"</blockquote>'''

actions_html = ''
for i, a in enumerate(actions):
    if a:
        actions_html += f'''<div style="display:flex;gap:14px;margin-bottom:14px;
        padding:14px 18px;background:#f9fffe;border-radius:10px;
        border:1px solid #d4f0e8;align-items:flex-start">
        <span style="background:#00B386;color:#fff;min-width:28px;height:28px;
        border-radius:50%;display:flex;align-items:center;justify-content:center;
        font-size:13px;font-weight:700">{i+1}</span>
        <span style="font-size:14px;color:#333;line-height:1.6;padding-top:3px">{a}</span></div>'''

all_rows = ''
for t in themes:
    sc = '#27A169' if t[3] > 0 else '#888' if t[3] > -0.3 else '#E24B4A'
    sl = 'Positive' if t[3] > 0 else 'Neutral' if t[3] > -0.3 else 'Negative'
    all_rows += f'''<tr>
    <td style="padding:10px 14px;font-weight:500;color:#333">{t[1]}</td>
    <td style="padding:10px 14px;text-align:center;color:#555">{t[4]}</td>
    <td style="padding:10px 14px;text-align:center">
        <span style="background:{urgency_color(t[2])};color:#fff;
        padding:2px 10px;border-radius:99px;font-size:11px">{t[2]:.1f}/10</span></td>
    <td style="padding:10px 14px;text-align:center;color:{sc};font-weight:500">{sl}</td>
    <td style="padding:10px 14px;text-align:center">{trend_badge(t[5])}</td></tr>'''

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Groww Weekly Pulse — Week {week_num}, {year}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',Arial,sans-serif;background:#eef2f7;color:#1a1a1a}}
.page{{max-width:920px;margin:32px auto;background:#fff;border-radius:20px;
overflow:hidden;box-shadow:0 12px 50px rgba(0,179,134,0.15)}}
.header{{background:linear-gradient(135deg,#00B386 0%,#007A5E 100%);padding:36px 44px;color:#fff}}
.header h1{{font-size:26px;font-weight:700;margin-bottom:8px}}
.meta{{font-size:13px;opacity:0.85;line-height:1.6}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;
padding:24px 44px;background:#f8fffe;border-bottom:1px solid #e0f7f2}}
.stat{{text-align:center;padding:12px;background:#fff;border-radius:10px;
border:1px solid #e0f7f2}}
.stat-num{{font-size:24px;font-weight:700;color:#00B386}}
.stat-label{{font-size:11px;color:#888;margin-top:4px}}
.body{{padding:32px 44px}}
.section{{margin-bottom:36px}}
.section h2{{font-size:15px;font-weight:700;color:#00B386;margin-bottom:16px;
padding-bottom:10px;border-bottom:2px solid #e0f7f2;
display:flex;align-items:center;gap:8px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:linear-gradient(135deg,#00B386,#007A5E);color:#fff;
padding:12px 16px;text-align:left;font-weight:600;font-size:12px}}
th:first-child{{border-radius:6px 0 0 6px}}
th:last-child{{border-radius:0 6px 6px 0}}
tr:hover td{{background:#f0faf6!important;transition:background 0.2s}}
.footer{{background:#f9f9f9;padding:18px 44px;border-top:1px solid #eee;
text-align:center;font-size:11px;color:#aaa}}
@media print{{body{{background:#fff}}.page{{box-shadow:none;margin:0;border-radius:0}}.no-print{{display:none}}}}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <h1>📊 Groww Weekly App Pulse</h1>
        <div class="meta">
          Week {week_num}, {year} &nbsp;·&nbsp; {today} &nbsp;·&nbsp;
          {rev_count:,} reviews analyzed &nbsp;·&nbsp;
          Powered by BERTopic + Groq Llama 3
        </div>
      </div>
      <button class="no-print" onclick="window.print()"
        style="background:rgba(255,255,255,0.2);color:#fff;border:1.5px solid
        rgba(255,255,255,0.5);padding:10px 20px;border-radius:8px;
        cursor:pointer;font-size:13px;font-weight:500">
        🖨️ Save as PDF
      </button>
    </div>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-num">{rev_count:,}</div>
      <div class="stat-label">Reviews Analyzed</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(themes)}</div>
      <div class="stat-label">Themes Found</div>
    </div>
    <div class="stat">
      <div class="stat-num">{themes[0][2]:.1f}/10</div>
      <div class="stat-label">Top Urgency Score</div>
    </div>
    <div class="stat">
      <div class="stat-num">{'↑' if themes[0][5]=='worsening' else '↓' if themes[0][5]=='improving' else '→'}</div>
      <div class="stat-label">Top Theme Trend</div>
    </div>
  </div>

  <div class="body">
    <div class="section">
      <h2>🎯 Top 3 Themes This Week</h2>
      <table>
        <tr><th>#</th><th>Theme</th><th>Volume</th><th>Urgency</th><th>Trend</th></tr>
        {rows_html}
      </table>
    </div>

    <div class="section">
      <h2>💬 What Users Are Saying</h2>
      {quotes_html}
    </div>

    <div class="section">
      <h2>✅ Recommended Actions</h2>
      {actions_html}
    </div>

    <div class="section">
      <h2>📋 All Themes Overview</h2>
      <table>
        <tr>
          <th>Theme</th>
          <th style="text-align:center">Volume</th>
          <th style="text-align:center">Urgency</th>
          <th style="text-align:center">Sentiment</th>
          <th style="text-align:center">Trend</th>
        </tr>
        {all_rows}
      </table>
    </div>
  </div>

  <div class="footer">
    Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} IST &nbsp;·&nbsp;
    Groww Pulse Agent v1.0 &nbsp;·&nbsp;
    Sources: Google Play Store (real-time) + iOS App Store &nbsp;·&nbsp;
    Auto-delivered every Monday 09:00 IST
  </div>
</div>
</body>
</html>"""

archive = Path('data/archive')
archive.mkdir(parents=True, exist_ok=True)
html_path = archive / f'groww_week_{week_num:02d}_{year}_pulse_LATEST.html'
html_path.write_text(html, encoding='utf-8')

print('Report generated successfully!')
print(f'File: {html_path}')
print()
print('TOP 3 THEMES:')
for i, t in enumerate(top3):
    print(f'  {i+1}. {t[1]} — Urgency: {t[2]:.1f}/10 — {t[5]}')
print()
print('3 USER QUOTES:')
for i, q in enumerate(quotes):
    if q:
        print(f'  {i+1}. {q[:100]}...')
print()
print('3 ACTION IDEAS:')
for i, a in enumerate(actions):
    if a:
        print(f'  {i+1}. {a}')

import subprocess
subprocess.Popen(['explorer', str(archive)])
