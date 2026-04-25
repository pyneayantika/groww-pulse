import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

REQUIRED_VARS = [
    "GROQ_API_KEY", "DB_URL", "RECIPIENT_LIST",
    "AUTO_SEND", "ENABLE_EXTERNAL_SEND"
]

all_ok = True

print("=" * 50)
print("  GROWW PULSE — ENVIRONMENT CHECK")
print("=" * 50)

# Check env vars
print("\n[1] Environment Variables:")
for var in REQUIRED_VARS:
    val = os.getenv(var)
    if val:
        print(f"  ✓ {var}")
    else:
        print(f"  ✗ {var} — MISSING")
        all_ok = False

# Check Groq API
print("\n[2] Groq API:")
try:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    r = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=1
    )
    print("  ✓ Groq API: OK")
except Exception as e:
    print(f"  ✗ Groq API: FAILED — {e}")
    all_ok = False

# Check ChromaDB
print("\n[3] ChromaDB:")
try:
    from storage.vector_store import init_collection
    init_collection()
    print("  ✓ ChromaDB: OK")
except Exception as e:
    print(f"  ✗ ChromaDB: FAILED — {e}")
    all_ok = False

# Check SQLite
print("\n[4] SQLite Database:")
try:
    import sqlite3
    from storage.db import init_db
    init_db()
    db_path = os.getenv("DB_URL", "").replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    tables = [r[0] for r in
              conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    print(f"  ✓ SQLite: OK — tables: {tables}")
except Exception as e:
    print(f"  ✗ SQLite: FAILED — {e}")
    all_ok = False

# Check spaCy
print("\n[5] spaCy Model:")
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    print("  ✓ spaCy en_core_web_sm: OK")
except Exception as e:
    print(f"  ✗ spaCy: FAILED — {e}")
    all_ok = False

# Check embedder
print("\n[6] Embedding Model:")
try:
    from ai.embedder import get_model
    model = get_model()
    test_emb = model.encode(["test review"])
    print(f"  ✓ BAAI/bge-small-en-v1.5: OK — dim={test_emb.shape[1]}")
except Exception as e:
    print(f"  ✗ Embedder: FAILED — {e}")
    all_ok = False

print("\n" + "=" * 50)
if all_ok:
    print("  ENVIRONMENT OK — ready to run")
    sys.exit(0)
else:
    print("  ENVIRONMENT FAILED — fix errors above")
    sys.exit(1)
