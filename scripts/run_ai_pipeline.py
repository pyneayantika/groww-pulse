import sys, os
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from datetime import datetime

print("=" * 55)
print("  AI PIPELINE — Using existing DB reviews")
print("=" * 55)

# Load reviews from DB
from storage.db import get_session
from storage.models import Review, WeeklyRun

session = get_session()
week_num = datetime.now().isocalendar()[1]
year = datetime.now().year

reviews_orm = session.query(Review).all()
reviews = [
    {c.name: getattr(r, c.name) for c in Review.__table__.columns}
    for r in reviews_orm
]
session.close()
print(f"\n[1] Loaded {len(reviews)} reviews from database")

if len(reviews) == 0:
    print("  ERROR: No reviews in database. Run fix_and_run.py first.")
    sys.exit(1)

# Embed
print("\n[2] Embedding reviews...")
from ai.embedder import embed_reviews
embeddings, source = embed_reviews(reviews)
print(f"  Embeddings done: {embeddings.shape} using {source}")

# Cluster
print("\n[3] Clustering into themes...")
from ai.clusterer import cluster_reviews
texts = [r.get('text','') for r in reviews]
result = cluster_reviews(texts, embeddings, len(reviews))
clusters = result['clusters']
print(f"  Clusters: {len(clusters)} themes via {result['algorithm_used']}")
for c in clusters:
    print(f"    {c['theme_id']} — {c['label']} ({c['size']} reviews)")

# Label
print("\n[4] Labeling themes with Groq Llama 3...")
from ai.llm_labeler import label_themes
from ai.urgency_scorer import compute_trend
from ai.quote_selector import select_weekly_quotes
labeled = label_themes(clusters, reviews)
for t in labeled:
    t['trend_direction'] = compute_trend(
        t['theme_id'], t.get('urgency_score', 5)
    )
    print(f"  {t['theme_id']}: urgency={t.get('urgency_score')}, sentiment={t.get('sentiment_score')}")
quotes = select_weekly_quotes(labeled)
print(f"  Quotes selected: {len([q for q in quotes if q])}")

# Build pulse note
print("\n[5] Building weekly pulse note...")
from report.pulse_builder import build_pulse_note, render_pulse_note_markdown
ingestion_summary = {
    'inserted': len(reviews),
    'week_number': week_num,
    'year': year
}
note = build_pulse_note(labeled, quotes, ingestion_summary)
md = render_pulse_note_markdown(note)
print(f"  Word count: {note.word_count}")
print(f"  Top themes: {[t.label for t in note.top_themes]}")

# Save report
print("\n[6] Saving reports...")
archive = Path("data/archive")
archive.mkdir(parents=True, exist_ok=True)
md_path = archive / f"groww_week_{week_num:02d}_{year}_pulse.md"
md_path.write_text(md, encoding='utf-8')
print(f"  Markdown saved: {md_path}")

# Save HTML
from report.weekly_report_generator import build_weekly_report, render_weekly_html, save_weekly_reports
try:
    from report.email_composer import compose_email
    email = compose_email(note, "https://placeholder.url")
    html_path = archive / f"groww_week_{week_num:02d}_{year}_pulse.html"
    html_path.write_text(email['body_html'], encoding='utf-8')
    print(f"  HTML saved: {html_path}")
except Exception as e:
    print(f"  HTML warning: {e}")

# Save to DB
from storage.db import session_scope
from storage.models import Theme
with session_scope() as s:
    run = WeeklyRun(
        week_number=week_num, year=year,
        reviews_fetched=len(reviews), reviews_kept=len(reviews),
        themes_found=len(labeled), status='completed'
    )
    s.add(run)
    s.flush()
    for t in labeled:
        theme = Theme(
            run_id=run.id, theme_id=t.get('theme_id',''),
            label=t.get('theme_label', t.get('label','')),
            urgency_score=float(t.get('urgency_score',5)),
            sentiment_score=float(t.get('sentiment_score',0)),
            volume=int(t.get('volume',0)),
            trend_direction=t.get('trend_direction','stable'),
            top_quote=t.get('top_quote',''),
            keywords=t.get('top_keywords',[]),
            action_idea=t.get('action_idea',''),
            labeling_method=t.get('labeling_method','llm')
        )
        s.add(theme)

print("\n" + "=" * 55)
print("  WEEKLY PULSE NOTE PREVIEW")
print("=" * 55)
print(md)
print("\n" + "=" * 55)
print("  AI PIPELINE COMPLETE")
print(f"  Report: {md_path}")
print("=" * 55)
