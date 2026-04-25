from ingestion.pii_stripper import strip_pii_text
from typing import List, Dict, Any


def select_weekly_quotes(labeled_themes: List[Dict[str, Any]]) -> List[str]:
    """
    Select 3 representative quotes for the weekly report based on different criteria.
    
    Args:
        labeled_themes: List of labeled theme dictionaries
        
    Returns:
        List of 3 quotes (empty strings if not enough themes)
    """
    if not labeled_themes:
        return ["", "", ""]
    
    # Sort themes by different criteria
    sorted_by_urgency = sorted(
        labeled_themes, key=lambda x: x.get("urgency_score", 0), reverse=True
    )
    
    sorted_by_sentiment = sorted(
        labeled_themes, key=lambda x: x.get("sentiment_score", 0)
    )
    
    # Get themes with worsening trend
    worsening_themes = [
        t for t in labeled_themes 
        if t.get("trend_direction") == "worsening"
    ]
    
    # Get themes by volume
    sorted_by_volume = sorted(
        labeled_themes, key=lambda x: x.get("volume", 0), reverse=True
    )
    
    selected = []
    seen_themes = set()
    
    # Candidate selection strategy
    candidates = []
    
    # 1. Most urgent theme
    if sorted_by_urgency:
        candidates.append(("urgent", sorted_by_urgency[0]))
    
    # 2. Most negative sentiment theme
    if sorted_by_sentiment:
        candidates.append(("sentiment", sorted_by_sentiment[0]))
    
    # 3. Most concerning trend (worsening or highest volume)
    if worsening_themes:
        candidates.append(("trend", worsening_themes[0]))
    elif sorted_by_volume:
        candidates.append(("volume", sorted_by_volume[0]))
    
    # Select quotes ensuring no theme is repeated
    for candidate_type, theme in candidates:
        if theme.get("theme_id") not in seen_themes:
            quote = _extract_quote_from_theme(theme, candidate_type)
            if quote:
                selected.append(quote)
                seen_themes.add(theme.get("theme_id"))
    
    # Fill remaining slots with quotes from other themes
    if len(selected) < 3:
        remaining_themes = [
            t for t in labeled_themes 
            if t.get("theme_id") not in seen_themes
        ]
        
        for theme in remaining_themes:
            if len(selected) >= 3:
                break
            
            quote = _extract_quote_from_theme(theme, "filler")
            if quote:
                selected.append(quote)
                seen_themes.add(theme.get("theme_id"))
    
    # Ensure we always return exactly 3 quotes
    while len(selected) < 3:
        selected.append("")
    
    return selected[:3]


def _extract_quote_from_theme(theme: Dict[str, Any], selection_type: str) -> str:
    """
    Extract and process a quote from a theme based on selection criteria.
    
    Args:
        theme: Theme dictionary
        selection_type: Type of selection (urgent, sentiment, trend, volume, filler)
        
    Returns:
        Processed quote string or empty string
    """
    # Try to get the top quote from the theme
    quote = theme.get("top_quote", "")
    
    if quote and quote.strip():
        # Clean and validate the quote
        cleaned_quote = _clean_quote(quote)
        if cleaned_quote:
            return cleaned_quote
    
    # If no top quote, generate one based on theme characteristics
    return _generate_fallback_quote(theme, selection_type)


def _clean_quote(quote: str) -> str:
    """
    Clean and validate a quote.
    
    Args:
        quote: Raw quote string
        
    Returns:
        Cleaned quote or empty string if invalid
    """
    if not quote or not quote.strip():
        return ""
    
    # Strip PII
    cleaned = strip_pii_text(quote.strip())
    
    # Remove common prefixes/suffixes
    prefixes_to_remove = ["Quote:", "User says:", "Review:", "Comment:"]
    for prefix in prefixes_to_remove:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    
    # Length validation
    if len(cleaned) < 10:
        return ""
    
    if len(cleaned) > 300:
        cleaned = cleaned[:297] + "..."
    
    # Ensure it's a complete sentence (ends with punctuation or is a complete thought)
    if not any(cleaned.endswith(p) for p in [".", "!", "?", "..."]):
        # Add ellipsis if it seems truncated
        if not cleaned.endswith(".") and not cleaned.endswith("!") and not cleaned.endswith("?"):
            cleaned += "..."
    
    return cleaned


def _generate_fallback_quote(theme: Dict[str, Any], selection_type: str) -> str:
    """
    Generate a fallback quote when no suitable quote is available.
    
    Args:
        theme: Theme dictionary
        selection_type: Type of selection
        
    Returns:
        Generated quote or empty string
    """
    theme_label = theme.get("theme_label", "this issue")
    urgency = theme.get("urgency_score", 5)
    sentiment = theme.get("sentiment_score", 0)
    volume = theme.get("volume", 0)
    
    # Generate contextual quotes based on selection type and theme characteristics
    if selection_type == "urgent" and urgency >= 7:
        return f"Users are experiencing urgent issues with {theme_label.lower()} requiring immediate attention."
    
    elif selection_type == "sentiment" and sentiment < -0.3:
        return f"Strong negative sentiment detected around {theme_label.lower()} experiences."
    
    elif selection_type == "trend" and theme.get("trend_direction") == "worsening":
        return f"Growing concerns about {theme_label.lower()} as issues are worsening over time."
    
    elif selection_type == "volume" and volume >= 10:
        return f"High volume of feedback regarding {theme_label.lower()} affecting many users."
    
    # Generic fallback
    if urgency >= 6:
        return f"Significant user concerns about {theme_label.lower()} need to be addressed."
    elif sentiment < 0:
        return f"Users express dissatisfaction with {theme_label.lower()} functionality."
    else:
        return f"Users provide feedback about {theme_label.lower()} features and experience."


def select_top_quotes_by_criteria(labeled_themes: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    """
    Select top quotes with metadata for detailed analysis.
    
    Args:
        labeled_themes: List of labeled theme dictionaries
        limit: Maximum number of quotes to return
        
    Returns:
        List of quote dictionaries with metadata
    """
    quotes = []
    
    for theme in labeled_themes:
        quote = _extract_quote_from_theme(theme, "detailed")
        if quote:
            quotes.append({
                "quote": quote,
                "theme_id": theme.get("theme_id"),
                "theme_label": theme.get("theme_label"),
                "urgency_score": theme.get("urgency_score"),
                "sentiment_score": theme.get("sentiment_score"),
                "volume": theme.get("volume"),
                "trend_direction": theme.get("trend_direction")
            })
    
    # Sort by urgency and volume
    quotes.sort(key=lambda x: (x["urgency_score"], x["volume"]), reverse=True)
    
    return quotes[:limit]


def test_quote_selector():
    """Test function to verify quote selector works correctly."""
    # Create test themes
    test_themes = [
        {
            "theme_id": "T1",
            "theme_label": "App Performance",
            "urgency_score": 8.5,
            "sentiment_score": -0.7,
            "volume": 25,
            "trend_direction": "worsening",
            "top_quote": "The app crashes every time I try to trade, this is unacceptable!"
        },
        {
            "theme_id": "T2", 
            "theme_label": "Customer Support",
            "urgency_score": 6.0,
            "sentiment_score": -0.3,
            "volume": 15,
            "trend_direction": "stable",
            "top_quote": "Customer support never responds to my tickets, very frustrating."
        },
        {
            "theme_id": "T3",
            "theme_label": "Features",
            "urgency_score": 4.0,
            "sentiment_score": 0.5,
            "volume": 8,
            "trend_direction": "improving",
            "top_quote": "Love the new features, keep up the good work!"
        },
        {
            "theme_id": "T4",
            "theme_label": "UI/UX",
            "urgency_score": 3.0,
            "sentiment_score": 0.2,
            "volume": 5,
            "trend_direction": "stable",
            "top_quote": ""  # Empty quote to test fallback
        }
    ]
    
    # Test weekly quote selection
    weekly_quotes = select_weekly_quotes(test_themes)
    print("Weekly quotes:")
    for i, quote in enumerate(weekly_quotes, 1):
        print(f"  {i}. {quote}")
    
    # Test detailed quote selection
    detailed_quotes = select_top_quotes_by_criteria(test_themes, limit=3)
    print("\nDetailed quotes:")
    for quote_data in detailed_quotes:
        print(f"  Theme: {quote_data['theme_label']}")
        print(f"  Quote: {quote_data['quote']}")
        print(f"  Urgency: {quote_data['urgency_score']}")
        print()


if __name__ == "__main__":
    test_quote_selector()
