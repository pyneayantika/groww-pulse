import os
import httpx
from pathlib import Path
from typing import Optional
from datetime import datetime

GDOCS_MCP_URL = "https://drivemcp.googleapis.com"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def get_access_token() -> str:
    """Get OAuth2 access token using refresh token."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("Missing Google OAuth credentials. Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN")
    
    response = httpx.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    })
    response.raise_for_status()
    return response.json()["access_token"]


def check_doc_exists(week_number: int, year: int) -> Optional[str]:
    """Check if a Google Doc already exists for the given week and return its web view link."""
    try:
        token = get_access_token()
        title = f"Groww Weekly App Pulse — Week {week_number}, {year}"
        
        resp = httpx.get(
            "https://www.googleapis.com/drive/v3/files",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "q": f"name='{title}' and mimeType='application/vnd.google-apps.document'",
                "fields": "files(id,webViewLink,name)"
            }
        )
        resp.raise_for_status()
        
        files = resp.json().get("files", [])
        if files:
            print(f"Found existing doc: {files[0].get('name')}")
            return files[0].get("webViewLink")
            
    except Exception as e:
        print(f"Doc check failed: {e}")
    
    return None


def create_pulse_doc(note, markdown_content: str) -> str:
    """
    Create a fully formatted Google Doc with:
    - Branded header with Groww green
    - Executive summary section
    - Detailed themes table with all 5 themes
    - User quotes section with blockquote styling
    - Action items with numbered list
    - All themes deep dive section
    - Footer with metadata
    """
    week_num = note.week_number
    year = note.year

    # Check if doc already exists
    existing = check_doc_exists(week_num, year)
    if existing:
        print(f"Reusing existing doc: {existing}")
        return existing

    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    title = f"Groww Weekly App Pulse — Week {week_num}, {year}"

    # STEP 1: Create the document
    meta = httpx.post(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        json={"name": title, "mimeType": "application/vnd.google-apps.document"}
    )
    meta.raise_for_status()
    doc_id = meta.json()["id"]
    print(f"Created Google Doc ID: {doc_id}")

    # STEP 2: Build comprehensive document content
    top_themes = note.top_themes if hasattr(note, 'top_themes') else []
    quotes = note.user_quotes if hasattr(note, 'user_quotes') else []
    actions = note.action_ideas if hasattr(note, 'action_ideas') else []
    total_reviews = note.total_reviews_analyzed if hasattr(note, 'total_reviews_analyzed') else 0
    sentiment = note.overall_sentiment if hasattr(note, 'overall_sentiment') else 0
    generated = note.generated_at if hasattr(note, 'generated_at') else datetime.now()
    surge = note.surge_week if hasattr(note, 'surge_week') else False

    doc_text = f"""GROWW WEEKLY APP PULSE REPORT
Week {week_num}, {year}

EXECUTIVE SUMMARY

This report analyzes {total_reviews:,} user reviews collected from Google Play Store and iOS App Store for the Groww investment platform during Week {week_num} of {year}. The AI-powered analysis identifies the top themes, urgency scores, and recommended product actions for the week.

Overall Sentiment Score: {sentiment:+.2f} (scale: -1.0 negative to +1.0 positive)
Reviews Analyzed: {total_reviews:,}
Themes Identified: {len(top_themes)}
Report Generated: {generated.strftime('%Y-%m-%d %H:%M')} IST
{"SURGE WEEK: Unusually high review volume detected this week." if surge else ""}

─────────────────────────────────────────────────

TOP 3 THEMES THIS WEEK

The following themes were identified as the most urgent issues requiring immediate product attention:

"""

    for i, theme in enumerate(top_themes):
        label = theme.label if hasattr(theme, 'label') else str(theme)
        urgency = theme.urgency_score if hasattr(theme, 'urgency_score') else 0
        volume = theme.volume if hasattr(theme, 'volume') else 0
        trend = theme.trend_direction if hasattr(theme, 'trend_direction') else ''
        sentiment_score = theme.sentiment_score if hasattr(theme, 'sentiment_score') else 0
        keywords = theme.top_keywords if hasattr(theme, 'top_keywords') else []
        urgency_label = "CRITICAL" if urgency >= 8 else "HIGH" if urgency >= 6 else "MEDIUM"
        trend_arrow = "Worsening" if trend == "worsening" else "Improving" if trend == "improving" else "Stable"
        doc_text += f"""Theme {i+1}: {label}
Urgency Score: {urgency:.1f}/10 ({urgency_label})
Review Volume: {volume} reviews this week
Sentiment: {sentiment_score:+.2f}
Trend: {trend_arrow}
Top Keywords: {', '.join(keywords[:5]) if keywords else 'N/A'}

"""

    doc_text += """─────────────────────────────────────────────────

WHAT USERS ARE SAYING
Real user quotes (PII-redacted) representing each top theme:

"""
    for quote in quotes:
        if quote and len(quote) > 5:
            doc_text += f'"{quote}"\n\n'

    doc_text += """─────────────────────────────────────────────────

RECOMMENDED ACTIONS
Based on the theme analysis, the following actions are recommended for the product team:

"""
    for i, action in enumerate(actions):
        if action:
            doc_text += f"{i+1}. {action}\n\n"

    doc_text += """─────────────────────────────────────────────────

ALL THEMES OVERVIEW

Theme Label | Volume | Urgency | Sentiment | Trend
"""
    for theme in top_themes:
        label = theme.label if hasattr(theme, 'label') else str(theme)
        urgency = theme.urgency_score if hasattr(theme, 'urgency_score') else 0
        volume = theme.volume if hasattr(theme, 'volume') else 0
        trend = theme.trend_direction if hasattr(theme, 'trend_direction') else ''
        sentiment_score = theme.sentiment_score if hasattr(theme, 'sentiment_score') else 0
        doc_text += f"{label} | {volume} reviews | {urgency:.1f}/10 | {sentiment_score:+.2f} | {trend}\n"

    doc_text += f"""
─────────────────────────────────────────────────

METHODOLOGY

Data Collection: Reviews scraped from Google Play Store (real-time) and iOS App Store using automated scraping pipeline.

Language Filter: Only English-language reviews retained (ASCII-ratio detection).

PII Protection: All personally identifiable information (phone numbers, emails, PAN numbers) automatically redacted before any processing.

AI Clustering: BERTopic algorithm clusters reviews into maximum 5 themes using semantic embeddings (BAAI/bge-small-en-v1.5).

LLM Labeling: Groq Llama 3.1 (llama-3.1-8b-instant) assigns urgency scores, sentiment scores, and action recommendations per theme.

─────────────────────────────────────────────────

ABOUT THIS REPORT

This report is automatically generated every Monday at 09:00 IST by the Groww Pulse Agent — an AI-powered review intelligence system built for product and growth teams.

For questions about this report, contact the product analytics team.

Generated: {generated.strftime('%Y-%m-%d %H:%M')} IST
System: Groww Pulse Agent v1.0
Model: BERTopic + Groq llama-3.1-8b-instant
"""

    # STEP 3: Insert content
    httpx.post(
        f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
        headers=headers,
        json={"requests": [{"insertText": {"location": {"index": 1}, "text": doc_text}}]}
    )

    # STEP 4: Apply formatting
    lines = doc_text.split('\n')
    index = 1
    format_requests = []

    SECTION_HEADINGS = {
        "EXECUTIVE SUMMARY", "TOP 3 THEMES THIS WEEK",
        "WHAT USERS ARE SAYING", "RECOMMENDED ACTIONS",
        "ALL THEMES OVERVIEW", "METHODOLOGY", "ABOUT THIS REPORT"
    }

    for line in lines:
        line_len = len(line) + 1  # +1 for newline

        if line == "GROWW WEEKLY APP PULSE REPORT":
            format_requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": index, "endIndex": index + line_len},
                    "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    "fields": "namedStyleType"
                }
            })
            format_requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": index, "endIndex": index + line_len},
                    "textStyle": {
                        "bold": True,
                        "fontSize": {"magnitude": 24, "unit": "PT"},
                        "foregroundColor": {"color": {"rgbColor": {
                            "red": 0.0, "green": 0.702, "blue": 0.525
                        }}}
                    },
                    "fields": "bold,fontSize,foregroundColor"
                }
            })

        elif line in SECTION_HEADINGS:
            format_requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": index, "endIndex": index + line_len},
                    "paragraphStyle": {"namedStyleType": "HEADING_2"},
                    "fields": "namedStyleType"
                }
            })
            format_requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": index, "endIndex": index + line_len},
                    "textStyle": {
                        "bold": True,
                        "fontSize": {"magnitude": 14, "unit": "PT"},
                        "foregroundColor": {"color": {"rgbColor": {
                            "red": 0.0, "green": 0.702, "blue": 0.525
                        }}}
                    },
                    "fields": "bold,fontSize,foregroundColor"
                }
            })

        elif line.startswith('Theme ') and ':' in line:
            format_requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": index, "endIndex": index + line_len},
                    "textStyle": {
                        "bold": True,
                        "fontSize": {"magnitude": 12, "unit": "PT"}
                    },
                    "fields": "bold,fontSize"
                }
            })

        elif line.startswith('"') and line.endswith('"'):
            format_requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": index, "endIndex": index + line_len},
                    "textStyle": {
                        "italic": True,
                        "foregroundColor": {"color": {"rgbColor": {
                            "red": 0.3, "green": 0.3, "blue": 0.3
                        }}}
                    },
                    "fields": "italic,foregroundColor"
                }
            })
            format_requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": index, "endIndex": index + line_len},
                    "paragraphStyle": {
                        "indentStart": {"magnitude": 36, "unit": "PT"}
                    },
                    "fields": "indentStart"
                }
            })

        index += line_len

    # Apply formatting in batches of 20
    for i in range(0, len(format_requests), 20):
        batch = format_requests[i:i + 20]
        try:
            httpx.post(
                f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
                headers=headers,
                json={"requests": batch}
            )
        except Exception as e:
            print(f"Formatting batch {i // 20} warning: {e}")

    # STEP 5: Set view-only sharing
    httpx.post(
        f"https://www.googleapis.com/drive/v3/files/{doc_id}/permissions",
        headers=headers,
        json={"role": "reader", "type": "anyone"}
    )

    # STEP 6: Get shareable URL
    file_resp = httpx.get(
        f"https://www.googleapis.com/drive/v3/files/{doc_id}",
        headers=headers,
        params={"fields": "webViewLink"}
    )
    url = file_resp.json().get(
        "webViewLink",
        f"https://docs.google.com/document/d/{doc_id}"
    )
    print(f"Google Doc created: {url}")
    return url


def convert_markdown_to_plain(markdown_content: str) -> str:
    """Convert markdown content to plain text for better Google Docs rendering."""
    if not markdown_content:
        return ""
    
    # Simple markdown to plain text conversion
    lines = markdown_content.split('\n')
    plain_lines = []
    
    for line in lines:
        # Convert headers to plain text with emphasis
        if line.startswith('# '):
            plain_lines.append(line[2:].upper())
        elif line.startswith('## '):
            plain_lines.append(line[3:])
        elif line.startswith('### '):
            plain_lines.append(line[4:])
        # Convert blockquotes
        elif line.strip().startswith('> '):
            plain_lines.append(f"QUOTE: {line.strip()[2:]}")
        # Convert table rows
        elif '|' in line and line.strip():
            # Simple table handling - just remove pipes
            clean_row = line.replace('|', ' ').strip()
            if clean_row and not all(c in '- ' for c in clean_row):
                plain_lines.append(clean_row)
        # Handle lists
        elif line.strip().startswith(('1. ', '2. ', '3. ', '4. ', '5. ')):
            plain_lines.append(line.strip())
        elif line.strip().startswith(('- ', '* ')):
            plain_lines.append(f"• {line.strip()[2:]}")
        else:
            plain_lines.append(line)
    
    # Join with proper spacing
    result = '\n'.join(plain_lines)
    
    # Add some spacing around sections
    result = result.replace('\n##', '\n\n##')
    result = result.replace('\n###', '\n\n###')
    result = result.replace('\n#', '\n\n#')
    
    return result.strip()


def test_gdocs_client():
    """Test function to verify Google Docs client works."""
    try:
        # Test token retrieval (will fail if credentials not set)
        token = get_access_token()
        print("Successfully retrieved access token")
        
        # Test doc existence check
        existing = check_doc_exists(1, 2024)
        print(f"Doc existence check result: {existing}")
        
    except Exception as e:
        print(f"Google Docs client test failed: {e}")
        print("This is expected if Google credentials are not configured")


if __name__ == "__main__":
    test_gdocs_client()
