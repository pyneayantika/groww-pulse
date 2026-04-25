import sys, subprocess, json
from pathlib import Path

sys.path.insert(0, '.')

print('Fetching raw Android reviews to see actual content...')

js = """
const gplay = require('google-play-scraper');
gplay.reviews({
  appId: 'com.nextbillion.groww',
  lang: 'en', country: 'in',
  sort: gplay.sort.NEWEST,
  num: 20
}).then(({data}) => {
  const mapped = data.map(r => ({
    rating: r.score,
    text: r.text || '',
    date: new Date(r.date).toISOString().split('T')[0]
  }));
  process.stdout.write(JSON.stringify(mapped));
}).catch(e => process.stderr.write(e.message));
"""

Path('temp_check.js').write_text(js)
result = subprocess.run(
    ['node', 'temp_check.js'],
    capture_output=True, timeout=30
)
Path('temp_check.js').unlink()

stdout = result.stdout.decode('utf-8', errors='ignore').strip()
if stdout:
    reviews = json.loads(stdout)
    print(f'Fetched {len(reviews)} reviews')
    print()
    print('RAW REVIEW CONTENT:')
    print('-' * 50)
    for i, r in enumerate(reviews[:15]):
        text = r['text']
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text),1)
        print(f'{i+1}. [{r["rating"]}star] [{r["date"]}] ASCII:{ascii_ratio:.0%}')
        print(f'   TEXT: {repr(text[:80])}')
        print()
else:
    print('No output from scraper')
    print('STDERR:', result.stderr.decode('utf-8', errors='ignore')[:200])
