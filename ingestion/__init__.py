"""
Ingestion pipeline for groww-pulse project.

Handles fetching, filtering, deduplicating, and storing app reviews.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.db import bulk_insert_reviews
from storage.csv_archive import append_to_archive, rotate_archive
from .pii_stripper import strip_pii
from .language_filter import filter_english
from .deduplicator import deduplicate
from .ios_scraper import fetch_ios_reviews
from .android_scraper import fetch_android_reviews
from .csv_fallback import load_csv_reviews

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def apply_noise_filters(reviews: List[Dict[str, Any]], weekly_median: int = 300) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Apply noise filters to reviews and return kept reviews and noise log."""
    kept = []
    noise_log = []
    
    # Define sentiment keywords
    negative_words = ["bad", "terrible", "worst", "broken", "fraud", "scam", "useless", "pathetic"]
    positive_words = ["good", "great", "excellent", "love", "perfect", "amazing", "best"]
    
    for review in reviews:
        text = review.get("text", "")
        
        # Filter 1: minimum length
        if len(text.strip()) < 20:
            noise_log.append({**review, "reason": "too_short"})
            continue
        
        # Filter 2: max length truncation
        if len(text) > 10000:
            review["text"] = text[:1000] + " [truncated]"
        
        # Filter 3: spam (type-token ratio)
        words = text.lower().split()
        if len(words) > 5:
            ratio = len(set(words)) / len(words)
            if ratio < 0.40:
                noise_log.append({**review, "reason": "spam"})
                continue
        
        # Filter 4: rating-text mismatch
        neg_count = sum(1 for w in negative_words if w in text.lower())
        pos_count = sum(1 for w in positive_words if w in text.lower())
        rating = review.get("rating", 3)
        
        if rating >= 4 and neg_count > 2:
            review["suspicious_review"] = True
        if rating <= 2 and pos_count > 2:
            review["suspicious_review"] = True
        
        kept.append(review)
    
    # Filter 5: surge week
    if len(kept) > weekly_median * 3:
        bands = defaultdict(list)
        for r in kept:
            bands[r.get("rating", 3)].append(r)
        
        sampled = []
        for band_reviews in bands.values():
            sampled.extend(band_reviews[:100])
        
        kept = sampled[:500]
        logger.info(f"SURGE MODE: sampled 500 from {len(kept)} reviews")
    
    # Save noise log
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    log_path = Path("data/processed") / f"noise_log_{datetime.now():%Y%m%d}.json"
    
    try:
        with open(log_path, "w", encoding='utf-8') as f:
            json.dump(noise_log, f, indent=2, default=str)
        logger.info(f"Saved noise log to {log_path}")
    except Exception as e:
        logger.warning(f"Could not save noise log: {e}")
    
    # Also write CSV version
    import csv
    csv_path = Path("data/processed") / "noise_log.csv"
    csv_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as cf:
        writer = csv.DictWriter(cf, fieldnames=[
            "review_id", "store", "rating", "date", "reason", "logged_at"
        ])
        if not csv_exists:
            writer.writeheader()
        for entry in noise_log:
            writer.writerow({
                "review_id": entry.get("review_id", ""),
                "store": entry.get("store", ""),
                "rating": entry.get("rating", ""),
                "date": entry.get("date", ""),
                "reason": entry.get("reason", "unknown"),
                "logged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
    
    return kept, noise_log


def run_ingestion(days_back: int = 7, csv_fallback_path: str = None) -> Dict[str, Any]:
    """Run the complete ingestion pipeline."""
    logger.info("Starting ingestion pipeline")
    
    # Step 1: Fetch reviews
    logger.info("Step 1: Fetching reviews")
    
    ios_reviews = []
    android_reviews = []
    
    try:
        ios_reviews = fetch_ios_reviews("1404871703", days_back)
        logger.info(f"Fetched {len(ios_reviews)} iOS reviews")
    except Exception as e:
        logger.warning(f"Failed to fetch iOS reviews: {e}")
    
    try:
        android_reviews = fetch_android_reviews("com.nextbillion.groww", days_back)
        logger.info(f"Fetched {len(android_reviews)} Android reviews")
    except Exception as e:
        logger.warning(f"Failed to fetch Android reviews: {e}")
    
    # CSV fallback if provided
    if csv_fallback_path:
        try:
            csv_reviews = load_csv_reviews(csv_fallback_path)
            logger.info(f"Loaded {len(csv_reviews)} CSV reviews")
            android_reviews.extend(csv_reviews)
        except Exception as e:
            logger.warning(f"Failed to load CSV reviews: {e}")
    
    # Step 2: Merge and deduplicate
    logger.info("Step 2: Merging and deduplicating reviews")
    all_reviews = ios_reviews + android_reviews
    deduped_reviews = deduplicate(all_reviews)
    
    # Step 3: Filter English reviews
    logger.info("Step 3: Filtering English reviews")
    english_reviews = filter_english(deduped_reviews)
    
    # Step 4: Apply noise filters
    logger.info("Step 4: Applying noise filters")
    filtered_reviews, noise_log = apply_noise_filters(english_reviews)
    
    # Step 5: Strip PII
    logger.info("Step 5: Stripping PII from reviews")
    pii_stripped_reviews = []
    for review in filtered_reviews:
        try:
            cleaned_review = strip_pii(review)
            pii_stripped_reviews.append(cleaned_review)
        except Exception as e:
            logger.warning(f"Failed to strip PII from review {review.get('review_id', 'unknown')}: {e}")
            continue
    
    # Step 6: Bulk insert into database
    logger.info("Step 6: Inserting reviews into database")
    inserted_count = 0
    try:
        inserted_count = bulk_insert_reviews(pii_stripped_reviews)
        logger.info(f"Inserted {inserted_count} reviews into database")
    except Exception as e:
        logger.error(f"Failed to insert reviews into database: {e}")
    
    # Step 7: Archive and rotate
    logger.info("Step 7: Archiving reviews")
    try:
        # Calculate week number and year
        now = datetime.now()
        week_number = now.isocalendar()[1]
        year = now.year
        
        # Archive reviews
        archive_success = append_to_archive(pii_stripped_reviews, week_number, year)
        if archive_success:
            logger.info(f"Archived {len(pii_stripped_reviews)} reviews")
        
        # Rotate old archives
        deleted_count = rotate_archive()
        if deleted_count > 0:
            logger.info(f"Rotated {deleted_count} old archive files")
            
    except Exception as e:
        logger.error(f"Failed to archive reviews: {e}")
        week_number = datetime.now().isocalendar()[1]
        year = datetime.now().year
    
    # Prepare summary
    summary = {
        'fetched': len(all_reviews),
        'deduped': len(deduped_reviews),
        'english': len(english_reviews),
        'noise_dropped': len(noise_log),
        'inserted': inserted_count,
        'week_number': week_number,
        'year': year,
        'ios_fetched': len(ios_reviews),
        'android_fetched': len(android_reviews),
        'pii_stripped': len(pii_stripped_reviews)
    }
    
    logger.info(f"Ingestion completed: {summary}")
    return summary


def test_ingestion():
    """Test function to verify ingestion pipeline works."""
    # Test with CSV fallback
    test_csv_path = "test_reviews.csv"
    
    # Create test CSV
    import pandas as pd
    test_data = {
        'review_text': [
            'This app is really great and I love using it every day! The interface is clean and easy to use.',
            'The app keeps crashing and is very slow to load. Very disappointed with the performance.',
            'Good interface but needs more features for advanced trading.',
            'Excellent trading platform with good customer support and low fees.',
            'I have been using this app for 6 months and it works perfectly for my investment needs.'
        ],
        'rating': [5, 1, 3, 5, 4],
        'date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
    }
    
    test_df = pd.DataFrame(test_data)
    test_df.to_csv(test_csv_path, index=False)
    
    try:
        # Run ingestion with CSV fallback
        summary = run_ingestion(days_back=30, csv_fallback_path=test_csv_path)
        print(f"Test ingestion completed: {summary}")
    finally:
        # Clean up
        Path(test_csv_path).unlink(missing_ok=True)


# Export main functions
__all__ = [
    'run_ingestion',
    'apply_noise_filters',
    'filter_english',
    'deduplicate',
    'strip_pii',
    'fetch_ios_reviews',
    'fetch_android_reviews',
    'load_csv_reviews'
]
