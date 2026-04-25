import os
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from .models import Base, Review

ROOT = Path(__file__).parent.parent
DB_URL = os.getenv("DB_URL", f"sqlite:///{ROOT}/data/groww_pulse.db")

_engine = None
_SessionLocal = None


def get_engine():
    """Get SQLAlchemy engine with SQLite-specific configuration."""
    global _engine
    if _engine is None:
        if DB_URL.startswith("sqlite"):
            _engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
        else:
            _engine = create_engine(DB_URL)
    return _engine


def init_db():
    """Initialize database by creating directories and tables."""
    # Create data directory if it doesn't exist
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    
    # Create all tables
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def get_session():
    """Get a new database session."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal()


@contextmanager
def session_scope():
    """Context manager for database sessions with automatic commit/rollback."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def bulk_insert_reviews(reviews: list[dict]) -> int:
    """Bulk insert reviews with INSERT OR IGNORE for SQLite."""
    if not reviews:
        return 0
    
    engine = get_engine()
    
    # For SQLite, use INSERT OR IGNORE to handle duplicates
    if DB_URL.startswith("sqlite"):
        # Convert to list of tuples for raw SQL
        review_data = []
        for review in reviews:
            review_data.append((
                review.get('review_id'),
                review.get('store'),
                review.get('rating'),
                review.get('title'),
                review.get('text'),
                review.get('date'),
                review.get('app_version'),
                review.get('language_detected'),
                review.get('language_confidence'),
                review.get('is_duplicate', False),
                review.get('pii_stripped', False),
                review.get('suspicious_review', False),
                review.get('noise_flag'),
                review.get('week_number')
            ))
        
        # Use raw SQL with INSERT OR IGNORE
        from sqlalchemy import text
        with engine.connect() as conn:
            stmt = text("""
            INSERT OR IGNORE INTO reviews (
                review_id, store, rating, title, text, date, app_version,
                language_detected, language_confidence, is_duplicate,
                pii_stripped, suspicious_review, noise_flag, week_number
            ) VALUES (:review_id, :store, :rating, :title, :text, :date, :app_version,
                      :language_detected, :language_confidence, :is_duplicate,
                      :pii_stripped, :suspicious_review, :noise_flag, :week_number)
            """)
            conn.execute(stmt, [
                {
                    'review_id': r[0], 'store': r[1], 'rating': r[2],
                    'title': r[3], 'text': r[4], 'date': r[5],
                    'app_version': r[6], 'language_detected': r[7],
                    'language_confidence': r[8], 'is_duplicate': r[9],
                    'pii_stripped': r[10], 'suspicious_review': r[11],
                    'noise_flag': r[12], 'week_number': r[13]
                }
                for r in review_data
            ])
            conn.commit()
            return len(review_data)
    else:
        # For other databases, use SQLAlchemy's bulk operations with conflict handling
        with session_scope() as session:
            try:
                session.bulk_insert_mappings(Review, reviews)
                return len(reviews)
            except SQLAlchemyError as e:
                # If there's a conflict, try individual inserts
                inserted_count = 0
                for review in reviews:
                    try:
                        db_review = Review(**review)
                        session.add(db_review)
                        session.flush()
                        inserted_count += 1
                    except SQLAlchemyError:
                        session.rollback()
                        continue
                return inserted_count
