import sys, json, subprocess, csv, os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

print('=' * 60)
print('  GROWW — RAW REVIEW EXPORT (No Filtering)')
print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 60)

# ── Fetch raw Android reviews ─────────────────────────────────
print('\n[1] Fetching raw Android reviews from Google Play...')

js_code = """
const gplay = require('google-play-scraper');

async function fetchAll() {
    let all = [];
    
    // Fetch 200 newest reviews
    try {
        const {data: batch1} = await gplay.reviews({
            appId: 'com.nextbillion.groww',
            lang: 'en', country: 'in',
            sort: gplay.sort.NEWEST,
            num: 200
        });
        all = all.concat(batch1);
        process.stderr.write('Batch 1: ' + batch1.length + ' reviews\\n');
    } catch(e) {
        process.stderr.write('Batch 1 error: ' + e.message + '\\n');
    }
    
    // Fetch 200 most helpful reviews  
    try {
        const {data: batch2} = await gplay.reviews({
            appId: 'com.nextbillion.groww',
            lang: 'en', country: 'in',
            sort: gplay.sort.HELPFULNESS,
            num: 200
        });
        all = all.concat(batch2);
        process.stderr.write('Batch 2: ' + batch2.length + ' reviews\\n');
    } catch(e) {
        process.stderr.write('Batch 2 error: ' + e.message + '\\n');
    }
    
    // Fetch 200 most rated reviews
    try {
        const {data: batch3} = await gplay.reviews({
            appId: 'com.nextbillion.groww',
            lang: 'en', country: 'in',
            sort: gplay.sort.RATING,
            num: 200
        });
        all = all.concat(batch3);
        process.stderr.write('Batch 3: ' + batch3.length + ' reviews\\n');
    } catch(e) {
        process.stderr.write('Batch 3 error: ' + e.message + '\\n');
    }
    
    // Deduplicate by review ID
    const seen = new Set();
    const unique = all.filter(r => {
        if(seen.has(r.id)) return false;
        seen.add(r.id);
        return true;
    });
    
    // Map to clean structure — NO filtering
    const mapped = unique.map(r => ({
        review_id:    String(r.id),
        store:        'android',
        rating:       r.score,
        title:        r.title || '',
        text:         r.text || '',
        date:         new Date(r.date).toISOString().split('T')[0],
        app_version:  r.version || '',
        thumbs_up:    r.thumbsUp || 0,
        author_name:  r.userName || '',
        reply_text:   r.replyText || '',
        reply_date:   r.replyDate ? new Date(r.replyDate).toISOString().split('T')[0] : '',
        scraped_at:   new Date().toISOString()
    }));
    
    process.stdout.write(JSON.stringify(mapped));
}

fetchAll().catch(e => {
    process.stderr.write('Fatal: ' + e.message);
    process.exit(1);
});
"""

js_file = Path('fetch_raw.js')
js_file.write_text(js_code, encoding='utf-8')

env = os.environ.copy()
result = subprocess.run(
    ['node', 'fetch_raw.js'],
    capture_output=True,
    timeout=120,
    env=env
)
js_file.unlink()

stderr = result.stderr.decode('utf-8', errors='ignore')
stdout = result.stdout.decode('utf-8', errors='ignore').strip()

print(f'  {stderr.strip()}')

android_reviews = []
if stdout:
    try:
        android_reviews = json.loads(stdout)
        print(f'  Total unique Android reviews: {len(android_reviews)}')
    except Exception as e:
        print(f'  Parse error: {e}')

# ── iOS via iTunes RSS (raw) ──────────────────────────────────
print('\n[2] Fetching raw iOS reviews via iTunes RSS...')
import urllib.request

ios_reviews = []
headers = {
    'User-Agent': 'iTunes/12.12.4 (Macintosh; OS X 12.6) AppleWebKit/7614.5.17',
}

for page in range(1, 11):
    try:
        url = f'https://itunes.apple.com/in/rss/customerreviews/page={page}/id=1404871703/sortby=mostrecent/json'
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
        entries = data.get('feed', {}).get('entry', [])
        if not entries:
            break
        # Skip first entry — it's app info
        if entries and 'im:name' in str(entries[0]):
            entries = entries[1:]
        for entry in entries:
            ios_reviews.append({
                'review_id':   entry.get('id', {}).get('label', ''),
                'store':       'ios',
                'rating':      entry.get('im:rating', {}).get('label', ''),
                'title':       entry.get('title', {}).get('label', ''),
                'text':        entry.get('content', {}).get('label', ''),
                'date':        entry.get('updated', {}).get('label', '')[:10],
                'app_version': entry.get('im:version', {}).get('label', ''),
                'thumbs_up':   '',
                'author_name': entry.get('author', {}).get('name', {}).get('label', ''),
                'reply_text':  '',
                'reply_date':  '',
                'scraped_at':  datetime.now().isoformat()
            })
        print(f'  iOS page {page}: {len(entries)} reviews')
        import time; time.sleep(1)
    except Exception as e:
        print(f'  iOS page {page}: {str(e)[:50]}')
        break

print(f'  Total iOS reviews: {len(ios_reviews)}')

# ── Combine ALL reviews ───────────────────────────────────────
all_raw = android_reviews + ios_reviews
print(f'\n[3] Total raw reviews: {len(all_raw)}')
print(f'    Android : {len(android_reviews)}')
print(f'    iOS     : {len(ios_reviews)}')

# ── Save to CSV — NO FILTERING ────────────────────────────────
print('\n[4] Saving to CSV...')

output_dir = Path('data/raw')
output_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
csv_path = output_dir / f'groww_raw_reviews_{timestamp}.csv'

columns = [
    'review_id', 'store', 'rating', 'title', 'text',
    'date', 'app_version', 'thumbs_up', 'author_name',
    'reply_text', 'reply_date', 'scraped_at'
]

with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    for review in all_raw:
        row = {col: review.get(col, '') for col in columns}
        # Clean text for CSV
        for field in ['title', 'text', 'reply_text']:
            if row[field]:
                row[field] = str(row[field]).replace('\n', ' ').replace('\r', ' ')
        writer.writerow(row)

print(f'  Saved: {csv_path}')
print(f'  Size : {csv_path.stat().st_size / 1024:.1f} KB')

# ── Preview ───────────────────────────────────────────────────
print('\n[5] RAW DATA PREVIEW (first 10 reviews):')
print('-' * 60)
for r in all_raw[:10]:
    print(f"[{r['store']}] {r['rating']}star | {r['date']}")
    print(f"  Author : {r.get('author_name','') or 'Anonymous'}")
    print(f"  Text   : {str(r.get('text',''))[:100]}...")
    if r.get('reply_text'):
        print(f"  Reply  : {str(r['reply_text'])[:80]}...")
    print()

# ── Stats ─────────────────────────────────────────────────────
print('=' * 60)
print('  RAW EXPORT SUMMARY')
print('=' * 60)
print(f'  Total reviews exported : {len(all_raw)}')
print(f'  Android                : {len(android_reviews)}')
print(f'  iOS                    : {len(ios_reviews)}')
print(f'  CSV file               : {csv_path}')
print(f'  Columns                : {len(columns)}')
print()
print('  Columns included:')
for col in columns:
    print(f'    ✅ {col}')
print()
print('  NOTE: This is completely RAW data.')
print('  No language filtering, no PII removal,')
print('  no deduplication, no noise filtering.')
print('  Exactly as received from the stores.')
print('=' * 60)
print('  RAW EXPORT COMPLETE')
print('=' * 60)
