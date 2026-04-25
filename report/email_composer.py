from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import re
from typing import Dict, Any

TEMPLATE_DIR = Path(__file__).parent / "templates"


def compose_email(note, gdoc_url: str) -> Dict[str, str]:
    """
    Compose email with HTML and text versions from pulse note.
    
    Args:
        note: WeeklyPulseNote object
        gdoc_url: URL to the Google Doc
        
    Returns:
        Dictionary with email components
    """
    try:
        env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
        tmpl = env.get_template("email_template.j2")
        body_html = tmpl.render(note=note, gdoc_url=gdoc_url)
        
        # Strip HTML tags for text version
        body_text = re.sub(r'<[^>]+>', '', body_html)
        
        # Clean up extra whitespace in text version
        body_text = re.sub(r'\s+', ' ', body_text).strip()
        
        return {
            "subject": f"📊 Groww App Pulse — Week {note.week_number}, {note.year}",
            "body_html": body_html,
            "body_text": body_text,
            "gdoc_url": gdoc_url
        }
        
    except Exception as e:
        print(f"Error composing email: {e}")
        return _fallback_email(note, gdoc_url)


def _fallback_email(note, gdoc_url: str) -> Dict[str, str]:
    """Fallback email composition if template fails."""
    subject = f"📊 Groww App Pulse — Week {note.week_number}, {note.year}"
    
    # Simple text fallback
    body_text = f"""
Groww App Pulse - Week {note.week_number}, {note.year}
{note.week_start_date} to {note.week_end_date}
{note.total_reviews_analyzed} reviews analyzed

Top Themes:
"""
    
    for theme in note.top_themes:
        body_text += f"\n{theme.rank}. {theme.label} (Volume: {theme.volume}, Urgency: {theme.urgency_score}/10)"
    
    if note.user_quotes:
        body_text += "\n\nWhat Users Are Saying:\n"
        for quote in note.user_quotes:
            if quote.strip():
                body_text += f"\n- \"{quote}\""
    
    if note.action_ideas:
        body_text += "\n\nRecommended Actions:\n"
        for i, action in enumerate(note.action_ideas, 1):
            if action.strip():
                body_text += f"\n{i}. {action}"
    
    body_text += f"\n\nView full report: {gdoc_url}"
    body_text += f"\nGenerated {note.generated_at.strftime('%Y-%m-%d %H:%M')} IST"
    
    return {
        "subject": subject,
        "body_html": f"<pre>{body_text}</pre>",
        "body_text": body_text.strip(),
        "gdoc_url": gdoc_url
    }


def test_email_composer():
    """Test function to verify email composer works correctly."""
    from .pulse_builder import WeeklyPulseNote, ThemeSummary
    from datetime import datetime
    
    # Create test note
    test_note = WeeklyPulseNote(
        week_number=15,
        year=2024,
        week_start_date="2024-04-08",
        week_end_date="2024-04-14",
        total_reviews_analyzed=150,
        top_themes=[
            ThemeSummary(
                rank=1,
                theme_id="T1",
                label="App Performance",
                volume=25,
                urgency_score=8.5,
                sentiment_score=-0.7,
                trend_direction="worsening",
                top_keywords=["slow", "crash", "bug"],
                action_idea="Investigate performance issues"
            )
        ],
        user_quotes=["The app crashes every time I try to trade"],
        action_ideas=["Investigate performance issues and optimize app speed"],
        overall_sentiment=-0.3,
        word_count=150,
        generated_at=datetime.now(),
        surge_week=False
    )
    
    # Compose email
    email = compose_email(test_note, "https://docs.google.com/document/d/123")
    
    print(f"Email subject: {email['subject']}")
    print(f"HTML length: {len(email['body_html'])}")
    print(f"Text length: {len(email['body_text'])}")
    print(f"Text preview: {email['body_text'][:200]}...")


if __name__ == "__main__":
    test_email_composer()
