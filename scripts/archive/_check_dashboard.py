import urllib.request, json

data = json.loads(urllib.request.urlopen('http://localhost:5000/api/latest-run').read())
print('Status:', data.get('status'))
print('Week:', data.get('week_number'), data.get('year'))
themes = data.get('themes', [])
print(f'Themes: {len(themes)}')
for t in themes:
    print(f"  [{t['urgency_score']}/10] {t['label']} — {t['volume']} reviews")

print()
history = json.loads(urllib.request.urlopen('http://localhost:5000/api/history').read())
print(f'History runs: {len(history)}')
for r in history[:5]:
    print(f"  Week {r['week_number']} — {r['status']} — {r['themes_found']} themes")

print()
print('DASHBOARD FIXED')
