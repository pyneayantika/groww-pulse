import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from pathlib import Path
import time
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import itertools

USER_AGENTS = itertools.cycle([
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
])

RATE_LIMIT_SLEEP = 2  # seconds between requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_ios_reviews(app_id: str, days_back: int = 7) -> List[Dict[str, Any]]:
    """Fetch iOS reviews from App Store using app-store-web-scraper."""
    try:
        from app_store_web_scraper import AppStoreEntry
    except ImportError:
        logger.error("app-store-web-scraper not installed. Install with: pip install app-store-web-scraper")
        return []

    try:
        logger.info(f"Fetching iOS reviews for app_id: {app_id} via app-store-web-scraper")
        cutoff = datetime.now() - timedelta(days=days_back)

        app = AppStoreEntry(country='in', app_id=app_id)
        raw = list(app.reviews(limit=200))

        if not raw:
            logger.info("iOS scraper returned 0 reviews")
            return []

        def _get(obj, *attrs, default=''):
            """Get attribute from either a dict or an object."""
            for attr in attrs:
                val = obj.get(attr, None) if isinstance(obj, dict) else getattr(obj, attr, None)
                if val is not None:
                    return val
            return default

        reviews = []
        for review_data in raw:
            try:
                review_date = _get(review_data, 'date')
                if review_date is None or review_date == '':
                    continue
                if hasattr(review_date, 'year'):
                    review_date = datetime(
                        review_date.year, review_date.month, review_date.day
                    )
                elif isinstance(review_date, str):
                    review_date = datetime.fromisoformat(review_date[:10])
                if review_date < cutoff:
                    continue

                date_str = review_date.strftime('%Y-%m-%d')
                raw_id = str(_get(review_data, 'id'))
                review_id = hashlib.sha256(
                    f"ios{raw_id}{date_str}".encode('utf-8')
                ).hexdigest()

                reviews.append({
                    'review_id': review_id,
                    'store': 'ios',
                    'rating': int(_get(review_data, 'rating', default=0) or 0),
                    'title': str(_get(review_data, 'title')),
                    'text': str(_get(review_data, 'body', 'review', 'content')),
                    'date': date_str,
                    'app_version': str(_get(review_data, 'version', 'app_version')),
                    'raw_id': raw_id
                })

            except Exception as e:
                logger.warning(f"Error processing individual iOS review: {e}")
                continue

        logger.info(f"Successfully fetched {len(reviews)} iOS reviews")
        return reviews

    except Exception as e:
        logger.warning(f"iOS scraper error (returning empty list): {e}")
        return []


def test_ios_scraper():
    """Test function to verify iOS scraper works."""
    # Use a known app ID for testing
    test_app_id = "co.groww.stocks"
    reviews = fetch_ios_reviews(test_app_id, days_back=1)
    
    print(f"Fetched {len(reviews)} iOS reviews")
    if reviews:
        print("Sample review:")
        sample = reviews[0]
        for key, value in sample.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    test_ios_scraper()
