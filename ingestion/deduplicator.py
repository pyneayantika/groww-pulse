import hashlib
import re
import logging
from typing import Dict, Any, List
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.db import session_scope
from storage.models import Review

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize text for deduplication: lowercase, remove punctuation, collapse whitespace."""
    if not text:
        return ""
    
    # Convert to lowercase
    normalized = text.lower()
    
    # Remove punctuation (keep alphanumeric and spaces)
    normalized = re.sub(r'[^a-z0-9\s]', ' ', normalized)
    
    # Collapse multiple spaces to single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Strip leading/trailing spaces
    normalized = normalized.strip()
    
    return normalized


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized text."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def deduplicate(reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate reviews within batch and against existing reviews in database."""
    if not reviews:
        return reviews
    
    # Step 1: Within-batch deduplication
    seen_hashes = {}
    batch_duplicates = 0
    
    for review in reviews:
        text = review.get('text', '')
        text_hash = compute_text_hash(text)
        
        if text_hash in seen_hashes:
            # Mark as duplicate
            review['is_duplicate'] = True
            batch_duplicates += 1
        else:
            seen_hashes[text_hash] = review
            review['is_duplicate'] = False
    
    # Step 2: Cross-store deduplication against database
    existing_review_ids = set()
    try:
        with session_scope() as session:
            # Get all existing review_ids from database
            existing_reviews = session.query(Review.review_id).all()
            existing_review_ids = {review.review_id for review in existing_reviews}
    except Exception as e:
        logger.warning(f"Could not query existing reviews from database: {e}")
    
    # Step 3: Filter out duplicates
    kept_reviews = []
    cross_store_duplicates = 0
    
    for review in reviews:
        # Skip if already marked as duplicate within batch
        if review.get('is_duplicate', False):
            continue
        
        # Skip if review_id already exists in database
        if review.get('review_id') in existing_review_ids:
            review['is_duplicate'] = True
            cross_store_duplicates += 1
            continue
        
        kept_reviews.append(review)
    
    total_duplicates = batch_duplicates + cross_store_duplicates
    logger.info(f"Deduplication completed:")
    logger.info(f"  Total reviews: {len(reviews)}")
    logger.info(f"  Within-batch duplicates: {batch_duplicates}")
    logger.info(f"  Cross-store duplicates: {cross_store_duplicates}")
    logger.info(f"  Kept reviews: {len(kept_reviews)}")
    
    return kept_reviews


def test_deduplicator():
    """Test function to verify deduplication works correctly."""
    test_reviews = [
        {
            'review_id': '1',
            'text': 'This app is great!',
            'store': 'test'
        },
        {
            'review_id': '2',
            'text': 'This app is great!',  # Duplicate
            'store': 'test'
        },
        {
            'review_id': '3',
            'text': 'THIS APP IS GREAT!',  # Duplicate (case insensitive)
            'store': 'test'
        },
        {
            'review_id': '4',
            'text': 'This app is terrible!',
            'store': 'test'
        },
        {
            'review_id': '5',
            'text': 'The app is great but has some issues.',
            'store': 'test'
        }
    ]
    
    filtered = deduplicate(test_reviews)
    print(f"Deduplicated {len(test_reviews)} reviews to {len(filtered)} unique reviews")
    for review in filtered:
        print(f"  {review['review_id']}: {review['text'][:50]}...")


if __name__ == "__main__":
    test_deduplicator()
