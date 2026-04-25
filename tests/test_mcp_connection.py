import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')

print('Testing Google MCP Connection...')
print()

client_id     = os.getenv('GOOGLE_CLIENT_ID','')
client_secret = os.getenv('GOOGLE_CLIENT_SECRET','')
refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN','')

if not client_id:
    print('GOOGLE_CLIENT_ID missing from .env')
elif not client_secret:
    print('GOOGLE_CLIENT_SECRET missing from .env')
elif not refresh_token:
    print('GOOGLE_REFRESH_TOKEN missing from .env')
else:
    print(f'Client ID     : {client_id[:30]}...')
    print(f'Client Secret : {client_secret[:15]}...')
    print(f'Refresh Token : {refresh_token[:20]}...')
    print()

    import httpx
    try:
        resp = httpx.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id':     client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type':    'refresh_token'
            }
        )
        if resp.status_code == 200:
            token = resp.json().get('access_token','')
            print(f'Google OAuth  : CONNECTED')
            print(f'Access token  : {token[:30]}...')
            print()
            print('MCP INTEGRATION READY')
            print('Run: python scripts/manual_run.py full')
        else:
            print(f'Google OAuth  : FAILED')
            print(f'Error         : {resp.json()}')
    except Exception as e:
        print(f'Connection error: {e}')
