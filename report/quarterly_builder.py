"""
Quarterly report builder — aggregates 12 weekly runs into one report.
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, date, timedelta
from storage.db import get_session
from storage.models import WeeklyRun, Theme


def count_consecutive_worsening(urgency_history: list[float]) -> int:
    """Count consecutive weeks where urgency is worsening (increasing)."""
    count = 0
    for i in range(len(urgency_history) - 1, 0, -1):
        if urgency_history[i] > urgency_history[i-1]:
            count += 1
        else:
            break
    return count


def build_heatmap(runs: list, themes_by_run: dict) -> str:
    """Build a heatmap showing urgency scores across weeks for each theme."""
    BLOCKS = {(1, 4): "░", (5, 7): "▓", (8, 10): "█"}
    
    def get_block(score):
        if score is None:
            return " "
        for (lo, hi), block in BLOCKS.items():
            if lo <= score <= hi:
                return block
        return "░"
    
    theme_ids = ["T1", "T2", "T3", "T4", "T5"]
    theme_labels = {
        "T1": "Onboarding & KYC",
        "T2": "Payments & Withdrawals",
        "T3": "Portfolio & Performance",
        "T4": "App Stability & UX",
        "T5": "Customer Support"
    }
    
    lines = []
    lines.append(f"\n{'Week':<8} {'T1':<6} {'T2':<6} {'T3':<6} {'T4':<6} {'T5':<6} Status")
    lines.append("-" * 52)
    
    for run in runs:
        run_themes = themes_by_run.get(run.id, {})
        row = f"Wk {run.week_number:<4} "
        for tid in theme_ids:
            score = run_themes.get(tid)
            row += f"{get_block(score):<6}"
        row += run.status
        lines.append(row)
    
    lines.append("\nLegend: ░ Low (1-4)  ▓ Medium (5-7)  █ High (8-10)")
    return "\n".join(lines)


def build_quarterly_report(quarter: int = None, year: int = None) -> str:
    """Build a comprehensive quarterly report aggregating all weekly runs."""
    if not year:
        year = date.today().year
    if not quarter:
        quarter = (date.today().month - 1) // 3 + 1
    
    session = get_session()
    try:
        # Get all weekly runs this quarter
        runs = (
            session.query(WeeklyRun)
            .filter(WeeklyRun.year == year)
            .order_by(WeeklyRun.week_number)
            .all()
        )
        
        if not runs:
            return f"No weekly runs found for Q{quarter} {year}."
        
        # Build themes_by_run lookup
        themes_by_run = {}
        all_themes = []
        for run in runs:
            themes = session.query(Theme).filter(Theme.run_id == run.id).all()
            themes_by_run[run.id] = {t.theme_id: t.urgency_score for t in themes}
            all_themes.extend(themes)
        
        # Total reviews
        total_reviews = sum(r.reviews_kept for r in runs)
        avg_sentiment = sum(
            t.sentiment_score for t in all_themes
        ) / len(all_themes) if all_themes else 0
        
        # Detect regressions (3+ consecutive worsening weeks)
        regressions = []
        theme_ids = ["T1", "T2", "T3", "T4", "T5"]
        for tid in theme_ids:
            history = []
            for run in runs:
                score = themes_by_run.get(run.id, {}).get(tid)
                if score is not None:
                    history.append(score)
            if len(history) >= 3:
                consec = count_consecutive_worsening(history)
                if consec >= 3:
                    regressions.append({
                        "theme_id": tid,
                        "consecutive_weeks": consec,
                        "urgency_history": history
                    })
        
        # Collect quotes archive
        quotes_archive = {}
        for theme in all_themes:
            tid = theme.theme_id
            if tid not in quotes_archive:
                quotes_archive[tid] = []
            if theme.top_quote and len(quotes_archive[tid]) < 3:
                quotes_archive[tid].append(theme.top_quote)
        
        # Surge weeks
        review_counts = [r.reviews_kept for r in runs if r.reviews_kept > 0]
        median_reviews = sorted(review_counts)[len(review_counts)//2] if review_counts else 300
        surge_weeks = [r for r in runs if r.reviews_kept > median_reviews * 2]
        
        # Build report
        lines = []
        lines.append(f"# Groww App Review Intelligence — Q{quarter} {year} Quarterly Report")
        lines.append(f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} IST_")
        lines.append(f"_Covers {len(runs)} weekly runs · {total_reviews:,} total reviews analyzed_")
        lines.append("\n---\n")
        
        # Section 1: Executive Summary
        lines.append("## 1. Executive Summary\n")
        lines.append(f"- **Total weeks analyzed:** {len(runs)} of 12")
        lines.append(f"- **Total reviews processed:** {total_reviews:,}")
        lines.append(f"- **Average sentiment:** {avg_sentiment:+.2f} (-1=negative, +1=positive)")
        lines.append(f"- **Surge weeks detected:** {len(surge_weeks)}")
        lines.append(f"- **Themes with regressions:** {len(regressions)}")
        
        # Section 2: Theme Heatmap
        lines.append("\n## 2. Theme Heatmap (Urgency by Week)\n")
        lines.append(build_heatmap(runs, themes_by_run))
        
        # Section 3: Top Regressions
        lines.append("\n## 3. Top Regressions\n")
        if regressions:
            for r in regressions:
                theme_label = {
                    "T1": "Onboarding & KYC",
                    "T2": "Payments & Withdrawals",
                    "T3": "Portfolio & Performance",
                    "T4": "App Stability & UX",
                    "T5": "Customer Support"
                }.get(r["theme_id"], r["theme_id"])
                lines.append(
                    f"- **{theme_label}**: worsening for "
                    f"{r['consecutive_weeks']} consecutive weeks "
                    f"(urgency: {r['urgency_history']})"
                )
        else:
            lines.append("_No themes showed 3+ consecutive weeks of worsening urgency._")
        
        # Section 4: Verbatim Quotes Archive
        lines.append("\n## 4. Verbatim Quotes Archive\n")
        for tid, quotes in quotes_archive.items():
            theme_label = {
                "T1": "Onboarding & KYC", "T2": "Payments & Withdrawals",
                "T3": "Portfolio & Performance", "T4": "App Stability & UX",
                "T5": "Customer Support"
            }.get(tid, tid)
            lines.append(f"\n### {theme_label}")
            for q in quotes:
                lines.append(f'> "{q}"')
        
        # Section 5: Action Backlog
        lines.append("\n## 5. Action Backlog\n")
        seen_actions = set()
        action_count = 0
        for theme in all_themes:
            if theme.action_idea and theme.action_idea not in seen_actions:
                seen_actions.add(theme.action_idea)
                lines.append(f"- [ ] [{theme.theme_id}] {theme.action_idea}")
                action_count += 1
        if action_count == 0:
            lines.append("_No actions recorded yet._")
        
        # Section 6: Seasonal Observations
        lines.append("\n## 6. Seasonal Observations\n")
        if surge_weeks:
            for sw in surge_weeks:
                lines.append(
                    f"- **Week {sw.week_number}**: surge detected "
                    f"({sw.reviews_kept} reviews vs ~{median_reviews} normal). "
                    f"Possible market event or app update."
                )
        else:
            lines.append("_No unusual volume spikes detected this quarter._")
        
        lines.append("\n---")
        lines.append("_Report auto-generated by Groww Pulse Agent_")
        
        report = "\n".join(lines)
        
        # Save to archive
        out_path = Path("data/archive") / f"groww_q{quarter}_{year}_quarterly_report.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"Quarterly report saved to: {out_path}")
        
        return report
    
    finally:
        session.close()


if __name__ == "__main__":
    report = build_quarterly_report()
    print(report[:500] + "\n...[truncated]")
