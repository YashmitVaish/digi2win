from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Session
from datetime import datetime
import uuid

engine = create_engine("sqlite:///twin.db")

class Base(DeclarativeBase): 
    pass

class Memory(Base):
    __tablename__ = "memories"
    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    type          = Column(String)   # fact | preference | event | goal | style
    content       = Column(Text)
    importance    = Column(Float, default=1.0)
    confidence    = Column(Float, default=1.0)
    access_count  = Column(Integer, default=0)
    created_at    = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    embedding_id  = Column(String)

class Profile(Base):
    __tablename__ = "profile"
    key        = Column(String, primary_key=True)
    value      = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Conversation(Base):
    __tablename__ = "conversations"
    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    role       = Column(String)
    content    = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

def get_db():
    with Session(engine) as session:
        yield session