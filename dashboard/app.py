import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from flask import Flask, render_template, jsonify, send_file, request
from storage.db import get_session
from storage.models import WeeklyRun, Theme
from storage.csv_archive import export_quarterly
import os
import sqlite3
import csv
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/summary")
def summary():
    """Overall system summary stats."""
    session = get_session()
    try:
        runs = session.query(WeeklyRun).filter(
            WeeklyRun.status == 'completed',
            WeeklyRun.themes_found > 0
        ).order_by(WeeklyRun.reviews_kept.desc()).all()

        if not runs:
            runs = session.query(WeeklyRun).filter(
                WeeklyRun.status == 'completed'
            ).order_by(WeeklyRun.id.desc()).all()

        best_run = runs[0] if runs else None

        # Direct DB count — always reflects real-time state
        db_path = os.getenv('DB_URL', 'sqlite:///data/groww_pulse.db').replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        total_reviews = conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
        android_count = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='android'").fetchone()[0]
        ios_count = conn.execute("SELECT COUNT(*) FROM reviews WHERE store='ios'").fetchone()[0]
        conn.close()

        from sqlalchemy import func as sqlfunc
        total_weeks = session.query(
            sqlfunc.count(sqlfunc.distinct(WeeklyRun.week_number))
        ).filter(
            WeeklyRun.status == 'completed',
            WeeklyRun.week_number <= 12
        ).scalar() or 0

        themes = []
        if best_run:
            themes_orm = session.query(Theme).filter(
                Theme.run_id == best_run.id
            ).order_by(Theme.urgency_score.desc()).all()
            # Deduplicate by label, cap at 5
            seen = {}
            for t in themes_orm:
                lbl = (t.label or "").strip()
                if lbl not in seen or (t.urgency_score or 0) > (seen[lbl].urgency_score or 0):
                    seen[lbl] = t
            themes_deduped = sorted(seen.values(), key=lambda x: x.urgency_score or 0, reverse=True)[:5]
            themes = [{
                "theme_id":        t.theme_id,
                "label":           t.label,
                "urgency_score":   round(t.urgency_score or 0, 1),
                "sentiment_score": round(t.sentiment_score or 0, 2),
                "volume":          t.volume or 0,
                "trend_direction": t.trend_direction or "stable",
                "top_quote":       t.top_quote or "",
                "action_idea":     t.action_idea or "",
                "keywords":        t.keywords or []
            } for t in themes_deduped]

        return jsonify({
            "total_reviews":  total_reviews,
            "android_count":  android_count,
            "ios_count":      ios_count,
            "total_weeks":    total_weeks,
            "themes_found":   len(themes),
            "top_urgency":    themes[0]["urgency_score"] if themes else 0,
            "top_trend":      themes[0]["trend_direction"] if themes else "stable",
            "gdoc_url":       best_run.gdoc_url if best_run else "",
            "last_run_date":  str(best_run.run_date)[:10] if best_run else "",
            "themes":         themes
        })
    except Exception as e:
        return jsonify({"error": str(e), "themes": [], "total_reviews": 0})
    finally:
        session.close()

@app.route("/api/weekly-history")
def weekly_history():
    """12 weeks history — one row per week, no duplicates."""
    session = get_session()
    try:
        all_runs = session.query(WeeklyRun).filter(
            WeeklyRun.status == 'completed',
            WeeklyRun.week_number <= 12
        ).order_by(WeeklyRun.week_number.asc()).all()

        # Deduplicate: keep best run per week (most reviews)
        week_map = {}
        for run in all_runs:
            wk = run.week_number
            if wk not in week_map:
                week_map[wk] = run
            else:
                if (run.reviews_kept or 0) > (week_map[wk].reviews_kept or 0):
                    week_map[wk] = run

        history = []
        for wk in sorted(week_map.keys()):
            r = week_map[wk]
            top_theme = session.query(Theme).filter(
                Theme.run_id == r.id
            ).order_by(Theme.urgency_score.desc()).first()

            history.append({
                "week_number":  wk,
                "year":         r.year or 2026,
                "run_date":     str(r.run_date)[:10],
                "reviews_kept": r.reviews_kept or 0,
                "themes_found": r.themes_found or 0,
                "status":       r.status,
                "top_issue":    top_theme.label if top_theme else "N/A",
                "top_urgency":  round(top_theme.urgency_score, 1) if top_theme else 0,
                "run_id":       r.id,
                "is_surge":     (r.reviews_kept or 0) > 600
            })

        return jsonify(history)
    except Exception as e:
        return jsonify([])
    finally:
        session.close()

@app.route("/api/week/<int:week_num>/themes")
def week_themes(week_num):
    """Get themes for a specific week."""
    session = get_session()
    try:
        run = session.query(WeeklyRun).filter(
            WeeklyRun.week_number == week_num,
            WeeklyRun.status == 'completed'
        ).order_by(WeeklyRun.reviews_kept.desc()).first()

        if not run:
            return jsonify({"error": "Week not found", "themes": []})

        themes = session.query(Theme).filter(
            Theme.run_id == run.id
        ).order_by(Theme.urgency_score.desc()).all()

        return jsonify({
            "week_number":  week_num,
            "reviews_kept": run.reviews_kept,
            "themes": [{
                "theme_id":        t.theme_id,
                "label":           t.label,
                "urgency_score":   round(t.urgency_score or 0, 1),
                "sentiment_score": round(t.sentiment_score or 0, 2),
                "volume":          t.volume or 0,
                "trend_direction": t.trend_direction or "stable",
                "top_quote":       t.top_quote or "",
                "action_idea":     t.action_idea or "",
            } for t in themes]
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        session.close()

@app.route("/api/export/csv/<int:week_num>")
def export_week_csv(week_num):
    """Export reviews for a specific week as CSV."""
    try:
        archive = Path("data/archive")
        candidates = [
            archive / f"week_{week_num:02d}_2026.csv",
            archive / f"week_{week_num}_2026.csv",
        ]
        for candidate in candidates:
            if candidate.exists():
                return send_file(
                    str(candidate.resolve()),
                    as_attachment=True,
                    download_name=f"groww_week_{week_num:02d}_2026_reviews.csv",
                    mimetype="text/csv; charset=utf-8"
                )
        # Generate on the fly
        db_path = os.getenv('DB_URL', 'sqlite:///data/groww_pulse.db').replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        rows = conn.execute('''
            SELECT review_id, store, rating, title, text,
                   date, app_version, language_detected,
                   pii_stripped, suspicious_review, week_number
            FROM reviews WHERE week_number=?
            ORDER BY rating ASC, date DESC
        ''', (week_num,)).fetchall()
        conn.close()
        if not rows:
            return jsonify({"error": f"No reviews found for Week {week_num}"}), 404
        out = archive / f"week_{week_num:02d}_2026.csv"
        archive.mkdir(parents=True, exist_ok=True)
        with open(out, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Review ID', 'Store', 'Rating (1-5)', 'Title',
                'Review Text', 'Date', 'App Version', 'Language',
                'PII Stripped', 'Suspicious', 'Week Number'
            ])
            writer.writerows(rows)
        return send_file(
            str(out.resolve()),
            as_attachment=True,
            download_name=f"groww_week_{week_num:02d}_2026_reviews.csv",
            mimetype="text/csv; charset=utf-8"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export/quarterly")
def export_quarterly_csv():
    """Export all reviews as quarterly CSV."""
    try:
        archive = Path("data/archive")
        archive.mkdir(parents=True, exist_ok=True)
        q_file = archive / "groww_q1_2026_quarterly_reviews.csv"
        if not q_file.exists():
            db_path = os.getenv('DB_URL', 'sqlite:///data/groww_pulse.db').replace('sqlite:///', '')
            conn = sqlite3.connect(db_path)
            rows = conn.execute('''
                SELECT review_id, store, rating, title, text,
                       date, app_version, language_detected,
                       pii_stripped, suspicious_review, week_number
                FROM reviews
                ORDER BY week_number ASC, date DESC
            ''').fetchall()
            conn.close()
            with open(q_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Review ID', 'Store', 'Rating (1-5)', 'Title',
                    'Review Text', 'Date', 'App Version', 'Language',
                    'PII Stripped', 'Suspicious', 'Week Number'
                ])
                writer.writerows(rows)
        return send_file(
            str(q_file.resolve()),
            as_attachment=True,
            download_name="groww_q1_2026_all_reviews.csv",
            mimetype="text/csv; charset=utf-8"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export/themes")
def export_themes_csv():
    """Export theme analysis summary as CSV."""
    try:
        archive = Path("data/archive")
        archive.mkdir(parents=True, exist_ok=True)
        t_file = archive / "groww_q1_2026_themes_summary.csv"
        if not t_file.exists():
            db_path = os.getenv('DB_URL', 'sqlite:///data/groww_pulse.db').replace('sqlite:///', '')
            conn = sqlite3.connect(db_path)
            rows = conn.execute('''
                SELECT t.theme_id, t.label,
                       t.urgency_score, t.sentiment_score,
                       t.volume, t.trend_direction,
                       t.top_quote, t.action_idea,
                       w.week_number, w.year
                FROM themes t
                JOIN weekly_runs w ON t.run_id = w.id
                WHERE w.status = "completed"
                ORDER BY w.week_number ASC, t.urgency_score DESC
            ''').fetchall()
            conn.close()
            with open(t_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Theme ID', 'Theme Label',
                    'Urgency Score', 'Sentiment Score',
                    'Volume', 'Trend Direction',
                    'Top Quote', 'Action Idea',
                    'Week Number', 'Year'
                ])
                writer.writerows(rows)
        return send_file(
            str(t_file.resolve()),
            as_attachment=True,
            download_name="groww_q1_2026_themes_summary.csv",
            mimetype="text/csv; charset=utf-8"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/export/theme/<theme_id>")
def export_theme_reviews_csv(theme_id):
    """Export reviews matching a specific theme (by keyword) as CSV."""
    try:
        db_path = os.getenv('DB_URL', 'sqlite:///data/groww_pulse.db').replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)

        # Fetch the theme row (most recent completed run)
        theme_row = conn.execute('''
            SELECT t.theme_id, t.label, t.keywords, t.volume, w.week_number
            FROM themes t
            JOIN weekly_runs w ON t.run_id = w.id
            WHERE t.theme_id = ? AND w.status = "completed"
            ORDER BY w.id DESC LIMIT 1
        ''', (theme_id,)).fetchone()

        # Fallback: try matching by label if theme_id not found
        if not theme_row:
            theme_row = conn.execute('''
                SELECT t.theme_id, t.label, t.keywords, t.volume, w.week_number
                FROM themes t
                JOIN weekly_runs w ON t.run_id = w.id
                WHERE LOWER(t.label) = LOWER(?) AND w.status = "completed"
                ORDER BY w.id DESC LIMIT 1
            ''', (theme_id,)).fetchone()

        if not theme_row:
            conn.close()
            return jsonify({"error": f"Theme '{theme_id}' not found"}), 404

        t_id, label, keywords_raw, volume, week_num = theme_row

        # Parse keywords JSON
        import json as _json
        try:
            keywords = _json.loads(keywords_raw) if isinstance(keywords_raw, str) else (keywords_raw or [])
        except Exception:
            keywords = []

        # Build LIKE conditions for each keyword — search across ALL reviews (no week filter)
        if keywords:
            like_clauses = ' OR '.join(['LOWER(text) LIKE ?'] * len(keywords))
            params = ['%' + kw.lower() + '%' for kw in keywords]
            rows = conn.execute(f'''
                SELECT review_id, store, rating, title, text, date,
                       app_version, language_detected, week_number
                FROM reviews
                WHERE ({like_clauses})
                ORDER BY rating ASC, date DESC
            ''', params).fetchall()
        else:
            rows = []

        # Fallback: if no keyword matches, return all reviews for that theme's week
        if not rows:
            rows = conn.execute('''
                SELECT review_id, store, rating, title, text, date,
                       app_version, language_detected, week_number
                FROM reviews WHERE week_number = ?
                ORDER BY rating ASC, date DESC
            ''', (week_num,)).fetchall()

        conn.close()

        if not rows:
            return jsonify({"error": f"No reviews matched for theme '{label}'"}), 404

        archive = Path("data/archive")
        archive.mkdir(parents=True, exist_ok=True)
        safe_label = "".join(c if c.isalnum() or c in "_- " else "_" for c in label).strip().replace(" ", "_")[:40]
        out = archive / f"groww_theme_{safe_label}_wk{week_num:02d}.csv"

        with open(out, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Review ID', 'Store', 'Rating', 'Title', 'Review Text',
                             'Date', 'App Version', 'Language', 'Week'])
            writer.writerows(rows)

        return send_file(
            str(out.resolve()),
            as_attachment=True,
            download_name=f"groww_theme_{safe_label}_wk{week_num:02d}.csv",
            mimetype="text/csv; charset=utf-8"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/store-breakdown")
def store_breakdown():
    """iOS vs Android review breakdown."""
    session = get_session()
    try:
        db_path = os.getenv(
            'DB_URL', 'sqlite:///data/groww_pulse.db'
        ).replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)

        android_total = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE store='android'"
        ).fetchone()[0]

        ios_total = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE store='ios'"
        ).fetchone()[0]

        total = android_total + ios_total

        android_ratings = {}
        ios_ratings = {}
        for stars in [1, 2, 3, 4, 5]:
            android_ratings[stars] = conn.execute(
                "SELECT COUNT(*) FROM reviews WHERE store='android' AND rating=?",
                (stars,)
            ).fetchone()[0]
            ios_ratings[stars] = conn.execute(
                "SELECT COUNT(*) FROM reviews WHERE store='ios' AND rating=?",
                (stars,)
            ).fetchone()[0]

        weekly = conn.execute("""
            SELECT week_number,
                   SUM(CASE WHEN store='android' THEN 1 ELSE 0 END) as android,
                   SUM(CASE WHEN store='ios' THEN 1 ELSE 0 END) as ios
            FROM reviews
            GROUP BY week_number
            ORDER BY week_number
        """).fetchall()

        real_android = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE store='android' AND date >= '2026-04-21'"
        ).fetchone()[0]

        conn.close()

        return jsonify({
            "total":   total,
            "android": {
                "count":        android_total,
                "percentage":   round(android_total / total * 100, 1) if total else 0,
                "ratings":      android_ratings,
                "real_reviews": real_android,
                "scraper":      "google-play-scraper (npm)",
            },
            "ios": {
                "count":        ios_total,
                "percentage":   round(ios_total / total * 100, 1) if total else 0,
                "ratings":      ios_ratings,
                "real_reviews": 0,
                "scraper":      "Playwright (limited)",
            },
            "weekly_breakdown": [
                {"week": r[0], "android": r[1], "ios": r[2]}
                for r in weekly
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/api/trigger-run", methods=["POST"])
def trigger_run():
    """Manually trigger the pipeline."""
    try:
        from scheduler.orchestrator import run_weekly_pipeline
        result = run_weekly_pipeline()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("Starting Groww Pulse Dashboard...")
    print("Dashboard: http://localhost:5000")
    port = int(__import__("os").environ.get("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)
