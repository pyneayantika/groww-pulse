import sys, os
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

print("=" * 60)
print("  PLAYWRIGHT SCRAPER INTEGRATION TEST")
print("=" * 60)

# Test 1: Import scraper
print("\n[1] Testing Playwright scraper import...")
try:
    from ingestion.playwright_scraper_v2 import scrape_all_reviews
    print("  ✅ Import successful")
except Exception as e:
    print(f"  ❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Scrape reviews
print("\n[2] Testing review scraping...")
try:
    result = scrape_all_reviews(days_back=7)  # Last 7 days
    print(f"  ✅ Scraping completed")
    print(f"  iOS: {result['ios_count']} reviews")
    print(f"  Android: {result['android_count']} reviews")
    print(f"  Total: {result['total_count']} reviews")
    
    if result['total_count'] == 0:
        print("  ❌ No reviews found")
        sys.exit(1)
    
except Exception as e:
    print(f"  ❌ Scraping failed: {e}")
    sys.exit(1)

# Test 3: Verify review format
print("\n[3] Testing review format...")
try:
    all_reviews = result['total_reviews']
    sample_review = all_reviews[0]
    
    required_fields = ['review_id', 'store', 'rating', 'text', 'date', 'language_detected']
    missing_fields = [field for field in required_fields if field not in sample_review]
    
    if missing_fields:
        print(f"  ❌ Missing fields: {missing_fields}")
        sys.exit(1)
    
    print(f"  ✅ Review format valid")
    print(f"  Sample: [{sample_review['store']}] {sample_review['rating']}★ | {sample_review['text'][:50]}...")
    
except Exception as e:
    print(f"  ❌ Format validation failed: {e}")
    sys.exit(1)

# Test 4: Test with existing pipeline components
print("\n[4] Testing pipeline integration...")
try:
    # Test deduplication
    from ingestion.deduplicator import deduplicate
    deduped = deduplicate(all_reviews)
    print(f"  ✅ Deduplication: {len(all_reviews)} → {len(deduped)}")
    
    # Test language filter
    from ingestion.language_filter import filter_english
    english = filter_english(deduped)
    print(f"  ✅ Language filter: {len(deduped)} → {len(english)}")
    
    # Test embedding
    from ai.embedder import embed_reviews
    embeddings, source = embed_reviews(english[:10])  # Test with small subset
    print(f"  ✅ Embedding: {embeddings.shape} using {source}")
    
except Exception as e:
    print(f"  ❌ Pipeline integration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Save test results
print("\n[5] Saving test results...")
try:
    import json
    output_file = Path("data/playwright_integration_test.json")
    output_file.parent.mkdir(exist_ok=True)
    
    # Prepare serializable data
    test_result = {
        'test_timestamp': str(Path(__file__).stat().st_mtime),
        'scraper_result': {
            'ios_count': result['ios_count'],
            'android_count': result['android_count'],
            'total_count': result['total_count'],
            'scraping_method': result['scraping_method']
        },
        'pipeline_tests': {
            'deduplication_input': len(all_reviews),
            'deduplication_output': len(deduped),
            'language_filter_output': len(english),
            'embedding_shape': list(embeddings.shape),
            'embedding_source': source
        },
        'sample_reviews': [
            {k: v for k, v in review.items() if k != 'language_confidence'}
            for review in all_reviews[:3]
        ]
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(test_result, f, indent=2, ensure_ascii=False)
    
    print(f"  ✅ Test results saved: {output_file}")
    
except Exception as e:
    print(f"  ❌ Save failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("  INTEGRATION TEST COMPLETE")
print("  ✅ Playwright scraper works with existing pipeline")
print("  ✅ Review format compatible with AI pipeline")
print("  ✅ All pipeline components accept scraped reviews")
print("=" * 60)
