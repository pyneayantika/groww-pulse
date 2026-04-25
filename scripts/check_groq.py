import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

key = os.getenv('GROQ_API_KEY', '')
print(f'Current key in .env: {key[:15]}...{key[-5:]}' if len(key) > 20 else f'Key: {key}')
print(f'Key length: {len(key)}')
print()

if not key:
    print('ERROR: GROQ_API_KEY is empty in .env')
elif not key.startswith('gsk_'):
    print('ERROR: Key does not start with gsk_ — likely wrong key')
else:
    print('Key format looks correct. Testing API call...')
    try:
        from groq import Groq
        client = Groq(api_key=key)
        r = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[{'role':'user','content':'say OK'}],
            max_tokens=5
        )
        print(f'Groq API: {r.choices[0].message.content}')
        print('GROQ KEY IS VALID — no new key needed')
    except Exception as e:
        print(f'GROQ ERROR: {e}')
        print()
        print('Key is invalid or expired.')
        print('Go to https://console.groq.com to get a new one.')
