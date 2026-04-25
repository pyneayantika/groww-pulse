import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
]

print('Starting Google OAuth flow...')
print('A browser window will open. Sign in and click Allow.')
print()

flow = InstalledAppFlow.from_client_secrets_file(
    'credentials.json',
    scopes=SCOPES
)

# Try multiple ports until one works
creds = None
for port in [8090, 8091, 8092, 8093, 9000, 9090, 3000]:
    try:
        print(f'Trying port {port}...')
        creds = flow.run_local_server(port=port)
        print(f'Success on port {port}')
        break
    except OSError:
        print(f'Port {port} busy, trying next...')
        continue

if not creds:
    print('All ports busy. Trying console flow...')
    creds = flow.run_console()

print()
print('=' * 60)
print('  COPY THESE 3 VALUES INTO YOUR .env FILE')
print('=' * 60)
print(f'GOOGLE_CLIENT_ID={creds.client_id}')
print(f'GOOGLE_CLIENT_SECRET={creds.client_secret}')
print(f'GOOGLE_REFRESH_TOKEN={creds.refresh_token}')
print('=' * 60)

Path('google_tokens.json').write_text(
    json.dumps({
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'refresh_token': creds.refresh_token
    }, indent=2)
)
print()
print('Saved to google_tokens.json as backup')
