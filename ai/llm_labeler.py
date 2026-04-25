import os
import re
import json
import hashlib
import html
import sys
from typing import List, Dict, Any
from pathlib import Path
from groq import Groq
from ingestion.pii_stripper import strip_pii_text

# Initialize Groq client
try:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
except Exception as e:
    print(f"Warning: Could not initialize Groq client: {e}")
    client = None

SYSTEM_PROMPT = (
    "You are a senior product analyst for Groww, an Indian fintech investment app. "
    "Analyze user reviews and return ONLY a valid JSON object. "
    "No explanation, no markdown, no preamble."
)

INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"you are now",
    r"disregard your",
    r"new system prompt",
    r"forget everything",
    r"act as [a-z]+",
    r"system prompt:",
    r"pretend you are"
]

# System prompt hash guard
SYSTEM_PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()

def verify_system_prompt_integrity():
    current_hash = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
    if current_hash != SYSTEM_PROMPT_HASH:
        raise SecurityError("System prompt has been tampered with!")

class SecurityError(Exception):
    pass


def sanitize_text(text: str) -> str:
    """Sanitize text to prevent prompt injection attacks."""
    if not text:
        return ""
    
    # HTML escape
    text = html.escape(text)
    
    # Remove potential injection patterns
    for pattern in INJECTION_PATTERNS:
        text = re.sub(pattern, "[FILTERED]", text, flags=re.IGNORECASE)
    
    # Limit length to prevent token overflow
    if len(text) > 1000:
        text = text[:1000] + "..."
    
    return text


def label_themes(clusters: List[Dict[str, Any]], reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Label theme clusters using Groq Llama 3 LLM.
    
    Args:
        clusters: List of cluster dictionaries with theme information
        reviews: List of review dictionaries
        
    Returns:
        List of labeled theme dictionaries with LLM-generated labels
    """
    # Verify system prompt integrity
    verify_system_prompt_integrity()
    
    if not client:
        print("Groq client not available, using fallback labeling")
        return _fallback_labeling(clusters, reviews)
    
    labeled = []
    
    for cluster in clusters:
        indices = cluster.get("review_indices", [])[:15]  # Limit to 15 reviews
        selected = [reviews[i] for i in indices if i < len(reviews)]
        
        if not selected:
            continue
        
        # Build reviews XML
        reviews_xml = ""
        for r in selected:
            safe_text = sanitize_text(r.get("text", ""))
            reviews_xml += (
                f'<r id="{r.get("review_id","")}" '
                f'rating="{r.get("rating","")}" '
                f'date="{r.get("date","")}">'
                f'{safe_text}</r>\n'
            )
        
        # Define expected schema
        schema = {
            "theme_id": cluster["theme_id"],
            "theme_label": cluster["label"],
            "urgency_score": 5,
            "sentiment_score": 0.0,
            "volume": cluster["size"],
            "trend_direction": "stable",
            "top_quote": "",
            "top_keywords": cluster.get("keywords", [])[:3],
            "action_idea": ""
        }
        
        # Build prompt
        prompt = (
            f"Analyze these reviews for theme: {cluster['label']}.\n"
            f"<reviews>\n{reviews_xml}</reviews>\n\n"
            f"Return ONLY this JSON (fill all fields):\n{json.dumps(schema, indent=2)}"
        )
        
        result = schema.copy()
        result["labeling_method"] = "llm"
        
        try:
            # Call LLM
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.1,
                timeout=30
            )
            
            raw = response.choices[0].message.content.strip()
            
            # Strip markdown fences if present
            raw = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE)
            raw = raw.strip()
            
            # Parse JSON response
            parsed = json.loads(raw)
            
            # Validate and update result
            if isinstance(parsed, dict):
                # Ensure required fields exist
                for key in schema.keys():
                    if key in parsed:
                        result[key] = parsed[key]
                
                # Validate ranges
                result["urgency_score"] = max(1, min(10, float(result.get("urgency_score", 5))))
                result["sentiment_score"] = max(-1, min(1, float(result.get("sentiment_score", 0))))
                result["volume"] = int(result.get("volume", cluster["size"]))
                
                # Validate trend direction
                valid_trends = ["worsening", "improving", "stable", "insufficient_data"]
                if result.get("trend_direction") not in valid_trends:
                    result["trend_direction"] = "stable"
                
            else:
                raise ValueError("Response is not a dictionary")
                
        except json.JSONDecodeError as e:
            print(f"JSON decode error for theme {cluster['label']}: {e}")
            # Retry once with stricter instructions
            try:
                retry_prompt = prompt + "\n\nIMPORTANT: Return ONLY valid JSON, nothing else."
                response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": retry_prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.1,
                    timeout=30
                )
                raw = response.choices[0].message.content.strip()
                raw = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE)
                raw = raw.strip()
                parsed = json.loads(raw)
                result.update(parsed)
                print(f"Retry successful for theme {cluster['label']}")
            except Exception as retry_e:
                print(f"Retry failed for theme {cluster['label']}: {retry_e}")
                result = _fallback_label_single_cluster(cluster, selected)
                result["labeling_method"] = "keyword_fallback"
                
        except Exception as e:
            print(f"LLM error for theme {cluster['label']}: {e}")
            result = _fallback_label_single_cluster(cluster, selected)
            result["labeling_method"] = "keyword_fallback"
        
        # POST-LLM DOUBLE PASS — rescan all string fields in result
        from ingestion.pii_stripper import strip_pii_text
        
        pii_detected = False
        for field in ["top_quote", "action_idea", "theme_label"]:
            original = result.get(field, "")
            if original:
                cleaned = strip_pii_text(original)
                if cleaned != original:
                    pii_detected = True
                    result[field] = cleaned
                    print(f"POST-LLM PII DETECTED in field '{field}' — redacted")
        
        result["pii_post_llm_detected"] = pii_detected
        
        labeled.append(result)
    
    return labeled


def _fallback_labeling(clusters: List[Dict[str, Any]], reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fallback labeling method when LLM is not available."""
    labeled = []
    for cluster in clusters:
        indices = cluster.get("review_indices", [])[:15]
        selected = [reviews[i] for i in indices if i < len(reviews)]
        
        result = _fallback_label_single_cluster(cluster, selected)
        labeled.append(result)
    
    return labeled


def _fallback_label_single_cluster(cluster: Dict[str, Any], selected_reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fallback labeling for a single cluster."""
    # Calculate urgency based on ratings
    ratings = [r.get("rating", 3) for r in selected_reviews]
    avg_rating = sum(ratings) / len(ratings) if ratings else 3
    urgency_score = round(10 - (avg_rating * 2), 1)  # Inverse: lower rating = higher urgency
    
    # Simple sentiment based on keywords
    positive_words = ["good", "great", "excellent", "love", "perfect", "amazing", "best"]
    negative_words = ["bad", "terrible", "worst", "broken", "fraud", "scam", "useless", "pathetic"]
    
    all_text = " ".join([r.get("text", "").lower() for r in selected_reviews])
    pos_count = sum(1 for word in positive_words if word in all_text)
    neg_count = sum(1 for word in negative_words if word in all_text)
    
    if neg_count > pos_count:
        sentiment_score = -0.5
    elif pos_count > neg_count:
        sentiment_score = 0.5
    else:
        sentiment_score = 0.0
    
    # Select a quote (first review, truncated)
    top_quote = ""
    if selected_reviews:
        quote_text = selected_reviews[0].get("text", "")
        if len(quote_text) > 200:
            quote_text = quote_text[:200] + "..."
        top_quote = strip_pii_text(quote_text)
    
    return {
        "theme_id": cluster["theme_id"],
        "theme_label": cluster["label"],
        "urgency_score": urgency_score,
        "sentiment_score": sentiment_score,
        "volume": cluster["size"],
        "trend_direction": "stable",
        "top_quote": top_quote,
        "top_keywords": cluster.get("keywords", [])[:3],
        "action_idea": "",
        "labeling_method": "keyword_fallback"
    }


def test_llm_labeler():
    """Test function to verify LLM labeler works."""
    # Create test data
    test_clusters = [
        {
            "theme_id": "T1",
            "label": "App Performance",
            "review_indices": [0, 1, 2],
            "keywords": ["slow", "crash", "bug"],
            "size": 3
        }
    ]
    
    test_reviews = [
        {
            "review_id": "test_1",
            "text": "The app is very slow and keeps crashing",
            "rating": 1,
            "date": "2024-01-01"
        },
        {
            "review_id": "test_2",
            "text": "I hate this app, it's terrible",
            "rating": 1,
            "date": "2024-01-02"
        },
        {
            "review_id": "test_3",
            "text": "Too many bugs and performance issues",
            "rating": 2,
            "date": "2024-01-03"
        }
    ]
    
    # Test labeling
    labeled = label_themes(test_clusters, test_reviews)
    
    print(f"Labeled {len(labeled)} themes:")
    for theme in labeled:
        print(f"  Theme: {theme['theme_label']}")
        print(f"  Urgency: {theme['urgency_score']}")
        print(f"  Sentiment: {theme['sentiment_score']}")
        print(f"  Method: {theme['labeling_method']}")


if __name__ == "__main__":
    test_llm_labeler()
