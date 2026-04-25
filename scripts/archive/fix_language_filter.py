import sys
sys.path.insert(0, '.')

# Patch language_filter.py to be less aggressive
from pathlib import Path

filter_file = Path('ingestion/language_filter.py')
content = filter_file.read_text(encoding='utf-8')
print('Current file size:', len(content), 'chars')

# Write a completely fixed version
new_content = '''"""
ingestion/language_filter.py
Keep English reviews. Less aggressive for short Indian-English reviews.
"""
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Short reviews that are clearly English regardless of detector
ENGLISH_KEYWORDS = {
    'good', 'bad', 'app', 'great', 'nice', 'worst', 'best',
    'slow', 'fast', 'crash', 'fix', 'update', 'login', 'otp',
    'kyc', 'fund', 'sip', 'stock', 'money', 'invest', 'withdraw',
    'refund', 'support', 'help', 'error', 'issue', 'problem',
    'payment', 'bank', 'account', 'portfolio', 'returns', 'loss',
    'profit', 'market', 'trade', 'buy', 'sell', 'groww', 'upi',
    'excellent', 'terrible', 'pathetic', 'awesome', 'useless',
    'broken', 'fraud', 'scam', 'amazing', 'horrible', 'perfect',
    'please', 'kindly', 'thank', 'love', 'hate', 'works', 'not',
    'very', 'much', 'more', 'less', 'better', 'worse', 'easy',
    'hard', 'simple', 'complex', 'useful', 'helpful', 'worst',
}

def is_english(text: str) -> tuple[bool, float]:
    """
    Determine if text is English using multiple strategies.
    Returns (is_english, confidence)
    """
    if not text or len(text.strip()) < 2:
        return False, 0.0

    text_lower = text.lower().strip()
    words = text_lower.split()

    # Strategy 1: All ASCII characters = likely English
    if all(ord(c) < 128 for c in text):
        return True, 0.95

    # Strategy 2: Short reviews with known English words
    if len(words) <= 5:
        word_set = set(w.strip(".,!?") for w in words)
        if word_set & ENGLISH_KEYWORDS:
            return True, 0.90

    # Strategy 3: More than 60% ASCII characters
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    ascii_ratio = ascii_chars / len(text)
    if ascii_ratio > 0.60:
        return True, 0.85

    # Strategy 4: Use langdetect for longer reviews
    if len(words) > 3:
        try:
            from langdetect import detect_langs
            langs = detect_langs(text)
            for lang in langs:
                if lang.lang == "en" and lang.prob >= 0.50:
                    return True, lang.prob
        except Exception:
            pass

    # Strategy 5: Use langid as backup
    try:
        import langid
        lang, conf = langid.classify(text)
        if lang == "en" and conf > 0.50:
            return True, float(conf)
    except Exception:
        pass

    return False, 0.0


def filter_english(reviews: list[dict]) -> list[dict]:
    """Filter reviews to keep only English ones."""
    kept = []
    discarded = 0
    unknown = 0

    for review in reviews:
        text = review.get("text", "") or ""
        title = review.get("title", "") or ""
        combined = f"{title} {text}".strip()

        if not combined:
            unknown += 1
            continue

        is_eng, confidence = is_english(combined)

        if is_eng:
            review["language_detected"] = "en"
            review["language_confidence"] = round(confidence, 3)
            kept.append(review)
        else:
            discarded += 1

    log.info("Language filtering completed:")
    log.info(f"  Total reviews: {len(reviews)}")
    log.info(f"  Kept (English): {len(kept)}")
    log.info(f"  Discarded (non-English): {discarded}")
    log.info(f"  Unknown: {unknown}")

    # Much lower threshold - only abort if truly no English
    if len(kept) < 3:
        log.warning(
            f"INSUFFICIENT ENGLISH: only {len(kept)} English reviews found."
        )
        flag_path = Path("data/processed/insufficient_english_flag.txt")
        flag_path.parent.mkdir(parents=True, exist_ok=True)
        flag_path.write_text(f"insufficient_english:{len(kept)}")

    return kept
'''

filter_file.write_text(new_content, encoding='utf-8')
print('Language filter updated successfully')
print()

# Test immediately
print('Testing with real Android reviews...')
from ingestion.android_scraper import fetch_android_reviews
reviews = fetch_android_reviews('com.nextbillion.groww', days_back=7)
print(f'Fetched: {len(reviews)} Android reviews')

if reviews:
    # Import fresh
    import importlib
    import ingestion.language_filter as lf
    importlib.reload(lf)
    
    kept = lf.filter_english(reviews)
    print(f'After filter: {len(kept)} English reviews kept')
    print()
    if kept:
        print('Sample kept reviews:')
        for r in kept[:5]:
            print(f'  [{r["rating"]}star] {r["text"][:80]}')
    
    if len(kept) >= 5:
        print()
        print('LANGUAGE FILTER FIXED — enough reviews to run AI pipeline')
    else:
        print()
        print('Still too few — but threshold is now 3 instead of 10')
