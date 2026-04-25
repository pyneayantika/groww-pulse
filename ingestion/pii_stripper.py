import re
import hashlib
import spacy
from typing import Dict, Any

# Compile regex patterns at module level
EMAIL = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.IGNORECASE)
PHONE = re.compile(r'\b[789]\d{9}\b')
PAN = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
AADHAAR = re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')

# Load spaCy NLP model once at module level
try:
    NLP = spacy.load("en_core_web_sm")
except OSError:
    print("Warning: spaCy model 'en_core_web_sm' not found. PII detection will be limited to regex patterns.")
    NLP = None


def strip_pii_text(text: str) -> str:
    """Strip PII from text using two-pass approach (regex + spaCy NER)."""
    if not text:
        return text
    
    cleaned_text = text
    
    # Pass 1: Replace all regex matches with [REDACTED]
    cleaned_text = EMAIL.sub('[REDACTED]', cleaned_text)
    cleaned_text = PHONE.sub('[REDACTED]', cleaned_text)
    cleaned_text = PAN.sub('[REDACTED]', cleaned_text)
    cleaned_text = AADHAAR.sub('[REDACTED]', cleaned_text)
    
    # Pass 2: Run spaCy NER, redact PERSON entities only
    if NLP is not None:
        try:
            doc = NLP(cleaned_text)
            # Replace PERSON entities from right to left to avoid index shifting
            for ent in reversed(doc.ents):
                if ent.label_ == 'PERSON':
                    cleaned_text = cleaned_text[:ent.start_char] + '[REDACTED]' + cleaned_text[ent.end_char:]
        except Exception as e:
            print(f"Warning: spaCy NER failed: {e}")
    
    return cleaned_text


def strip_pii(review: Dict[str, Any]) -> Dict[str, Any]:
    """Strip PII from review title and text."""
    # Create a copy to avoid modifying the original
    cleaned_review = review.copy()
    
    # Strip PII from title and text
    if 'title' in cleaned_review and cleaned_review['title']:
        cleaned_review['title'] = strip_pii_text(cleaned_review['title'])
    
    if 'text' in cleaned_review and cleaned_review['text']:
        cleaned_review['text'] = strip_pii_text(cleaned_review['text'])
    
    # Mark as PII stripped
    cleaned_review['pii_stripped'] = True
    
    return cleaned_review


def test_pii_stripper():
    """Test function to verify PII stripping works correctly."""
    test_cases = [
        ("Call me at 9876543210", "Call me at [REDACTED]"),
        ("Email user@example.com", "Email [REDACTED]"),
        ("My PAN is ABCDE1234F", "My PAN is [REDACTED]"),
        ("Aadhar 1234 5678 9012", "Aadhar [REDACTED]"),
        ("John Doe called", "[REDACTED] called"),
    ]
    
    for input_text, expected in test_cases:
        result = strip_pii_text(input_text)
        print(f"Input: {input_text}")
        print(f"Output: {result}")
        print(f"Expected: {expected}")
        print("---")


if __name__ == "__main__":
    test_pii_stripper()
