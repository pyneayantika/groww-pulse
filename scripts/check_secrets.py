"""Check that no secrets are accidentally exposed in source files."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

SECRET_PATTERNS = [
    (r'sk-ant-[a-zA-Z0-9\-]+', "Anthropic API key"),
    (r'sk-[a-zA-Z0-9]{32,}', "OpenAI API key"),
    (r'gsk_[a-zA-Z0-9]{32,}', "Groq API key"),
    (r'ya29\.[a-zA-Z0-9\-_]+', "Google OAuth token"),
    (r'AIza[0-9A-Za-z\-_]{35}', "Google API key"),
]

SKIP_DIRS = {".venv", "node_modules", ".git", "__pycache__", ".chroma", "data"}
SKIP_FILES = {".env", ".env.example"}

found_secrets = []

for path in ROOT.rglob("*"):
    if any(skip in path.parts for skip in SKIP_DIRS):
        continue
    if path.name in SKIP_FILES:
        continue
    if path.suffix not in {".py", ".js", ".yaml", ".yml", ".json", ".md", ".txt"}:
        continue
    if not path.is_file():
        continue
    
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, content):
                found_secrets.append(f"  FOUND {label} in: {path.relative_to(ROOT)}")
    except Exception:
        continue

if found_secrets:
    print("SECRET SCAN FAILED — potential secrets found:")
    for s in found_secrets:
        print(s)
    sys.exit(1)
else:
    print("SECRET SCAN OK — no secrets found in source files")
