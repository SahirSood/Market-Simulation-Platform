from typing import Dict, List, Optional, Sequence
from datetime import datetime
import json
import math
from sqlalchemy import create_engine, func, inspect, text
from sqlalchemy.orm import sessionmaker
from .models import Base, Document, Chunk, RagJobStatus
from hashlib import sha256


class RagRepository:
    def __init__(self, engine_url: str = "sqlite:///:memory:"):
        self.engine_url = engine_url
        self.engine = create_engine(engine_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        Base.metadata.create_all(self.engine)
        self._ensure_optional_columns()

    def _ensure_optional_columns(self) -> None:
        """Add lightweight forward-compatible columns when create_all cannot."""
        inspector = inspect(self.engine)
        if "rag_documents" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("rag_documents")}
        if "raw_content" not in columns:
            with self.engine.begin() as conn:
                conn.execute(text("ALTER TABLE rag_documents ADD COLUMN raw_content TEXT"))

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
        raw_content: Optional[str] = None,
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
                raw_content=raw_content,
                content_hash=content_hash,
            )
            session.add(doc)
            session.flush()  # assign id

            for c in chunks:
                chunk = Chunk(
                    document_id=doc.id,
                    content=c.get("content"),
                    start_pos=c.get("start_pos"),
                    end_pos=c.get("end_pos"),
                    embedding=c.get("embedding"),
                )
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

    def start_job(
        self,
        job_type: str,
        metadata: Optional[dict] = None,
        max_attempts: int = 1,
    ) -> int:
        with self.SessionLocal() as session:
            job = RagJobStatus(
                job_type=str(job_type),
                status="running",
                attempts=0,
                max_attempts=max(1, int(max_attempts)),
                metadata_json=metadata or {},
            )
            session.add(job)
            session.commit()
            return int(job.id)

    def update_job_status(
        self,
        job_id: int,
        status: str,
        attempts: Optional[int] = None,
        error: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        with self.SessionLocal() as session:
            job = session.get(RagJobStatus, int(job_id))
            if job is None:
                return
            job.status = str(status)
            if attempts is not None:
                job.attempts = int(attempts)
            if error is not None:
                job.last_error = str(error)[:2000]
            if metadata:
                merged = dict(job.metadata_json or {})
                merged.update(metadata)
                job.metadata_json = merged
            if status in {"succeeded", "failed", "skipped"}:
                job.finished_at = datetime.utcnow()
            session.commit()

    def list_job_status(
        self,
        job_type: Optional[str] = None,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> list[dict]:
        with self.SessionLocal() as session:
            query = session.query(RagJobStatus)
            if job_type:
                query = query.filter(RagJobStatus.job_type == job_type)
            if status:
                query = query.filter(RagJobStatus.status == status)
            rows = (
                query.order_by(RagJobStatus.started_at.desc(), RagJobStatus.id.desc())
                .limit(limit)
                .all()
            )
            return [self._job_status_dict(row) for row in rows]

    def summarize_job_status(self) -> dict:
        with self.SessionLocal() as session:
            rows = (
                session.query(
                    RagJobStatus.job_type,
                    RagJobStatus.status,
                    func.count(RagJobStatus.id),
                    func.max(RagJobStatus.started_at),
                    func.max(RagJobStatus.finished_at),
                )
                .group_by(RagJobStatus.job_type, RagJobStatus.status)
                .all()
            )

        by_type: dict[str, dict[str, int]] = {}
        by_status: dict[str, int] = {}
        latest_started_at = None
        latest_finished_at = None
        total = 0
        for job_type, status, count, started_at, finished_at in rows:
            count = int(count or 0)
            total += count
            by_type.setdefault(job_type, {})[status] = count
            by_status[status] = by_status.get(status, 0) + count
            latest_started_at = max(
                [value for value in (latest_started_at, started_at) if value is not None],
                default=None,
            )
            latest_finished_at = max(
                [value for value in (latest_finished_at, finished_at) if value is not None],
                default=None,
            )
        return {
            "total": total,
            "by_type": by_type,
            "by_status": by_status,
            "latest_started_at": latest_started_at,
            "latest_finished_at": latest_finished_at,
        }

    def requeue_jobs(
        self,
        job_type: Optional[str] = None,
        statuses: Sequence[str] = ("failed",),
        limit: int = 20,
    ) -> list[dict]:
        requested_statuses = [str(status) for status in statuses if str(status).strip()]
        if not requested_statuses:
            return []

        with self.SessionLocal() as session:
            query = session.query(RagJobStatus).filter(RagJobStatus.status.in_(requested_statuses))
            if job_type:
                query = query.filter(RagJobStatus.job_type == job_type)
            rows = (
                query.order_by(RagJobStatus.finished_at.desc(), RagJobStatus.id.desc())
                .limit(max(1, int(limit)))
                .all()
            )
            requeued_at = datetime.utcnow().isoformat() + "Z"
            for row in rows:
                metadata = dict(row.metadata_json or {})
                metadata["requeued_at"] = requeued_at
                metadata["previous_status"] = row.status
                row.status = "queued"
                row.finished_at = None
                row.last_error = None
                row.metadata_json = metadata
            session.commit()
            return [self._job_status_dict(row) for row in rows]

    @staticmethod
    def _job_status_dict(row: RagJobStatus) -> dict:
        return {
            "id": row.id,
            "job_type": row.job_type,
            "status": row.status,
            "attempts": row.attempts,
            "max_attempts": row.max_attempts,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "last_error": row.last_error,
            "metadata": row.metadata_json or {},
        }

    def get_document_by_accession(self, accession_no: str) -> Optional[Document]:
        with self.SessionLocal() as session:
            return session.query(Document).filter(Document.accession_no == accession_no).first()

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

    def get_chunks_by_ids(self, chunk_ids: Sequence[int]) -> List[dict]:
        """Return RAG chunks with document metadata, preserving requested order."""
        requested_ids = []
        for chunk_id in chunk_ids:
            try:
                requested_ids.append(int(chunk_id))
            except (TypeError, ValueError):
                continue
        if not requested_ids:
            return []

        with self.SessionLocal() as session:
            rows = (
                session.query(Chunk)
                .join(Document)
                .filter(Chunk.id.in_(requested_ids))
                .all()
            )
            by_id = {
                chunk.id: {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document.id,
                    "ticker": chunk.document.ticker,
                    "title": chunk.document.title,
                    "source_url": chunk.document.source_url,
                    "source_type": chunk.document.source_type,
                    "source_name": chunk.document.source_name,
                    "form_type": chunk.document.form_type,
                    "cik": chunk.document.cik,
                    "accession_no": chunk.document.accession_no,
                    "published_at": chunk.document.published_at,
                    "content": chunk.content,
                    "start_pos": chunk.start_pos,
                    "end_pos": chunk.end_pos,
                }
                for chunk in rows
            }
            return [by_id[chunk_id] for chunk_id in requested_ids if chunk_id in by_id]

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

    def set_chunk_embeddings(self, embeddings_by_chunk_id: Dict[int, Sequence[float]]) -> int:
        if not embeddings_by_chunk_id:
            return 0
        updated = 0
        with self.SessionLocal() as session:
            chunks = (
                session.query(Chunk)
                .filter(Chunk.id.in_(list(embeddings_by_chunk_id.keys())))
                .all()
            )
            for chunk in chunks:
                embedding = embeddings_by_chunk_id.get(chunk.id)
                if embedding is None:
                    continue
                chunk.embedding = json.dumps(list(embedding))
                updated += 1
            session.commit()
        return updated

    def embed_missing_chunks(self, embedding_service, limit: int = 1000, batch_size: int = 64) -> int:
        if embedding_service is None or not embedding_service.is_available():
            return 0
        chunks = self.get_chunks_without_embeddings(limit=limit)
        updated = 0
        for start in range(0, len(chunks), max(1, batch_size)):
            batch = chunks[start:start + max(1, batch_size)]
            texts = [chunk.content for chunk in batch]
            embed_texts = getattr(embedding_service, "embed_texts", None)
            if callable(embed_texts):
                embeddings = embed_texts(texts)
            else:
                embeddings = [embedding_service.embed_text(text) for text in texts]
            updated += self.set_chunk_embeddings(
                {chunk.id: embedding for chunk, embedding in zip(batch, embeddings)}
            )
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
                scored = self._rank_vector_rows(query_embedding, rows, top_k=top_k)
                if scored:
                    return [self._evidence_row(ch, score) for score, ch in scored[:top_k]]

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
            if fallback:
                return [self._evidence_row(ch, score) for score, ch in fallback[:top_k]]

            # Last-resort context for live demos: if the query is too far from
            # filing text, still provide recent real filing chunks instead of an
            # empty evidence section. Low score keeps trade guardrails honest.
            rows.sort(
                key=lambda ch: (
                    ch.document.published_at or datetime.min,
                    -int(ch.id or 0),
                ),
                reverse=True,
            )
            return [self._evidence_row(ch, 0.01) for ch in rows[:top_k]]

    @staticmethod
    def _evidence_row(ch: Chunk, score: float) -> dict:
        return {
            "chunk_id": ch.id,
            "document_id": ch.document.id,
            "ticker": ch.document.ticker,
            "title": ch.document.title,
            "source_url": ch.document.source_url,
            "source_type": ch.document.source_type,
            "source_name": ch.document.source_name,
            "form_type": ch.document.form_type,
            "cik": ch.document.cik,
            "accession_no": ch.document.accession_no,
            "published_at": ch.document.published_at,
            "content": ch.content,
            "start_pos": ch.start_pos,
            "end_pos": ch.end_pos,
            "score": score,
        }

    def _rank_vector_rows(
        self,
        query_embedding: List[float],
        rows: Sequence[Chunk],
        top_k: int,
    ) -> List[tuple[float, Chunk]]:
        parsed: List[tuple[Chunk, List[float]]] = []
        for ch in rows:
            if not ch.embedding:
                continue
            try:
                emb = json.loads(ch.embedding)
            except json.JSONDecodeError:
                continue
            parsed.append((ch, emb))

        if not parsed:
            return []

        faiss_scored = self._rank_with_faiss(query_embedding, parsed, top_k=top_k)
        if faiss_scored is not None:
            return faiss_scored

        scored = []
        for ch, emb in parsed:
            score = self._cosine_similarity(query_embedding, emb)
            if score < -0.5:
                continue
            scored.append((score, ch))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _rank_with_faiss(
        query_embedding: List[float],
        parsed_rows: Sequence[tuple[Chunk, List[float]]],
        top_k: int,
    ) -> Optional[List[tuple[float, Chunk]]]:
        try:
            import faiss  # type: ignore
            import numpy as np  # type: ignore
        except Exception:
            return None

        vectors = []
        chunks = []
        dim = len(query_embedding)
        if dim == 0:
            return []
        for chunk, emb in parsed_rows:
            if len(emb) != dim:
                continue
            vectors.append(emb)
            chunks.append(chunk)
        if not vectors:
            return []

        matrix = np.array(vectors, dtype="float32")
        query = np.array([query_embedding], dtype="float32")
        faiss.normalize_L2(matrix)
        faiss.normalize_L2(query)
        index = faiss.IndexFlatIP(dim)
        index.add(matrix)
        scores, indexes = index.search(query, min(top_k, len(chunks)))
        ranked: List[tuple[float, Chunk]] = []
        for score, idx in zip(scores[0], indexes[0]):
            if idx < 0:
                continue
            ranked.append((float(score), chunks[int(idx)]))
        return ranked


def create_tables(repo: RagRepository):
    repo.create_tables()
