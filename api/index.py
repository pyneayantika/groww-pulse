import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard.app import app

if __name__ == "__main__":
    app.run()
