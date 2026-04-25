import itertools
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

ANDROID_USER_AGENTS = itertools.cycle([
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; OnePlus 9 Pro) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
])

RATE_LIMIT_SLEEP = 2

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_android_reviews(app_id: str, days_back: int = 7) -> List[Dict[str, Any]]:
    """Fetch Android reviews using Node.js script with retry logic and CSV fallback."""
    max_retries = 3
    backoff_delays = [2, 4, 8]  # seconds
    
    for attempt in range(max_retries):
        try:
            # Path to the Node.js script
            script_path = Path(__file__).parent.parent / "scripts" / "fetch_android.js"
            
            logger.info(f"Fetching Android reviews for app_id: {app_id} (attempt {attempt + 1})")
            
            # Rotate user agent and rate limit
            ua = next(ANDROID_USER_AGENTS)
            time.sleep(RATE_LIMIT_SLEEP)
            
            # Pass user-agent as env var to Node.js script
            import os
            env = os.environ.copy()
            env["SCRAPER_USER_AGENT"] = ua

            result = subprocess.run(
                ["node", str(script_path), app_id, str(days_back)],
                capture_output=True,
                timeout=60,
                cwd=str(Path(__file__).parent.parent),
                env=env
            )
            result_stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
            result_stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
            
            # Check if the script ran successfully
            if result.returncode != 0:
                raise Exception(f"Script failed with return code {result.returncode}: {result_stderr}")
            
            # Parse the JSON output
            try:
                reviews = json.loads(result_stdout)
                if not isinstance(reviews, list):
                    raise Exception("Expected JSON array from Android fetch script")
                
                logger.info(f"Successfully fetched {len(reviews)} Android reviews")
                return reviews
                
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON output: {e}")
                
        except subprocess.TimeoutExpired:
            error_msg = f"Android fetch script timed out after 60 seconds"
        except FileNotFoundError:
            error_msg = "Node.js not found. Please ensure Node.js is installed and in PATH"
        except Exception as e:
            error_msg = f"Error fetching Android reviews: {e}"
        
        # Handle retry logic
        if attempt < max_retries - 1:
            delay = backoff_delays[attempt]
            logger.warning(f"Attempt {attempt + 1} failed: {error_msg}. Waiting {delay}s...")
            time.sleep(delay)
        else:
            logger.error(f"Android scraper failed after {max_retries} attempts: {error_msg}")
    
    # All retries failed — use CSV fallback
    logger.warning("Android scraper failed after 3 retries — using CSV fallback")
    from ingestion.csv_fallback import load_csv_reviews
    
    raw_files = list(Path("data/raw").glob("android_*.csv"))
    if raw_files:
        latest = max(raw_files, key=lambda f: f.stat().st_mtime)
        reviews = load_csv_reviews(str(latest))
        for r in reviews:
            r["fallback_used"] = True
        logger.info(f"CSV fallback: loaded {len(reviews)} reviews from {latest.name}")
        return reviews
    
    logger.warning("No CSV fallback available — returning empty list")
    return []


def test_android_scraper():
    """Test function to verify Android scraper works."""
    # Use the Groww Android app ID
    test_app_id = "com.nextbillion.groww"
    reviews = fetch_android_reviews(test_app_id, days_back=1)
    
    print(f"Fetched {len(reviews)} Android reviews")
    if reviews:
        print("Sample review:")
        sample = reviews[0]
        for key, value in sample.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    test_android_scraper()
