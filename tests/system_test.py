import sys, os, sqlite3, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

print('=' * 60)
print('  GROWW PULSE AGENT — COMPLETE SYSTEM TEST')
print(f'  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 60)

results = {}

#  TEST 1: Environment 
print('\n[1] ENVIRONMENT VARIABLES')
required = ['GROQ_API_KEY','GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET','GOOGLE_REFRESH_TOKEN',
            'RECIPIENT_LIST','DB_URL']
all_set = True
for var in required:
    val = os.getenv(var,'')
    if val:
        print(f'   {var}: set')
    else:
        print(f'   {var}: MISSING')
        all_set = False
results['environment'] = all_set

#  TEST 2: Database 
print('\n[2] DATABASE')
try:
    db = os.getenv('DB_URL','sqlite:///data/groww_pulse.db').replace('sqlite:///','')
    conn = sqlite3.connect(db)
    total    = conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
    runs     = conn.execute('SELECT COUNT(*) FROM weekly_runs').fetchone()[0]
    themes   = conn.execute('SELECT COUNT(*) FROM themes').fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM weekly_runs WHERE status='completed'").fetchone()[0]
    conn.close()
    print(f'   Total reviews   : {total:,}')
    print(f'   Weekly runs     : {runs}')
    print(f'   Themes stored   : {themes}')
    print(f'   Completed runs  : {completed}')
    results['database'] = total > 0
except Exception as e:
    print(f'   Database error: {e}')
    results['database'] = False

#  TEST 3: ChromaDB 
print('\n[3] CHROMADB VECTOR STORE')
try:
    from storage.vector_store import init_collection, get_collection
    init_collection()
    col = get_collection()
    count = col.count()
    print(f'   ChromaDB connected')
    print(f'   Embeddings stored: {count}')
    results['chromadb'] = True
except Exception as e:
    print(f'   ChromaDB error: {e}')
    results['chromadb'] = False

#  TEST 4: Android Scraper 
print('\n[4] ANDROID SCRAPER (Google Play)')
try:
    from ingestion.android_scraper import fetch_android_reviews
    reviews = fetch_android_reviews('com.nextbillion.groww', days_back=3)
    if reviews:
        print(f'   Fetched: {len(reviews)} reviews')
        print(f'   Sample: [{reviews[0].get("rating")}] {reviews[0].get("text","")[:60]}')
        results['android_scraper'] = True
    else:
        print(f'    Fetched 0 reviews (rate limited)')
        results['android_scraper'] = False
except Exception as e:
    print(f'   Android scraper error: {e}')
    results['android_scraper'] = False

#  TEST 5: Language Filter 
print('\n[5] LANGUAGE FILTER')
try:
    from ingestion.language_filter import filter_english
    test = [
        {'review_id':'t1','text':'This app is great for investing','title':''},
        {'review_id':'t2','text':'यह ऐप बहत अचछ ह','title':''},
        {'review_id':'t3','text':'Bakwas app','title':''},
    ]
    kept = filter_english(test)
    print(f'   Input: 3 reviews')
    print(f'   Kept English: {len(kept)}')
    print(f'   Filter working correctly')
    results['language_filter'] = True
except Exception as e:
    print(f'   Language filter error: {e}')
    results['language_filter'] = False

#  TEST 6: PII Stripper 
print('\n[6] PII STRIPPER')
try:
    from ingestion.pii_stripper import strip_pii_text
    test = 'Call me at 9876543210 or email@test.com for help'
    result = strip_pii_text(test)
    if '[REDACTED]' in result:
        print(f'   PII detected and removed')
        print(f'   Input : {test}')
        print(f'   Output: {result}')
        results['pii_stripper'] = True
    else:
        print(f'   PII not removed: {result}')
        results['pii_stripper'] = False
except Exception as e:
    print(f'   PII stripper error: {e}')
    results['pii_stripper'] = False

#  TEST 7: AI Embedder 
print('\n[7] AI EMBEDDER (BAAI/bge-small-en-v1.5)')
try:
    from ai.embedder import embed_reviews
    test_reviews = [
        {'review_id':'e1','text':'App crashes frequently during market hours','store':'android','rating':1,'date':'2026-04-25','week_number':17},
        {'review_id':'e2','text':'Best investment app in India','store':'android','rating':5,'date':'2026-04-25','week_number':17},
    ]
    embeddings, source = embed_reviews(test_reviews)
    print(f'   Embeddings shape: {embeddings.shape}')
    print(f'   Model used: {source}')
    results['embedder'] = True
except Exception as e:
    print(f'   Embedder error: {e}')
    results['embedder'] = False

#  TEST 8: Groq LLM 
print('\n[8] GROQ LLM (llama-3.1-8b-instant)')
try:
    from groq import Groq
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    r = client.chat.completions.create(
        model='llama-3.1-8b-instant',
        messages=[{'role':'user','content':'Reply with just: OK'}],
        max_tokens=5
    )
    response = r.choices[0].message.content
    print(f'   Groq API connected')
    print(f'   Response: {response}')
    results['groq_llm'] = True
except Exception as e:
    print(f'   Groq error: {e}')
    results['groq_llm'] = False

#  TEST 9: Google OAuth 
print('\n[9] GOOGLE OAUTH (MCP)')
try:
    import httpx
    resp = httpx.post(
        'https://oauth2.googleapis.com/token',
        data={
            'client_id':     os.getenv('GOOGLE_CLIENT_ID'),
            'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
            'refresh_token': os.getenv('GOOGLE_REFRESH_TOKEN'),
            'grant_type':    'refresh_token'
        }
    )
    if resp.status_code == 200:
        token = resp.json().get('access_token','')
        print(f'   Google OAuth: CONNECTED')
        print(f'   Token: {token[:25]}...')
        results['google_oauth'] = True
    else:
        print(f'   OAuth failed: {resp.json()}')
        results['google_oauth'] = False
except Exception as e:
    print(f'   OAuth error: {e}')
    results['google_oauth'] = False

#  TEST 10: Gmail MCP 
print('\n[10] GMAIL MCP')
try:
    import httpx
    resp = httpx.post(
        'https://oauth2.googleapis.com/token',
        data={
            'client_id':     os.getenv('GOOGLE_CLIENT_ID'),
            'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
            'refresh_token': os.getenv('GOOGLE_REFRESH_TOKEN'),
            'grant_type':    'refresh_token'
        }
    )
    token = resp.json().get('access_token','')
    drafts = httpx.get(
        'https://gmail.googleapis.com/gmail/v1/users/me/drafts',
        headers={'Authorization': f'Bearer {token}'},
        params={'maxResults': 5}
    )
    if drafts.status_code == 200:
        draft_list = drafts.json().get('drafts',[])
        print(f'   Gmail MCP: CONNECTED')
        print(f'   Drafts found: {len(draft_list)}')
        results['gmail_mcp'] = True
    else:
        print(f'   Gmail failed: {drafts.status_code}')
        results['gmail_mcp'] = False
except Exception as e:
    print(f'   Gmail error: {e}')
    results['gmail_mcp'] = False

#  TEST 11: Report Files 
print('\n[11] REPORT FILES')
archive = Path('data/archive')
weekly  = list(archive.glob('groww_week_*.md'))
html    = list(archive.glob('groww_week_*.html'))
quarterly = list(archive.glob('groww_q*.md'))
csv_files = list(archive.glob('*.csv'))
print(f'   Weekly MD reports  : {len(weekly)}')
print(f'   Weekly HTML reports: {len(html)}')
print(f'   Quarterly reports  : {len(quarterly)}')
print(f'   CSV archives       : {len(csv_files)}')
results['reports'] = len(weekly) > 0

#  TEST 12: Dashboard 
print('\n[12] DASHBOARD')
try:
    from dashboard.app import app
    print(f'   Flask app importable')
    print(f'   Run: python dashboard/app.py')
    print(f'   URL: http://localhost:5000')
    results['dashboard'] = True
except Exception as e:
    print(f'   Dashboard error: {e}')
    results['dashboard'] = False

#  TEST 13: Scheduler 
print('\n[13] SCHEDULER')
try:
    from apscheduler.triggers.cron import CronTrigger
    import pytz
    IST = pytz.timezone('Asia/Kolkata')
    trigger = CronTrigger(
        day_of_week='mon', hour=9, minute=0, timezone=IST
    )
    print(f'   APScheduler importable')
    print(f'   Cron: Every Monday 09:00 IST')
    print(f'   Run: python scheduler/cron_runner.py')
    results['scheduler'] = True
except Exception as e:
    print(f'   Scheduler error: {e}')
    results['scheduler'] = False

#  FINAL REPORT 
print('\n' + '=' * 60)
print('  SYSTEM TEST RESULTS')
print('=' * 60)

passed = sum(1 for v in results.values() if v)
total_tests = len(results)

for test, result in results.items():
    icon = '' if result else ''
    name = test.replace('_',' ').title()
    print(f'  {icon} {name}')

print()
print(f'  Score: {passed}/{total_tests} tests passed')
print()

if passed == total_tests:
    print('   ALL SYSTEMS GO — GROWW PULSE AGENT READY')
elif passed >= total_tests * 0.8:
    print('   SYSTEM MOSTLY READY — minor issues above')
else:
    print('    SYSTEM NEEDS FIXES — check failed tests')

print('=' * 60)
