import sys
import os
from pathlib import Path
import click

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from scheduler.orchestrator import run_weekly_pipeline


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def cli(verbose):
    """Groww Pulse - Manual CLI for running pipeline components."""
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)


@cli.command()
@click.option('--force', is_flag=True, help='Force run even if no new reviews')
def full(force):
    """Run complete pipeline end-to-end."""
    click.echo("🚀 Starting complete Groww Pulse pipeline...")
    
    try:
        result = run_weekly_pipeline()
        
        status = result.get("status", "unknown")
        week_num = result.get("week_number", "unknown")
        themes = result.get("themes_found", 0)
        reviews = result.get("reviews_analyzed", 0)
        
        if status == "completed":
            click.echo(f"✅ Pipeline completed successfully!")
            click.echo(f"   Week: {week_num}")
            click.echo(f"   Themes found: {themes}")
            click.echo(f"   Reviews analyzed: {reviews}")
            
            if "gdoc_url" in result:
                click.echo(f"   Google Doc: {result['gdoc_url']}")
            
            if "draft_id" in result:
                click.echo(f"   Email Draft ID: {result['draft_id']}")
                
        elif status == "no_reviews":
            click.echo("⚠️  No new reviews found - pipeline skipped")
            
        else:
            click.echo(f"❌ Pipeline failed with status: {status}")
            if "error" in result:
                click.echo(f"   Error: {result['error']}")
                
    except Exception as e:
        click.echo(f"❌ Pipeline execution failed: {e}")
        raise click.Abort()


@cli.command()
@click.option('--days', default=7, help='Number of days to look back for reviews')
@click.option('--csv', type=click.Path(exists=True), help='CSV file to load reviews from')
def ingest(days, csv):
    """Ingest reviews from app stores and/or CSV."""
    click.echo(f"📥 Starting review ingestion (last {days} days)...")
    
    try:
        from ingestion import run_ingestion
        
        if csv:
            click.echo(f"📁 Loading reviews from CSV: {csv}")
            result = run_ingestion(days_back=days, csv_fallback_path=csv)
        else:
            result = run_ingestion(days_back=days)
        
        click.echo(f"✅ Ingestion completed!")
        click.echo(f"   Fetched: {result.get('fetched', 0)}")
        click.echo(f"   Deduped: {result.get('deduped', 0)}")
        click.echo(f"   English: {result.get('english', 0)}")
        click.echo(f"   Inserted: {result.get('inserted', 0)}")
        click.echo(f"   Week: {result.get('week_number', 'unknown')}")
        
        if result.get('surge_mode'):
            click.echo("   ⚡ Surge mode was activated")
            
    except Exception as e:
        click.echo(f"❌ Ingestion failed: {e}")
        raise click.Abort()


@cli.command()
def setup():
    """Initialize database and ChromaDB."""
    click.echo("🔧 Setting up Groww Pulse storage...")
    
    try:
        from storage.db import init_db
        from storage.vector_store import init_collection
        
        click.echo("   Initializing database...")
        init_db()
        
        click.echo("   Initializing vector store...")
        init_collection()
        
        click.echo("✅ Setup complete!")
        
    except Exception as e:
        click.echo(f"❌ Setup failed: {e}")
        raise click.Abort()


@cli.command()
@click.option("--week", default=None, type=int,
              help="ISO week number (default: latest completed run)")
@click.option("--year", default=None, type=int,
              help="Year (default: current year)")
@click.option("--format", "fmt", default="both",
              type=click.Choice(["md", "html", "both"]),
              help="Output format")
def weekly_report(week, year, fmt):
    """Generate weekly pulse report from database."""
    from report.weekly_report_generator import (
        build_weekly_report, render_weekly_markdown,
        render_weekly_html, save_weekly_reports
    )

    click.echo("Building weekly report...")
    result = save_weekly_reports(week_number=week, year=year)

    if "error" in result:
        click.echo(f"Error: {result['error']}", err=True)
        return

    click.echo(f"Week     : {result['week_number']}, {result['year']}")
    click.echo(f"Words    : {result['word_count']}")
    click.echo(f"Markdown : {result['md_path']}")
    click.echo(f"HTML     : {result['html_path']}")
    click.echo("Weekly report generated successfully.")


@cli.command()
@click.option('--text', default="This is a test review for Groww app.", help='Text to embed')
def embed(text):
    """Test embedding functionality."""
    click.echo("🧠 Testing text embedding...")
    
    try:
        from ai.embedder import embed_single_text
        
        embedding = embed_single_text(text)
        
        if hasattr(embedding, 'shape'):
            click.echo(f"✅ Embedding generated successfully!")
            click.echo(f"   Shape: {embedding.shape}")
            click.echo(f"   First 5 values: {embedding[:5]}")
        else:
            click.echo("❌ No embedding generated")
            
    except Exception as e:
        click.echo(f"❌ Embedding test failed: {e}")
        raise click.Abort()


@cli.command()
@click.option('--count', default=10, help='Number of recent reviews to test')
def cluster(count):
    """Test clustering with recent reviews."""
    click.echo(f"🔗 Testing clustering with {count} recent reviews...")
    
    try:
        from storage.db import get_session
        from storage.models import Review
        from ai.embedder import embed_reviews
        from ai.clusterer import cluster_reviews
        
        session = get_session()
        reviews = session.query(Review).order_by(Review.id.desc()).limit(count).all()
        
        if not reviews:
            click.echo("⚠️  No reviews found in database")
            return
        
        # Convert to dictionaries
        review_dicts = [
            {c.name: getattr(r, c.name) for c in Review.__table__.columns}
            for r in reviews
        ]
        
        click.echo(f"   Found {len(review_dicts)} reviews")
        
        # Embed
        texts = [r.get("text", "") for r in review_dicts]
        embeddings, source = embed_reviews(review_dicts)
        click.echo(f"   Embedded using: {source}")
        
        # Cluster
        result = cluster_reviews(texts, embeddings, len(review_dicts))
        clusters = result.get("clusters", [])
        algorithm = result.get("algorithm_used", "unknown")
        
        click.echo(f"✅ Clustering completed!")
        click.echo(f"   Algorithm: {algorithm}")
        click.echo(f"   Clusters found: {len(clusters)}")
        
        for i, cluster in enumerate(clusters[:3]):
            click.echo(f"   Cluster {i+1}: {cluster.get('label', 'Unknown')} (size: {cluster.get('size', 0)})")
            
    except Exception as e:
        click.echo(f"❌ Clustering test failed: {e}")
        raise click.Abort()


@cli.command()
def test():
    """Run all component tests."""
    click.echo("🧪 Running component tests...")
    
    tests = [
        ("Database", test_database),
        ("Vector Store", test_vector_store),
        ("Embeddings", test_embeddings),
        ("Clustering", test_clustering),
        ("Reports", test_reports)
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        click.echo(f"\n   Testing {name}...")
        try:
            test_func()
            click.echo(f"   ✅ {name} test passed")
            passed += 1
        except Exception as e:
            click.echo(f"   ❌ {name} test failed: {e}")
    
    click.echo(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        click.echo("🎉 All tests passed!")
    else:
        click.echo("⚠️  Some tests failed - check configuration")


def test_database():
    """Test database connection."""
    from storage.db import init_db, get_session
    init_db()
    session = get_session()
    session.close()


def test_vector_store():
    """Test vector store."""
    from storage.vector_store import init_collection, get_collection_stats
    init_collection()
    stats = get_collection_stats()
    assert isinstance(stats, dict)


def test_embeddings():
    """Test embedding functionality."""
    from ai.embedder import embed_single_text
    embedding = embed_single_text("Test text")
    assert hasattr(embedding, 'shape')


def test_clustering():
    """Test clustering with dummy data."""
    from ai.clusterer import load_taxonomy
    taxonomy = load_taxonomy()
    assert isinstance(taxonomy, list)
    assert len(taxonomy) > 0


def test_reports():
    """Test report building."""
    from report.pulse_builder import WeeklyPulseNote, ThemeSummary
    note = WeeklyPulseNote(
        week_number=1,
        year=2024,
        week_start_date="2024-01-01",
        week_end_date="2024-01-07",
        total_reviews_analyzed=100,
        top_themes=[
            ThemeSummary(
                rank=1,
                theme_id="T1",
                label="Test",
                volume=50,
                urgency_score=7.0,
                sentiment_score=0.0,
                trend_direction="stable"
            )
        ]
    )
    assert note.week_number == 1


if __name__ == "__main__":
    cli()
