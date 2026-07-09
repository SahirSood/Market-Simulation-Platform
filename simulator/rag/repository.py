from typing import List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from .models import Base, Document, Chunk
from hashlib import sha256


class RagRepository:
    def __init__(self, engine_url: str = "sqlite:///:memory:"):
        self.engine_url = engine_url
        self.engine = create_engine(engine_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def add_document_with_chunks(self, ticker: Optional[str], title: Optional[str], source_url: Optional[str], content: str, chunks: List[dict]):
        content_hash = sha256(content.encode("utf-8")).hexdigest()
        with self.SessionLocal() as session:
            # deduplicate document by hash
            existing = session.query(Document).filter_by(content_hash=content_hash).first()
            if existing:
                return existing

            doc = Document(ticker=ticker, title=title, source_url=source_url, content=content, content_hash=content_hash)
            session.add(doc)
            session.flush()  # assign id

            for c in chunks:
                chunk = Chunk(document_id=doc.id, content=c.get("content"), start_pos=c.get("start_pos"), end_pos=c.get("end_pos"), embedding=c.get("embedding"))
                session.add(chunk)

            session.commit()
            session.refresh(doc)
            return doc

    def get_chunks_by_ticker(self, ticker: str, limit: int = 10) -> List[Chunk]:
        with self.SessionLocal() as session:
            q = session.query(Chunk).join(Document).filter(Document.ticker == ticker).order_by(Chunk.id.desc()).limit(limit)
            return q.all()

    def search_chunks(self, query_text: str, limit: int = 10) -> List[Chunk]:
        # naive keyword fallback search using SQL LIKE
        with self.SessionLocal() as session:
            pattern = f"%{query_text}%"
            q = session.query(Chunk).filter(Chunk.content.ilike(pattern)).limit(limit)
            return q.all()
