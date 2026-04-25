"""
ingestion/language_filter.py
Simple ASCII-based English detection for Indian app reviews.
"""
import logging
log = logging.getLogger(__name__)

def filter_english(reviews: list[dict]) -> list[dict]:
    """
    Keep English reviews using ASCII ratio detection.
    Indian users write English reviews with 100% ASCII characters.
    Hindi/regional reviews contain non-ASCII unicode characters.
    """
    kept = []
    discarded = 0

    for review in reviews:
        text  = (review.get("text")  or "").strip()
        title = (review.get("title") or "").strip()
        combined = f"{title} {text}".strip()

        if not combined or len(combined) < 2:
            continue

        # RULE 1: 100% ASCII = definitely English or Hinglish
        # Covers: "good", "bad", "bakwas", "Customer support is pathetic"
        if all(ord(c) < 128 for c in combined):
            review["language_detected"]   = "en"
            review["language_confidence"] = 0.95
            kept.append(review)
            continue

        # RULE 2: 60%+ ASCII = mixed English/emoji = keep
        # Covers: "good 👍", "okay 👍😊", "nice work 🙂"
        ascii_ratio = sum(1 for c in combined if ord(c) < 128) / len(combined)
        if ascii_ratio >= 0.60:
            review["language_detected"]   = "en"
            review["language_confidence"] = round(ascii_ratio, 2)
            kept.append(review)
            continue

        # RULE 3: Mostly non-ASCII = Hindi/regional = discard
        # Covers: "जब से स्टॉक को watchlist में add किए"
        discarded += 1

    log.info(f"Language filter: kept {len(kept)} English / discarded {discarded} non-English")

    return kept
