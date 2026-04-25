from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Review(Base):
    __tablename__ = 'reviews'
    
    id = Column(Integer, primary_key=True)
    review_id = Column(String, unique=True, nullable=False)
    store = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    text = Column(String, nullable=False)
    date = Column(String, nullable=False)
    app_version = Column(String, nullable=True)
    language_detected = Column(String, nullable=True)
    language_confidence = Column(Float, nullable=True)
    is_duplicate = Column(Boolean, default=False)
    pii_stripped = Column(Boolean, default=False)
    suspicious_review = Column(Boolean, default=False)
    noise_flag = Column(String, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    week_number = Column(Integer, nullable=True)


class WeeklyRun(Base):
    __tablename__ = 'weekly_runs'
    
    id = Column(Integer, primary_key=True)
    run_date = Column(DateTime, default=datetime.utcnow)
    week_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    reviews_fetched = Column(Integer, default=0)
    reviews_kept = Column(Integer, default=0)
    english_count = Column(Integer, default=0)
    noise_dropped = Column(Integer, default=0)
    themes_found = Column(Integer, default=0)
    status = Column(String, default="running")
    algorithm_used = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    gdoc_url = Column(String, nullable=True)
    email_sent_at = Column(DateTime, nullable=True)
    surge_mode = Column(Boolean, default=False)
    
    # Relationships
    themes = relationship("Theme", back_populates="run")
    logs = relationship("RunLog", back_populates="run")


class Theme(Base):
    __tablename__ = 'themes'
    
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey('weekly_runs.id'), nullable=False)
    theme_id = Column(String, nullable=False)
    label = Column(String, nullable=False)
    urgency_score = Column(Float, nullable=False)
    sentiment_score = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    trend_direction = Column(String, nullable=False)
    top_quote = Column(String, nullable=False)
    keywords = Column(JSON, nullable=False)
    action_idea = Column(String, nullable=False)
    labeling_method = Column(String, default="llm")
    
    # Relationships
    run = relationship("WeeklyRun", back_populates="themes")


class RunLog(Base):
    __tablename__ = 'run_logs'
    
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey('weekly_runs.id'), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String, nullable=False)
    message = Column(String, nullable=False)
    step = Column(String, nullable=True)
    
    # Relationships
    run = relationship("WeeklyRun", back_populates="logs")
