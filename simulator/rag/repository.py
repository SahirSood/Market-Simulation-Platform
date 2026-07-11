from typing import List, Optional
from datetime import datetime
import json
import math
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, Document, Chunk
from hashlib import sha256


class RagRepository:
    def __init__(self, engine_url: str = "sqlite:///:memory:"):
        self.engine_url = engine_url
        self.engine = create_engine(engine_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def add_document_with_chunks(
        self,
        ticker: Optional[str],
        title: Optional[str],
        source_url: Optional[str],
        content: str,
        chunks: List[dict],
        source_type: Optional[str] = None,
        source_name: Optional[str] = None,
        form_type: Optional[str] = None,
        cik: Optional[str] = None,
        accession_no: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ):
        normalized_cik = self._normalize_cik(cik)
        content_hash = sha256(content.encode("utf-8")).hexdigest()
        with self.SessionLocal() as session:
            # deduplicate document by hash
            existing = session.query(Document).filter_by(content_hash=content_hash).first()
            if existing:
                return existing

            doc = Document(
                ticker=ticker,
                title=title,
                source_url=source_url,
                source_type=source_type,
                source_name=source_name,
                form_type=form_type,
                cik=normalized_cik,
                accession_no=accession_no,
                published_at=published_at,
                content=content,
                content_hash=content_hash,
            )
            session.add(doc)
            session.flush()  # assign id

            for c in chunks:
                chunk = Chunk(document_id=doc.id, content=c.get("content"), start_pos=c.get("start_pos"), end_pos=c.get("end_pos"), embedding=c.get("embedding"))
                session.add(chunk)

            session.commit()
            session.refresh(doc)
            return doc

    def count_documents(self) -> int:
        with self.SessionLocal() as session:
            return session.query(Document).count()

    def count_chunks(self) -> int:
        with self.SessionLocal() as session:
            return session.query(Chunk).count()

    @staticmethod
    def _normalize_cik(cik: Optional[str]) -> Optional[str]:
        if cik is None:
            return None
        cleaned = str(cik).strip()
        if not cleaned:
            return None
        return cleaned.zfill(10)

    def get_latest_accession_for_cik(self, cik: str) -> Optional[str]:
        normalized_cik = self._normalize_cik(cik)
        if normalized_cik is None:
            return None
        with self.SessionLocal() as session:
            doc = (
                session.query(Document)
                .filter(
                    Document.cik == normalized_cik,
                    Document.accession_no.isnot(None),
                )
                .order_by(
                    Document.published_at.is_(None),
                    Document.published_at.desc(),
                    Document.id.desc(),
                )
                .first()
            )
            if not doc:
                return None
            return doc.accession_no

    def get_chunks_by_ticker(self, ticker: str, limit: int = 10) -> List[Chunk]:
        with self.SessionLocal() as session:
            q = session.query(Chunk).join(Document).filter(Document.ticker == ticker).order_by(Chunk.id.desc()).limit(limit)
            return q.all()

    def get_chunks_without_embeddings(self, limit: int = 1000) -> List[Chunk]:
        with self.SessionLocal() as session:
            return session.query(Chunk).filter((Chunk.embedding == None) | (Chunk.embedding == "")).limit(limit).all()

    def set_chunk_embedding(self, chunk_id: int, embedding: List[float]) -> None:
        with self.SessionLocal() as session:
            chunk = session.query(Chunk).filter(Chunk.id == chunk_id).first()
            if not chunk:
                return
            chunk.embedding = json.dumps(embedding)
            session.commit()

    def embed_missing_chunks(self, embedding_service, limit: int = 1000) -> int:
        if embedding_service is None or not embedding_service.is_available():
            return 0
        updated = 0
        for chunk in self.get_chunks_without_embeddings(limit=limit):
            emb = embedding_service.embed_text(chunk.content)
            self.set_chunk_embedding(chunk.id, emb)
            updated += 1
        return updated

    def search_chunks(self, query_text: str, limit: int = 10) -> List[Chunk]:
        # naive keyword fallback search using SQL LIKE
        with self.SessionLocal() as session:
            pattern = f"%{query_text}%"
            q = session.query(Chunk).filter(Chunk.content.ilike(pattern)).limit(limit)
            return q.all()

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return -1.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return -1.0
        return dot / (na * nb)

    def retrieve_evidence(
        self,
        ticker: Optional[str],
        query_text: str,
        top_k: int = 5,
        embedding_service=None,
        as_of_date: Optional[datetime] = None,
    ) -> List[dict]:
        """
        Returns ranked evidence rows with keyword fallback when embeddings are unavailable.
        """
        with self.SessionLocal() as session:
            q = session.query(Chunk).join(Document)
            if ticker:
                q = q.filter(Document.ticker == ticker)
            if as_of_date is not None:
                q = q.filter((Document.published_at == None) | (Document.published_at <= as_of_date))
            rows = q.all()

            # Vector retrieval path
            if embedding_service is not None and embedding_service.is_available():
                query_embedding = embedding_service.embed_text(query_text)
                scored = []
                for ch in rows:
                    if not ch.embedding:
                        continue
                    try:
                        emb = json.loads(ch.embedding)
                    except json.JSONDecodeError:
                        continue
                    score = self._cosine_similarity(query_embedding, emb)
                    if score < -0.5:
                        continue
                    scored.append((score, ch))

                scored.sort(key=lambda x: x[0], reverse=True)
                if scored:
                    return [
                        {
                            "chunk_id": ch.id,
                            "document_id": ch.document.id,
                            "ticker": ch.document.ticker,
                            "source_url": ch.document.source_url,
                            "published_at": ch.document.published_at,
                            "content": ch.content,
                            "start_pos": ch.start_pos,
                            "end_pos": ch.end_pos,
                            "score": score,
                        }
                        for score, ch in scored[:top_k]
                    ]

            # Keyword fallback path
            query_tokens = [t for t in query_text.lower().split() if t]
            fallback = []
            for ch in rows:
                text = (ch.content or "").lower()
                if not text:
                    continue
                token_hits = sum(text.count(tok) for tok in query_tokens)
                if token_hits > 0:
                    fallback.append((float(token_hits), ch))

            fallback.sort(key=lambda x: x[0], reverse=True)
            return [
                {
                    "chunk_id": ch.id,
                    "document_id": ch.document.id,
                    "ticker": ch.document.ticker,
                    "source_url": ch.document.source_url,
                    "published_at": ch.document.published_at,
                    "content": ch.content,
                    "start_pos": ch.start_pos,
                    "end_pos": ch.end_pos,
                    "score": score,
                }
                for score, ch in fallback[:top_k]
            ]


def create_tables(repo: RagRepository):
    repo.create_tables()
