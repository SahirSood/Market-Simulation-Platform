from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Document(Base):
    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(32), index=True, nullable=True)
    title = Column(String(512), nullable=True)
    source_url = Column(String(1024), nullable=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "rag_chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    start_pos = Column(Integer, nullable=True)
    end_pos = Column(Integer, nullable=True)
    embedding = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")


Index("ix_rag_chunks_content", Chunk.content)
