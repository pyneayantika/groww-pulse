from storage.db import get_session
from storage.models import Theme
import numpy as np
from typing import Dict, Any
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def compute_trend(theme_id: str, current_urgency: float) -> str:
    """
    Compute trend direction for a theme based on historical urgency scores.
    
    Args:
        theme_id: Theme identifier
        current_urgency: Current urgency score
        
    Returns:
        Trend direction: "worsening", "improving", "stable", or "insufficient_data"
    """
    session = get_session()
    try:
        # Get historical urgency scores for this theme
        records = (
            session.query(Theme.urgency_score)
            .filter(Theme.theme_id == theme_id)
            .order_by(Theme.id.desc())
            .limit(8)  # Get last 8 records for trend analysis
            .all()
        )
        
        if not records:
            return "insufficient_data"
        
        # Extract scores (excluding current)
        historical_scores = [record[0] for record in records if record[0] is not None]
        
        if len(historical_scores) < 2:
            return "insufficient_data"
        
        # Add current score to the end for trend calculation
        all_scores = historical_scores + [current_urgency]
        
        # Calculate trend using linear regression
        x = np.arange(len(all_scores))
        y = np.array(all_scores)
        
        # Simple linear regression to find slope
        slope = np.polyfit(x, y, 1)[0]
        
        # Determine trend based on slope
        if slope > 0.5:
            return "worsening"
        elif slope < -0.5:
            return "improving"
        else:
            return "stable"
            
    except Exception as e:
        print(f"Error computing trend for theme {theme_id}: {e}")
        return "insufficient_data"
    finally:
        session.close()


def calculate_urgency_score(reviews: list[dict], theme_keywords: list[str] = None) -> float:
    """
    Calculate urgency score based on review ratings and content.
    
    Args:
        reviews: List of review dictionaries
        theme_keywords: Optional keywords related to the theme
        
    Returns:
        Urgency score (1-10, higher = more urgent)
    """
    if not reviews:
        return 5.0  # Neutral urgency
    
    # Base urgency from ratings (inverse: lower ratings = higher urgency)
    ratings = [r.get("rating", 3) for r in reviews if r.get("rating") is not None]
    if ratings:
        avg_rating = sum(ratings) / len(ratings)
        rating_urgency = 10 - (avg_rating * 2)  # Convert 1-5 scale to 1-10 urgency
    else:
        rating_urgency = 5.0
    
    # Content-based urgency boost
    content_urgency_boost = 0.0
    
    # Urgent keywords
    urgent_keywords = [
        "urgent", "emergency", "critical", "immediate", "asap", "broken",
        "crash", "stuck", "blocked", "cannot", "unable", "failed", "error",
        "lost", "missing", "disappeared", "fraud", "scam", "hack", "security"
    ]
    
    # Severity indicators
    severity_keywords = [
        "terrible", "horrible", "awful", "worst", "disaster", "nightmare",
        "useless", "worthless", "garbage", "trash", "unacceptable"
    ]
    
    all_text = " ".join([r.get("text", "").lower() for r in reviews])
    
    # Count urgent and severity keywords
    urgent_count = sum(1 for word in urgent_keywords if word in all_text)
    severity_count = sum(1 for word in severity_keywords if word in all_text)
    
    # Calculate content boost
    if urgent_count > 0:
        content_urgency_boost += min(2.0, urgent_count * 0.3)
    
    if severity_count > 0:
        content_urgency_boost += min(1.5, severity_count * 0.5)
    
    # Volume factor (more reviews = higher urgency)
    volume_factor = min(1.0, len(reviews) / 10.0)
    
    # Combine all factors
    final_urgency = rating_urgency + content_urgency_boost + volume_factor
    
    # Clamp to valid range
    final_urgency = max(1.0, min(10.0, final_urgency))
    
    return round(final_urgency, 1)


def update_theme_urgency(theme_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update theme data with calculated urgency and trend.
    
    Args:
        theme_data: Theme dictionary with basic information
        
    Returns:
        Updated theme dictionary with urgency and trend
    """
    # Extract reviews for this theme (if available)
    reviews = theme_data.get("reviews", [])
    
    # Calculate urgency score
    urgency = calculate_urgency_score(reviews, theme_data.get("keywords"))
    
    # Compute trend
    theme_id = theme_data.get("theme_id", "")
    trend = compute_trend(theme_id, urgency)
    
    # Update theme data
    theme_data["urgency_score"] = urgency
    theme_data["trend_direction"] = trend
    
    return theme_data


def test_urgency_scorer():
    """Test function to verify urgency scorer works correctly."""
    # Test trend calculation
    print("Testing trend calculation...")
    trend = compute_trend("T1", 7.5)
    print(f"Trend for theme T1 with urgency 7.5: {trend}")
    
    # Test urgency calculation
    print("\nTesting urgency calculation...")
    
    # Test reviews with different ratings
    test_reviews = [
        {"text": "This app is terrible and crashes constantly", "rating": 1},
        {"text": "Very bad experience, urgent fix needed", "rating": 2},
        {"text": "The app is broken and I lost money", "rating": 1}
    ]
    
    urgency = calculate_urgency_score(test_reviews)
    print(f"Urgency for negative reviews: {urgency}")
    
    # Test positive reviews
    positive_reviews = [
        {"text": "Great app, love the features", "rating": 5},
        {"text": "Excellent interface and performance", "rating": 4}
    ]
    
    positive_urgency = calculate_urgency_score(positive_reviews)
    print(f"Urgency for positive reviews: {positive_urgency}")
    
    # Test theme update
    print("\nTesting theme update...")
    theme_data = {
        "theme_id": "T1",
        "label": "Test Theme",
        "keywords": ["test", "app"],
        "reviews": test_reviews
    }
    
    updated = update_theme_urgency(theme_data)
    print(f"Updated theme urgency: {updated['urgency_score']}")
    print(f"Updated theme trend: {updated['trend_direction']}")


if __name__ == "__main__":
    test_urgency_scorer()
