import sys
import logging
import traceback
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

log = logging.getLogger("groww-pulse")


def run_weekly_pipeline() -> Dict[str, Any]:
    """Run the complete weekly pulse pipeline end-to-end."""
    summary = {"status": "running", "steps": {}}
    run_id = None
    
    try:
        # Initialize database and create run record
        from storage.db import get_session, init_db
        from storage.models import WeeklyRun, RunLog
        
        init_db()
        session = get_session()
        
        # Create weekly run record
        now = datetime.now()
        run = WeeklyRun(
            run_date=now,
            week_number=now.isocalendar()[1],
            year=now.year
        )
        session.add(run)
        session.commit()
        run_id = run.id
        
        def log_step(step: str, msg: str, level: str = "INFO"):
            """Log a step to both the logger and database."""
            log.info(f"[{step}] {msg}")
            try:
                entry = RunLog(run_id=run_id, level=level, message=msg, step=step)
                session.add(entry)
                session.commit()
            except Exception as e:
                log.error(f"Failed to log step to database: {e}")
        
        # STEP 1: Ingest reviews
        log_step("INGEST", "Starting review ingestion")
        from ingestion import run_ingestion
        ingest = run_ingestion(days_back=7)
        summary["steps"]["ingest"] = ingest
        log_step("INGEST", f"Inserted {ingest.get('inserted', 0)} reviews")
        
        # Update run with ingestion stats
        run.reviews_fetched = ingest.get('fetched', 0)
        run.reviews_kept = ingest.get('deduped', 0)
        run.english_count = ingest.get('english', 0)
        run.noise_dropped = ingest.get('noise_dropped', 0)
        run.surge_mode = ingest.get('surge_mode', False)
        session.commit()
        
        if ingest.get("inserted", 0) == 0:
            # Check if DB already has reviews for this week from a prior run
            from storage.models import Review as _Review
            _week_num = ingest.get("week_number", datetime.now().isocalendar()[1])
            _existing = session.query(_Review).filter(
                _Review.week_number == _week_num
            ).count()

            if _existing < 10:
                run.status = "no_reviews"
                session.commit()
                summary["status"] = "no_reviews"

                try:
                    from mcp.gmail_client import create_draft
                    no_review_payload = {
                        "subject": f"Groww Pulse — No New Reviews (Week {run.week_number}, {run.year})",
                        "body_html": f"""
                        <p>The Groww Pulse Agent ran on {run.run_date.strftime('%Y-%m-%d')}
                        but found <strong>no new English reviews</strong> for the past 7 days.</p>
                        <p>No action required. The scheduler will retry next Monday at 09:00 IST.</p>
                        """,
                        "body_text": "No new reviews found this week. Scheduler will retry next Monday."
                    }
                    create_draft(no_review_payload)
                    log_step("INGEST", "No reviews — notification email drafted", "WARN")
                except Exception as e:
                    log_step("INGEST", f"No reviews — email notification failed: {e}", "WARN")

                log_step("INGEST", "No reviews — skipping AI pipeline", "WARN")
                return summary
            else:
                log_step("INGEST", f"No new reviews inserted, but {_existing} existing reviews found for week {_week_num} — proceeding with AI pipeline")
        
        # Check for insufficient English reviews flag
        insufficient_flag = Path("data/processed/insufficient_english_flag.txt")
        if insufficient_flag.exists():
            insufficient_flag.unlink()  # clean up flag
            run.status = "insufficient_english"
            session.commit()
            summary["status"] = "insufficient_english"
            log_step("INGEST", "Insufficient English reviews — aborting", "WARN")
            return summary

        # STEP 2: Load reviews from database
        log_step("LOAD", "Loading reviews from database")
        from storage.models import Review
        week_num = ingest["week_number"]
        year = ingest["year"]
        
        reviews_orm = session.query(Review).filter(
            Review.week_number == week_num
        ).all()
        
        reviews = [
            {c.name: getattr(r, c.name) for c in Review.__table__.columns}
            for r in reviews_orm
        ]
        
        log_step("LOAD", f"Loaded {len(reviews)} reviews from database")
        
        # STEP 3: Embed and cluster reviews
        log_step("AI", "Embedding and clustering reviews")
        from ai.embedder import embed_reviews
        from ai.clusterer import cluster_reviews
        
        texts = [r.get("text", "") for r in reviews]
        embeddings, source = embed_reviews(reviews)
        log_step("AI", f"Generated embeddings using {source}")
        
        cluster_result = cluster_reviews(texts, embeddings, len(reviews))
        clusters = cluster_result["clusters"]
        run.algorithm_used = cluster_result["algorithm_used"]
        log_step("AI", f"Found {len(clusters)} clusters using {cluster_result['algorithm_used']}")
        
        # STEP 4: Label themes with LLM
        log_step("AI", "Labeling themes with LLM")
        from ai.llm_labeler import label_themes
        from ai.urgency_scorer import compute_trend
        from ai.quote_selector import select_weekly_quotes
        
        labeled = label_themes(clusters, reviews)
        log_step("AI", f"Labeled {len(labeled)} themes")
        
        # Compute trends for each theme
        for theme in labeled:
            theme["trend_direction"] = compute_trend(
                theme["theme_id"],
                theme.get("urgency_score", 5)
            )
        
        # Select weekly quotes
        quotes = select_weekly_quotes(labeled)
        log_step("AI", f"Selected {len([q for q in quotes if q])} quotes")
        
        # STEP 5: Build pulse note
        log_step("REPORT", "Building pulse note")
        from report.pulse_builder import build_pulse_note, render_pulse_note_markdown
        
        note = build_pulse_note(labeled, quotes, ingest)
        
        # Validate word count
        if note.word_count > 250:
            log_step("REPORT", f"Word count {note.word_count} exceeds 250 limit", "WARN")
        
        md_content = render_pulse_note_markdown(note)
        log_step("REPORT", f"Generated pulse note with {note.word_count} words")
        
        # STEP 6: Create Google Doc
        log_step("MCP", "Checking if doc already exists for this week")
        existing_url = None
        gdoc_url = "https://placeholder.gdoc.url"
        try:
            from mcp.gdocs_client import check_doc_exists, create_pulse_doc
            existing_url = check_doc_exists(note.week_number, note.year)
            if existing_url:
                gdoc_url = existing_url
                log_step("MCP", f"Reusing existing doc: {gdoc_url}")
            else:
                gdoc_url = create_pulse_doc(note, md_content)
                log_step("MCP", f"New doc created: {gdoc_url}")
            run.gdoc_url = gdoc_url
        except Exception as e:
            gdoc_url = f"https://docs.google.com/document/d/placeholder-{run_id}"
            log_step("MCP", f"GDoc failed: {e}", "WARN")
        
        # STEP 7: Create and send email
        log_step("MCP", "Creating email draft")
        draft_id = None
        try:
            from report.email_composer import compose_email
            from mcp.gmail_client import create_draft, send_draft
            
            payload = compose_email(note, gdoc_url)
            draft_id = create_draft(payload)
            log_step("MCP", f"Created email draft: {draft_id}")
            
            # Send email if auto-send is enabled
            if os.getenv("AUTO_SEND", "false").lower() == "true":
                sent = send_draft(draft_id)
                if sent:
                    run.email_sent_at = datetime.now()
                    log_step("MCP", "Email sent successfully")
                else:
                    log_step("MCP", "Email send failed", "WARN")
            else:
                log_step("MCP", "AUTO_SEND is false - email draft preserved")
                
            # Save email draft HTML to archive
            try:
                draft_dir = Path("data/archive/email_drafts")
                draft_dir.mkdir(parents=True, exist_ok=True)
                draft_path = draft_dir / f"email_draft_week_{week_num:02d}_{year}.html"
                draft_path.write_text(payload.get("body_html", ""), encoding="utf-8")
                log_step("MCP", f"Email draft HTML saved: {draft_path.name}")
            except Exception as e:
                log_step("MCP", f"Could not save email draft HTML: {e}", "WARN")
                
        except Exception as e:
            log_step("MCP", f"Email creation failed: {e}", "WARN")
        
        # STEP 8: Archive and finalize
        log_step("ARCHIVE", "Rotating archives")
        try:
            from storage.csv_archive import rotate_archive
            deleted_count = rotate_archive()
            if deleted_count > 0:
                log_step("ARCHIVE", f"Rotated {deleted_count} old archive files")
        except Exception as e:
            log_step("ARCHIVE", f"Archive rotation failed: {e}", "WARN")
        
        # Finalize run
        run.status = "completed"
        run.themes_found = len(labeled)
        run.reviews_kept = ingest.get('inserted', 0)
        session.commit()
        
        # Prepare final summary
        summary["status"] = "completed"
        summary["gdoc_url"] = gdoc_url
        summary["draft_id"] = draft_id
        summary["week_number"] = week_num
        summary["year"] = year
        summary["themes_found"] = len(labeled)
        summary["reviews_analyzed"] = len(reviews)
        
        log_step("DONE", f"Pipeline completed successfully - {len(labeled)} themes found")
        
    except Exception as e:
        # Handle pipeline failure
        tb = traceback.format_exc()
        log.error(f"Pipeline failed: {tb}")
        
        summary["status"] = "failed"
        summary["error"] = str(e)
        summary["traceback"] = tb
        
        # Update DB status
        try:
            if 'run' in locals() and 'session' in locals():
                run.status = "failed"
                run.error_message = str(e)[:500]
                session.commit()
        except Exception:
            pass
        
        # Send failure alert email
        try:
            from mcp.gmail_client import create_draft
            alert_payload = {
                "subject": f"🚨 Groww Pulse FAILED — Week {datetime.now().isocalendar()[1]}, {datetime.now().year}",
                "body_html": f"""
                <h2 style='color:#E24B4A;'>Pipeline Failed</h2>
                <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST</p>
                <p><strong>Error:</strong> {str(e)}</p>
                <pre style='background:#f5f5f5;padding:12px;font-size:12px;'>{tb[:1000]}</pre>
                <p>Please check logs and re-run manually:
                   <code>python scripts/manual_run.py full</code></p>
                """,
                "body_text": f"Pipeline failed: {str(e)}\n\nTraceback:\n{tb[:500]}"
            }
            create_draft(alert_payload)
            log.info("Failure alert email drafted")
        except Exception as alert_err:
            log.error(f"Could not send failure alert: {alert_err}")
    
    return summary


def test_pipeline():
    """Test function to verify pipeline works (without external services)."""
    print("Testing pipeline components...")
    
    try:
        # Test database initialization
        from storage.db import init_db
        init_db()
        print("✓ Database initialized")
        
        # Test vector store
        from storage.vector_store import init_collection
        init_collection()
        print("✓ Vector store initialized")
        
        # Test AI components (with dummy data)
        from ai.embedder import embed_single_text
        from ai.clusterer import load_taxonomy
        
        # Test embedding
        embedding = embed_single_text("Test review text")
        print(f"✓ Embedding test: {embedding.shape if hasattr(embedding, 'shape') else 'No embedding'}")
        
        # Test taxonomy loading
        taxonomy = load_taxonomy()
        print(f"✓ Taxonomy loaded: {len(taxonomy)} themes")
        
        # Test report building
        from report.pulse_builder import WeeklyPulseNote, ThemeSummary
        test_note = WeeklyPulseNote(
            week_number=1,
            year=2024,
            week_start_date="2024-01-01",
            week_end_date="2024-01-07",
            total_reviews_analyzed=100,
            top_themes=[
                ThemeSummary(
                    rank=1,
                    theme_id="T1",
                    label="Test Theme",
                    volume=50,
                    urgency_score=7.5,
                    sentiment_score=-0.3,
                    trend_direction="stable"
                )
            ],
            user_quotes=["Test quote"],
            action_ideas=["Test action"],
            overall_sentiment=-0.3,
            word_count=150
        )
        print(f"✓ Report building test: {test_note.week_number}")
        
        print("Pipeline component tests completed successfully")
        
    except Exception as e:
        print(f"Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_pipeline()
