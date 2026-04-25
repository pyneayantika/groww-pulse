"""
Weekly report generator.
Generates a standalone one-page weekly pulse report in three formats:
  1. Markdown (.md)    — for Google Docs and archive
  2. HTML (.html)      — for email and dashboard preview
  3. PDF-ready (.html) — print-friendly version
"""

import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, date, timedelta
from jinja2 import Environment, FileSystemLoader
from storage.db import get_session
from storage.models import WeeklyRun, Theme, Review
from ingestion.pii_stripper import strip_pii_text

TEMPLATE_DIR = Path(__file__).parent / "templates"

# ── Helpers ──────────────────────────────────────────────────────────

def get_week_dates(week_number: int, year: int) -> tuple[str, str]:
    """Return Monday and Sunday date strings for a given ISO week."""
    jan1 = date(year, 1, 4)
    start_of_week1 = jan1 - timedelta(days=jan1.weekday())
    week_start = start_of_week1 + timedelta(weeks=week_number - 1)
    week_end = week_start + timedelta(days=6)
    return week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")


def get_trend_emoji(direction: str) -> str:
    return {"worsening": "↑🔴", "improving": "↓🟢", "stable": "→🟡"}.get(
        direction, "→"
    )


def get_urgency_label(score: float) -> str:
    if score >= 8:
        return "Critical"
    elif score >= 5:
        return "High"
    elif score >= 3:
        return "Medium"
    return "Low"


# ── Core builder ─────────────────────────────────────────────────────────────

def build_weekly_report(week_number: int = None, year: int = None) -> dict:
    """
    Build a complete weekly report data dict from the database.
    If week_number/year not provided, uses the most recent completed run.
    """
    session = get_session()
    try:
        if week_number and year:
            run = (
                session.query(WeeklyRun)
                .filter(
                    WeeklyRun.week_number == week_number,
                    WeeklyRun.year == year
                )
                .first()
            )
        else:
            run = (
                session.query(WeeklyRun)
                .filter(WeeklyRun.status == "completed")
                .order_by(WeeklyRun.id.desc())
                .first()
            )

        if not run:
            return {"error": "No completed weekly run found in database."}

        themes = (
            session.query(Theme)
            .filter(Theme.run_id == run.id)
            .order_by(Theme.urgency_score.desc())
            .all()
        )

        week_start, week_end = get_week_dates(run.week_number, run.year)

        # Build top 3 themes
        top_themes = []
        for i, t in enumerate(themes[:3]):
            top_themes.append({
                "rank": i + 1,
                "theme_id": t.theme_id,
                "label": t.label,
                "volume": t.volume,
                "urgency_score": round(t.urgency_score, 1),
                "urgency_label": get_urgency_label(t.urgency_score),
                "sentiment_score": round(t.sentiment_score, 2),
                "trend_direction": t.trend_direction,
                "trend_emoji": get_trend_emoji(t.trend_direction),
                "top_quote": strip_pii_text(t.top_quote or ""),
                "keywords": t.keywords or [],
                "action_idea": t.action_idea or "",
            })

        # Select 3 best quotes (priority: urgency → sentiment → trend)
        quotes = []
        seen_themes = set()
        priority_sorted = sorted(
            themes,
            key=lambda x: (
                -x.urgency_score,
                x.sentiment_score,
                x.trend_direction == "worsening"
            )
        )
        for t in priority_sorted:
            if t.theme_id not in seen_themes and t.top_quote:
                quotes.append(strip_pii_text(t.top_quote))
                seen_themes.add(t.theme_id)
            if len(quotes) == 3:
                break
        while len(quotes) < 3:
            quotes.append("")

        # Action ideas from top 3 themes
        action_ideas = [
            t.get("action_idea", "") for t in top_themes
        ]

        # Overall sentiment (volume-weighted)
        total_vol = sum(t.volume for t in themes) or 1
        overall_sentiment = sum(
            t.sentiment_score * t.volume for t in themes
        ) / total_vol

        return {
            "week_number": run.week_number,
            "year": run.year,
            "week_start": week_start,
            "week_end": week_end,
            "run_date": run.run_date.strftime("%Y-%m-%d %H:%M") if run.run_date else "",
            "total_reviews": run.reviews_kept,
            "reviews_fetched": run.reviews_fetched,
            "reviews_kept": run.reviews_kept,
            "noise_dropped": run.noise_dropped,
            "themes_found": run.themes_found,
            "top_themes": top_themes,
            "all_themes": [
                {
                    "theme_id": t.theme_id,
                    "label": t.label,
                    "volume": t.volume,
                    "urgency_score": round(t.urgency_score, 1),
                    "sentiment_score": round(t.sentiment_score, 2),
                    "trend_direction": t.trend_direction,
                    "top_quote": strip_pii_text(t.top_quote or ""),
                    "action_idea": t.action_idea or "",
                }
                for t in themes
            ],
            "user_quotes": quotes,
            "action_ideas": action_ideas,
            "overall_sentiment": round(overall_sentiment, 2),
            "gdoc_url": run.gdoc_url or "",
            "surge_week": run.surge_mode,
            "algorithm_used": run.algorithm_used or "bertopic",
            "status": run.status,
        }
    finally:
        session.close()


# ── Markdown renderer ─────────────────────────────────────────────────────────────

def render_weekly_markdown(data: dict) -> str:
    """Render the weekly pulse note as Markdown (≤250 words enforced)."""

    if "error" in data:
        return f"# Error\n{data['error']}"

    lines = []
    lines.append(
        f"# Groww Weekly App Pulse — Week {data['week_number']}, {data['year']}"
    )
    lines.append(
        f"_{data['week_start']} to {data['week_end']} · "
        f"{data['total_reviews']:,} reviews analyzed_"
    )

    if data.get("surge_week"):
        lines.append(
            "\n⚡ **Surge Week** — unusually high review volume detected. "
            "Sample of 500 reviews analyzed."
        )

    lines.append("\n---\n")
    lines.append("## Top Themes This Week\n")
    lines.append("| Rank | Theme | Volume | Urgency | Trend |")
    lines.append("|------|-------|---------|-------|")
    for t in data["top_themes"]:
        lines.append(
            f"| {t['rank']} | {t['label']} | {t['volume']} | "
            f"{t['urgency_score']}/10 | {t['trend_direction']} |"
        )

    lines.append("\n## What Users Are Saying\n")
    for q in data["user_quotes"]:
        if q:
            lines.append(f'> "{q}"\n')

    lines.append("## Recommended Actions\n")
    for i, action in enumerate(data["action_ideas"], 1):
        if action:
            lines.append(f"{i}. {action}")

    lines.append(
        f"\n---\n_Generated {data['run_date']} IST · "
        f"Powered by Groww Pulse Agent_"
    )

    report = "\n".join(lines)

    # Enforce ≤250 words
    words = report.split()
    if len(words) > 250:
        # Shorten action ideas first
        data["action_ideas"] = [
            " ".join(a.split()[:15]) for a in data["action_ideas"]
        ]
        # Shorten quotes
        data["user_quotes"] = [
            " ".join(q.split()[:30]) + "..." if q else q
            for q in data["user_quotes"]
        ]
        return render_weekly_markdown(data)

    return report


# ── HTML renderer ─────────────────────────────────────────────────────────────

WEEKLY_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Groww Weekly Pulse — Week {{ data.week_number }}, {{ data.year }}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Inter', Arial, sans-serif; background: #f0faf6; color: #1a1a1a; }
  .page { max-width: 800px; margin: 32px auto; background: #fff;
          border-radius: 12px; overflow: hidden;
          box-shadow: 0 4px 24px rgba(0,179,134,0.1); }
  .header { background: #00B386; padding: 28px 36px; color: #fff; }
  .header h1 { font-size: 22px; font-weight: 700; }
  .header .meta { font-size: 13px; opacity: 0.85; margin-top: 4px; }
  .surge-banner { background: #FFF3CD; border-left: 4px solid #FFC107;
                  padding: 10px 36px; font-size: 13px; color: #856404; }
  .body { padding: 28px 36px; }
  .stats-row { display: grid; grid-template-columns: repeat(4,1fr);
               gap: 12px; margin-bottom: 24px; }
  .stat-card { background: #f0faf6; border-radius: 8px; padding: 14px;
               text-align: center; border: 1px solid #b3e8d8; }
  .stat-num { font-size: 22px; font-weight: 700; color: #00B386; }
  .stat-label { font-size: 11px; color: #666; margin-top: 2px; }
  h2 { font-size: 15px; font-weight: 600; color: #00B386;
       margin: 20px 0 10px; padding-bottom: 6px;
       border-bottom: 2px solid #e0f7f2; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: #00B386; color: #fff; padding: 9px 12px;
       text-align: left; font-weight: 600; }
  td { padding: 9px 12px; border-bottom: 1px solid #f0f0f0; }
  tr:nth-child(even) td { background: #f9fffe; }
  .urgency-badge { display: inline-block; padding: 2px 8px;
                   border-radius: 99px; font-size: 11px; font-weight: 600; }
  .critical { background: #fde8e8; color: #a32d2d; }
  .high { background: #fff0e0; color: #7a6000; }
  .medium { background: #fff9e0; color: #7a6000; }
  .low { background: #e8f5e9; color: #1b5e20; }
  blockquote { background: #f0faf6; border-left: 3px solid #00B386;
               border-radius: 6px; padding: 12px 16px; margin: 8px 0;
               font-style: italic; color: #555; font-size: 13px; }
  .actions ol { padding-left: 18px; }
  .actions li { padding: 6px 0; font-size: 13px;
                border-bottom: 1px dashed #eee; }
  .theme-cards { display: grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr));
                 gap: 12px; margin: 12px 0; }
  .theme-card { border: 1px solid #e0f7f2; border-radius: 8px; padding: 14px; }
  .theme-card-title { font-size: 13px; font-weight: 600; color: #00B386;
                      margin-bottom: 6px; }
  .theme-card-title { font-size: 13px; font-weight: 600; color: #00B386;
                      margin-bottom: 6px; }
  .cta-row { display: flex; gap: 12px; margin-top: 24px; flex-wrap: wrap; }
  .btn { display: inline-block; padding: 10px 20px; border-radius: 6px;
         font-size: 13px; font-weight: 600; text-decoration: none;
         cursor: pointer; border: none; }
  .btn-primary { background: #00B386; color: #fff; }
  .btn-outline { background: #fff; color: #00B386;
                 border: 1.5px solid #00B386; }
  .footer { background: #f9f9f9; padding: 16px 36px;
            font-size: 11px; color: #999; text-align: center;
            border-top: 1px solid #eee; }
  @media print { .cta-row { display: none; } body { background: #fff; } }
    .page { box-shadow: none; margin: 0; } }
</style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="header">
    <h1>📊 Groww Weekly App Pulse — Week {{ data.week_number }}, {{ data.year }}</h1>
    <div class="meta">
      {{ data.week_start }} to {{ data.week_end }} ·
      {{ data.total_reviews }} reviews analyzed ·
      {{ data.themes_found }} themes identified
    </div>
  </div>

  {% if data.surge_week %}
  <div class="surge-banner">
    ⚡ **Surge Week** — unusually high review volume detected.
       Sample of 500 reviews analyzed.
  </div>
  {% endif %}

  <div class="body">

    <!-- Stats Row -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-num">{{ data.reviews_fetched }}</div>
        <div class="stat-label">Reviews Fetched</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ data.reviews_kept }}</div>
        <div class="stat-label">Reviews Analyzed</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ data.themes_found }}</div>
        <div class="stat-label">Themes Found</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ data.overall_sentiment | round(2) }}</div>
        <div class="stat-label">Avg Sentiment</div>
      </div>
    </div>

    <!-- Top Themes Table -->
    <h2>🎯 Top Themes This Week</h2>
    <table>
      <tr>
        <th>#</th><th>Theme</th><th>Volume</th><th>Urgency</th><th>Trend</th>
      </tr>
      {% for t in data.top_themes %}
      <tr>
        <td><strong>{{ t.rank }}</strong></td>
        <td><strong>{{ t.label }}</strong></td>
        <td>{{ t.volume }} reviews</td>
        <td>
          <span class="urgency-badge {{ t.urgency_label | lower }}">
            {{ t.urgency_score }}/10 · {{ t.urgency_label }}
          </span>
        </td>
        <td>{{ t.trend_emoji }} {{ t.trend_direction }}</td>
      </tr>
      {% endfor %}
    </table>

    <!-- All Themes Cards -->
    {% if data.all_themes | length > 3 %}
    <h2>📋 All Themes</h2>
    <div class="theme-cards">
      {% for t in data.all_themes %}
      <div class="theme-card">
        <div class="theme-card-title">{{ t.theme_id }}: {{ t.label }}</div>
        <div style="font-size:12px;color:#555;margin-top:6px;
                    font-style:italic;">"{{ t.top_quote[:80] }}..."</div>
      </div>
      {% endfor %}
    </div>
    {% endif %}

    <!-- User Quotes -->
    <h2>💬 What Users Are Saying</h2>
    {% for quote in data.user_quotes %}
    {% if quote %}
    <blockquote>"{{ quote }}"</blockquote>
    {% endfor %}

    <!-- Recommended Actions -->
    <h2>✅ Recommended Actions</h2>
    <div class="actions">
      <ol>
      {% for action in data.action_ideas %}
      {% if action %}
      <li>{{ action }}</li>
      {% endfor %}
      </ol>
    </div>

    <!-- CTA Buttons -->
    <div class="cta-row">
      {% if data.gdoc_url %}
      <a href="{{ data.gdoc_url }}" class="btn btn-primary" target="_blank">
        📄 View Full Google Doc
      </a>
      {% endif %}
      <a href="javascript:window.print()" class="btn btn-outline">
        🖨️ Print / Save as PDF
      </a>
      <a href="http://localhost:5000" class="btn btn-outline">
        📊 Open Dashboard
      </a>
    </div>

  </div>

  <div class="footer">
    Generated {{ data.run_date }} IST ·
    Algorithm: {{ data.algorithm_used }} ·
    Auto-generated by Groww Pulse Agent every Monday 09:00 IST
  </div>
</div>
</body>
</html>"""


def render_weekly_html(data: dict) -> str:
    """Render the weekly report as a styled HTML page."""
    from jinja2 import Template
    tmpl = Template(WEEKLY_HTML_TEMPLATE)
    return tmpl.render(data=data)


# ── Save reports ──────────────────────────────────────────────────────────────

def save_weekly_reports(week_number: int = None, year: int = None) -> dict:
    """
    Build and save both Markdown and HTML weekly reports.
    Returns dict with file paths.
    """
    data = build_weekly_report(week_number, year)
    if "error" in data:
        print(f"Error: {data['error']}")
        return data

    wk = data["week_number"]
    yr = data["year"]

    archive_dir = Path("data/archive")
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Save Markdown
    md_path = archive_dir / f"groww_week_{wk:02d}_{yr}_pulse.md"
    md_content = render_weekly_markdown(data)
    md_path.write_text(md_content, encoding="utf-8")

    # Save HTML
    html_path = archive_dir / f"groww_week_{wk:02d}_{yr}_pulse.html"
    html_content = render_weekly_html(data)
    html_path.write_text(html_content, encoding="utf-8")

    # Save to email_drafts folder too
    drafts_dir = archive_dir / "email_drafts"
    drafts_dir.mkdir(exist_ok=True)
    draft_path = drafts_dir / f"email_draft_week_{wk:02d}_{yr}.html"
    draft_path.write_text(html_content, encoding="utf-8")

    print(f"Weekly report saved:")
    print(f"  Markdown : {md_path}")
    print(f"  HTML     : {html_path}")
    print(f"  Draft    : {draft_path}")

    return {
        "week_number": wk,
        "year": yr,
        "md_path": str(md_path),
        "html_path": str(html_path),
        "draft_path": str(draft_path),
        "word_count": len(md_content.split()),
    }


if __name__ == "__main__":
    result = save_weekly_reports()
    if "error" not in result:
        print(f"\nWord count: {result['word_count']} words")
        print("Weekly reports generated successfully.")
