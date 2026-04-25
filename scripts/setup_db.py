import sys
from pathlib import Path

# Add project root to Python path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# Import storage modules
from storage.db import init_db
from storage.vector_store import init_collection

def main():
    """Initialize the storage layer (database and vector store)."""
    try:
        # Initialize database
        print("Initializing database...")
        init_db()
        print("✓ Database initialized")
        
        # Initialize vector store
        print("Initializing vector store...")
        init_collection()
        print("✓ Vector store initialized")
        
        print("STORAGE OK")
        
    except Exception as e:
        print(f"Error during storage initialization: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
