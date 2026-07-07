import os
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "twin.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Memory(Base):
    __tablename__ = "memories"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    type = Column(String)
    content = Column(Text)
    importance = Column(Float, default=1.0)
    confidence = Column(Float, default=1.0)
    emotional_weight = Column(Float, default=0.0)
    access_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    embedding_id = Column(String)


class Profile(Base):
    __tablename__ = "profile"
    key = Column(String, primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, default="New chat")
    archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String)
    due_at = Column(DateTime)
    done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OnboardingState(Base):
    __tablename__ = "onboarding_state"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    current_step = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Base.metadata.create_all(engine)


def _ensure_sqlite_columns() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(memories)"))
        }
        if "emotional_weight" not in columns:
            conn.execute(text("ALTER TABLE memories ADD COLUMN emotional_weight FLOAT DEFAULT 0.0"))


_ensure_sqlite_columns()

def get_db():
    with SessionLocal() as session:
        yield session
