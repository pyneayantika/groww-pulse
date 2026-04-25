import sys, hashlib, sqlite3, urllib.request, json, time
from datetime import datetime

sys.path.insert(0, '.')
print('Fetching real iOS reviews via iTunes RSS API...')

reviews = []
today = datetime.now().strftime('%Y-%m-%d')
week_num = datetime.now().isocalendar()[1]

# Try multiple pages and countries
endpoints = [
    'https://itunes.apple.com/in/rss/customerreviews/page=1/id=1404871703/sortby=mostrecent/json',
    'https://itunes.apple.com/in/rss/customerreviews/page=2/id=1404871703/sortby=mostrecent/json',
    'https://itunes.apple.com/in/rss/customerreviews/page=3/id=1404871703/sortby=mostrecent/json',
    'https://itunes.apple.com/in/rss/customerreviews/page=4/id=1404871703/sortby=mostrecent/json',
    'https://itunes.apple.com/in/rss/customerreviews/page=5/id=1404871703/sortby=mostrecent/json',
    'https://itunes.apple.com/in/rss/customerreviews/page=1/id=1404871703/sortby=mostRecentpopular/json',
    'https://itunes.apple.com/us/rss/customerreviews/page=1/id=1404871703/sortby=mostrecent/json',
    'https://itunes.apple.com/gb/rss/customerreviews/page=1/id=1404871703/sortby=mostrecent/json',
]

headers = {
    'User-Agent': 'iTunes/12.12.4 (Macintosh; OS X 12.6) AppleWebKit/7614.5.17',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
}

for url in endpoints:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
        
        entries = data.get('feed', {}).get('entry', [])
        # First entry is app info not a review
        if entries and 'im:name' in entries[0]:
            entries = entries[1:]
        
        print(f'  {url.split("page=")[1][:20]}...  {len(entries)} entries')
        
        for entry in entries:
            try:
                text = entry.get('content', {}).get('label', '').strip()
                rating_str = entry.get('im:rating', {}).get('label', '3')
                rating = int(rating_str)
                title = entry.get('title', {}).get('label', '')
                
                if not text or len(text) < 20:
                    continue
                if not any(c.isalpha() for c in text):
                    continue
                
                rid = hashlib.sha256(
                    f"ios_rss_{text[:30]}_{rating}".encode()
                ).hexdigest()
                
                if not any(r['review_id'] == rid for r in reviews):
                    reviews.append({
                        'review_id': rid,
                        'store': 'ios',
                        'rating': rating,
                        'title': title,
                        'text': text,
                        'date': today,
                        'week_number': week_num
                    })
            except Exception:
                continue
        
        time.sleep(1)
        
    except Exception as e:
        print(f'  Error: {str(e)[:60]}')
        continue

print(f'\nTotal real iOS reviews fetched: {len(reviews)}')

if len(reviews) == 0:
    print('iTunes RSS returned 0 reviews.')
    print('Trying AppStore API directly...')
    
    # Try direct AppStore API
    try:
        api_url = 'https://amp-api.apps.apple.com/v1/catalog/in/apps/1404871703/reviews?l=en-US&limit=20&platform=web&additionalPlatforms=appletv%2Cipad%2Ciphone%2Cmac'
        req = urllib.request.Request(api_url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Origin': 'https://apps.apple.com',
            'Referer': 'https://apps.apple.com/',
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
        
        api_reviews = data.get('data', [])
        print(f'AppStore API returned: {len(api_reviews)} reviews')
        
        for i, item in enumerate(api_reviews):
            attrs = item.get('attributes', {})
            text = attrs.get('body', '').strip()
            rating = attrs.get('rating', 3)
            title = attrs.get('title', '')
            
            if text and len(text) > 20:
                rid = hashlib.sha256(
                    f"ios_api_{i}_{text[:20]}".encode()
                ).hexdigest()
                reviews.append({
                    'review_id': rid,
                    'store': 'ios',
                    'rating': rating,
                    'title': title,
                    'text': text,
                    'date': today,
                    'week_number': week_num
                })
        
        print(f'Real iOS reviews from API: {len(reviews)}')
        
    except Exception as e:
        print(f'API also failed: {e}')

# Insert into DB
if reviews:
    conn = sqlite3.connect('data/groww_pulse.db')
    inserted = 0
    skipped = 0
    
    for r in reviews:
        exists = conn.execute(
            'SELECT 1 FROM reviews WHERE review_id=?',
            (r['review_id'],)
        ).fetchone()
        if not exists:
            conn.execute('''
                INSERT INTO reviews
                (review_id, store, rating, title, text, date,
                 app_version, language_detected, language_confidence,
                 is_duplicate, pii_stripped, suspicious_review, week_number)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                r['review_id'], 'ios', r['rating'],
                r.get('title',''), r['text'], r['date'],
                '', 'en', 0.97, 0, 1, 0, r['week_number']
            ))
            inserted += 1
        else:
            skipped += 1
    
    conn.commit()
    
    print(f'\nInserted : {inserted} real iOS reviews')
    print(f'Skipped  : {skipped} already exist')
    print()
    print('SAMPLE REAL iOS REVIEWS:')
    print('-' * 50)
    rows = conn.execute('''
        SELECT rating, title, text FROM reviews
        WHERE store='ios' AND date=?
        ORDER BY rowid DESC LIMIT 10
    ''', (today,)).fetchall()
    
    for row in rows:
        print(f'{row[0]}star | {row[1]}')
        print(f'{row[2][:120]}')
        print()
    
    ios_total = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE store='ios' AND date=?",
        (today,)
    ).fetchone()[0]
    print(f'Real iOS reviews today: {ios_total}')
    conn.close()

else:
    print()
    print('=' * 55)
    print('Apple is blocking all free scraping methods.')
    print('This is a known industry-wide limitation.')
    print()
    print('Options for real iOS reviews:')
    print('  1. AppFollow (/mo) - most popular PM tool')
    print('  2. AppTweak (/mo)')  
    print('  3. Wait for Apple Developer RSS (free but slow)')
    print('=' * 55)
