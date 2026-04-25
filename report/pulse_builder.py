from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import List, Dict, Any

TEMPLATE_DIR = Path(__file__).parent / "templates"


@dataclass
class ThemeSummary:
    rank: int
    theme_id: str
    label: str
    volume: int
    urgency_score: float
    sentiment_score: float
    trend_direction: str
    top_keywords: List[str] = field(default_factory=list)
    action_idea: str = ""


@dataclass
class WeeklyPulseNote:
    week_number: int
    year: int
    week_start_date: str
    week_end_date: str
    total_reviews_analyzed: int
    top_themes: List[ThemeSummary] = field(default_factory=list)
    user_quotes: List[str] = field(default_factory=list)
    action_ideas: List[str] = field(default_factory=list)
    overall_sentiment: float = 0.0
    word_count: int = 0
    generated_at: datetime = field(default_factory=datetime.now)
    surge_week: bool = False
    clustering_fallback: bool = False


def count_words(text: str) -> int:
    """Count words in text, handling various edge cases."""
    if not text or not text.strip():
        return 0
    
    # Split on whitespace and filter out empty strings
    words = [word.strip() for word in text.split() if word.strip()]
    return len(words)


def truncate_to_250(text: str, note: WeeklyPulseNote) -> str:
    """Truncate content to meet 250-word limit by shortening various components."""
    if count_words(text) <= 250:
        return text
    
    print(f"Truncating pulse note from {count_words(text)} words to 250 words limit")
    
    # Shorten action ideas (keep first 15 words)
    note.action_ideas = [
        " ".join(action.split()[:15]) + ("..." if len(action.split()) > 15 else "")
        for action in note.action_ideas
        if action.strip()
    ]
    
    # Shorten quotes (keep first 30 words)
    note.user_quotes = [
        " ".join(quote.split()[:30]) + ("..." if len(quote.split()) > 30 else "")
        for quote in note.user_quotes
        if quote.strip()
    ]
    
    # Re-render with truncated content
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template("pulse_template.j2")
    return tmpl.render(note=note)


def build_pulse_note(labeled_themes: List[Dict[str, Any]], quotes: List[str],
                     ingestion_summary: Dict[str, Any]) -> WeeklyPulseNote:
    """Build a weekly pulse note from themes, quotes, and ingestion summary."""
    
    # Sort themes by urgency score and take top 3
    sorted_themes = sorted(
        labeled_themes, 
        key=lambda x: x.get("urgency_score", 0), 
        reverse=True
    )[:3]
    
    # Create theme summaries
    top_themes = []
    action_ideas = []
    
    for i, theme in enumerate(sorted_themes):
        theme_summary = ThemeSummary(
            rank=i + 1,
            theme_id=theme.get("theme_id", ""),
            label=theme.get("theme_label", theme.get("label", "")),
            volume=theme.get("volume", 0),
            urgency_score=round(theme.get("urgency_score", 0), 1),
            sentiment_score=round(theme.get("sentiment_score", 0), 2),
            trend_direction=theme.get("trend_direction", "stable"),
            top_keywords=theme.get("top_keywords", [])[:5],  # Limit to top 5 keywords
            action_idea=theme.get("action_idea", "")
        )
        top_themes.append(theme_summary)
        
        # Collect action ideas
        if theme_summary.action_idea:
            action_ideas.append(theme_summary.action_idea)
    
    # Calculate overall sentiment (weighted by volume)
    sentiments = [t.get("sentiment_score", 0) for t in labeled_themes]
    volumes = [t.get("volume", 1) for t in labeled_themes]
    total_vol = sum(volumes) or 1
    
    overall_sentiment = sum(s * v for s, v in zip(sentiments, volumes)) / total_vol
    
    # Get week information
    today = date.today()
    week_num = ingestion_summary.get("week_number", today.isocalendar()[1])
    year = ingestion_summary.get("year", today.year)
    
    # Calculate week date range
    week_start = today - timedelta(days=today.weekday())
    week_end = today
    
    # Check if this was a surge week
    surge_week = ingestion_summary.get("surge_mode", False)
    
    # Check if clustering fallback was used
    clustering_fallback = any(
        theme.get("labeling_method") == "keyword_fallback" 
        for theme in labeled_themes
    )
    
    # Final PII check on all quotes and actions
    from ingestion.pii_stripper import strip_pii_text
    quotes = [strip_pii_text(q) if q else q for q in quotes]
    action_ideas = [strip_pii_text(a) if a else a for a in action_ideas]

    # Create the pulse note
    note = WeeklyPulseNote(
        week_number=week_num,
        year=year,
        week_start_date=str(week_start),
        week_end_date=str(week_end),
        total_reviews_analyzed=ingestion_summary.get("inserted", 0),
        top_themes=top_themes,
        user_quotes=quotes[:3],  # Ensure max 3 quotes
        action_ideas=action_ideas[:5],  # Ensure max 5 action ideas
        overall_sentiment=round(overall_sentiment, 2),
        word_count=0,
        generated_at=datetime.now(),
        surge_week=surge_week,
        clustering_fallback=clustering_fallback
    )
    
    # Render markdown and count words
    md = render_pulse_note_markdown(note)
    note.word_count = count_words(md)
    
    # Truncate if over 250 words
    if note.word_count > 250:
        print(f"Word count {note.word_count} exceeds 250 limit, truncating...")
        md = truncate_to_250(md, note)
        note.word_count = count_words(md)
    
    return note


def render_pulse_note_markdown(note: WeeklyPulseNote) -> str:
    """Render the pulse note as markdown using Jinja2 template."""
    try:
        env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
        tmpl = env.get_template("pulse_template.j2")
        return tmpl.render(note=note)
    except Exception as e:
        print(f"Error rendering pulse note: {e}")
        # Fallback rendering
        return _fallback_render(note)


def _fallback_render(note: WeeklyPulseNote) -> str:
    """Fallback rendering if template fails."""
    lines = [
        f"# Groww Weekly App Pulse — Week {note.week_number}, {note.year}",
        f"_{note.week_start_date} to {note.week_end_date} · {note.total_reviews_analyzed} reviews analyzed_"
    ]
    
    if note.surge_week:
        lines.append("⚡ **Surge Week Detected** — high review volume. Sample of 500 analyzed.")
    
    lines.append("")
    lines.append("## Top Themes This Week")
    lines.append("")
    
    for theme in note.top_themes:
        lines.append(f"### {theme.rank}. {theme.label}")
        lines.append(f"- Volume: {theme.volume}")
        lines.append(f"- Urgency: {theme.urgency_score}/10")
        lines.append(f"- Trend: {theme.trend_direction}")
        lines.append("")
    
    if note.user_quotes:
        lines.append("## What Users Are Saying")
        lines.append("")
        for quote in note.user_quotes:
            if quote.strip():
                lines.append(f"> \"{quote}\"")
                lines.append("")
    
    if note.action_ideas:
        lines.append("## Recommended Actions")
        lines.append("")
        for i, action in enumerate(note.action_ideas, 1):
            if action.strip():
                lines.append(f"{i}. {action}")
                lines.append("")
    
    lines.append("---")
    lines.append(f"_Generated {note.generated_at.strftime('%Y-%m-%d %H:%M')} IST · {note.word_count} words_")
    
    return "\n".join(lines)


def test_pulse_builder():
    """Test function to verify pulse builder works correctly."""
    # Create test data
    test_themes = [
        {
            "theme_id": "T1",
            "theme_label": "App Performance",
            "volume": 25,
            "urgency_score": 8.5,
            "sentiment_score": -0.7,
            "trend_direction": "worsening",
            "top_keywords": ["slow", "crash", "bug"],
            "action_idea": "Investigate performance issues and optimize app speed",
            "labeling_method": "llm"
        },
        {
            "theme_id": "T2",
            "theme_label": "Customer Support",
            "volume": 15,
            "urgency_score": 6.0,
            "sentiment_score": -0.3,
            "trend_direction": "stable",
            "top_keywords": ["support", "response", "help"],
            "action_idea": "Improve response times and add live chat",
            "labeling_method": "llm"
        },
        {
            "theme_id": "T3",
            "theme_label": "Features",
            "volume": 8,
            "urgency_score": 4.0,
            "sentiment_score": 0.5,
            "trend_direction": "improving",
            "top_keywords": ["features", "new", "request"],
            "action_idea": "Consider adding requested features in next release",
            "labeling_method": "llm"
        }
    ]
    
    test_quotes = [
        "The app crashes every time I try to trade, this is unacceptable!",
        "Customer support never responds to my tickets, very frustrating.",
        "Love the new features, keep up the good work!"
    ]
    
    test_summary = {
        "week_number": 15,
        "year": 2024,
        "inserted": 150,
        "surge_mode": False
    }
    
    # Build pulse note
    note = build_pulse_note(test_themes, test_quotes, test_summary)
    
    print(f"Built pulse note for week {note.week_number}, {note.year}")
    print(f"Word count: {note.word_count}")
    print(f"Top themes: {len(note.top_themes)}")
    print(f"Quotes: {len(note.user_quotes)}")
    print(f"Action ideas: {len(note.action_ideas)}")
    print(f"Overall sentiment: {note.overall_sentiment}")
    
    # Render markdown
    markdown = render_pulse_note_markdown(note)
    print(f"\nMarkdown preview (first 500 chars):")
    print(markdown[:500] + "...")


if __name__ == "__main__":
    test_pulse_builder()
