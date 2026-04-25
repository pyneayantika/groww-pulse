import sys; sys.path.insert(0, '.')
from ingestion.language_filter import filter_english

test_reviews = [
    {"review_id":"1","text":"good","title":"","rating":5},
    {"review_id":"2","text":"bakwas","title":"","rating":1},
    {"review_id":"3","text":"Customer support is very pathetic","title":"","rating":1},
    {"review_id":"4","text":"New update is so pathetic Mobile terminal view got downgraded","title":"","rating":1},
    {"review_id":"5","text":"जब से स्टॉक को watchlist में add किए","title":"","rating":1},
    {"review_id":"6","text":"good 👍","title":"","rating":5},
    {"review_id":"7","text":"beech market me app stop working","title":"","rating":1},
    {"review_id":"8","text":"Groww app started putting my mutual fund investments in demat","title":"","rating":1},
]

kept = filter_english(test_reviews)
print(f"Kept: {len(kept)}/8 reviews")
for r in kept:
    print(f"  [{r['rating']}star] {r['text'][:60]}")

assert len(kept) >= 6, f"Expected 6+ kept, got {len(kept)}"
print("LANGUAGE FILTER TEST PASSED")
