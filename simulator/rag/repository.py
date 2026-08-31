from typing import Dict, List, Optional, Sequence
from datetime import datetime
from collections import defaultdict
import json
import math
from sqlalchemy import case, create_engine, func, inspect, or_, text
from sqlalchemy.orm import sessionmaker
from .models import Base, Document, Chunk, RagJobStatus
from hashlib import sha256


class RagRepository:
    def __init__(self, engine_url: str = "sqlite:///:memory:"):
        self.engine_url = engine_url
        engine_options = {} if engine_url.startswith("sqlite") else {
            "pool_size": 5,
            "max_overflow": 2,
            "pool_pre_ping": True,
            "pool_recycle": 1800,
        }
        self.engine = create_engine(engine_url, echo=False, **engine_options)
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
        normalized_ticker = str(ticker).upper().strip() if ticker else None
        normalized_accession = self._normalize_accession(accession_no)
        normalized_source_url = self._normalize_source_url(source_url)
        content_hash = sha256(content.encode("utf-8")).hexdigest()
        with self.SessionLocal() as session:
            if normalized_accession:
                existing = (
                    session.query(Document)
                    .filter(func.lower(Document.accession_no) == normalized_accession.lower())
                    .first()
                )
                if existing:
                    return existing
            if normalized_source_url:
                url_variants = {
                    normalized_source_url.lower(),
                    f"{normalized_source_url.lower()}/",
                }
                existing = (
                    session.query(Document)
                    .filter(func.lower(Document.source_url).in_(url_variants))
                    .first()
                )
                if existing:
                    return existing
            existing = session.query(Document).filter_by(content_hash=content_hash).first()
            if existing:
                return existing

            doc = Document(
                ticker=normalized_ticker,
                title=title,
                source_url=normalized_source_url,
                source_type=source_type,
                source_name=source_name,
                form_type=form_type,
                cik=normalized_cik,
                accession_no=normalized_accession,
                published_at=published_at,
                content=content,
                raw_content=raw_content,
                content_hash=content_hash,
            )
            session.add(doc)
            session.flush()  # assign id

            seen_chunks = set()
            for c in chunks:
                chunk_key = (
                    str(c.get("content") or ""),
                    c.get("start_pos"),
                    c.get("end_pos"),
                )
                if chunk_key in seen_chunks:
                    continue
                seen_chunks.add(chunk_key)
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

    def deduplicate_documents(self, dry_run: bool = True) -> dict:
        """Find or remove provable duplicate ingestions using stable identity keys."""
        with self.SessionLocal() as session:
            documents = session.query(Document).order_by(Document.id.asc()).all()
            parent = {int(doc.id): int(doc.id) for doc in documents}

            def find(value: int) -> int:
                while parent[value] != value:
                    parent[value] = parent[parent[value]]
                    value = parent[value]
                return value

            def union(left: int, right: int) -> None:
                left_root, right_root = find(left), find(right)
                if left_root != right_root:
                    parent[max(left_root, right_root)] = min(left_root, right_root)

            seen_keys: dict[tuple[str, str], int] = {}
            for doc in documents:
                keys = []
                accession = self._normalize_accession(doc.accession_no)
                source_url = self._normalize_source_url(doc.source_url)
                content_hash = str(doc.content_hash or "").strip().lower()
                if accession:
                    keys.append(("accession", accession.lower()))
                if source_url:
                    keys.append(("source_url", source_url.lower()))
                if content_hash:
                    keys.append(("content_hash", content_hash))
                for key in keys:
                    if key in seen_keys:
                        union(int(doc.id), seen_keys[key])
                    else:
                        seen_keys[key] = int(doc.id)

            groups: dict[int, list[Document]] = defaultdict(list)
            for doc in documents:
                groups[find(int(doc.id))].append(doc)
            duplicate_groups = [rows for rows in groups.values() if len(rows) > 1]
            duplicate_ids = [
                int(doc.id)
                for rows in duplicate_groups
                for doc in sorted(rows, key=lambda row: int(row.id))[1:]
            ]
            chunk_count = 0
            if duplicate_ids:
                chunk_count = int(
                    session.query(func.count(Chunk.id))
                    .filter(Chunk.document_id.in_(duplicate_ids))
                    .scalar()
                    or 0
                )
                if not dry_run:
                    for doc in documents:
                        if int(doc.id) in duplicate_ids:
                            session.delete(doc)
                    session.commit()

            return {
                "dry_run": bool(dry_run),
                "documents_scanned": len(documents),
                "duplicate_group_count": len(duplicate_groups),
                "duplicate_document_count": len(duplicate_ids),
                "duplicate_chunk_count": chunk_count,
                "canonical_document_ids": [
                    min(int(doc.id) for doc in rows) for rows in duplicate_groups
                ],
                "duplicate_document_ids": duplicate_ids,
                "removed_document_count": 0 if dry_run else len(duplicate_ids),
                "removed_chunk_count": 0 if dry_run else chunk_count,
            }

    def count_documents(self) -> int:
        with self.SessionLocal() as session:
            return session.query(Document).count()

    def count_chunks(self) -> int:
        with self.SessionLocal() as session:
            return session.query(Chunk).count()

    def count_documents_by_ticker(self, ticker: str) -> int:
        symbol = str(ticker or "").upper().strip()
        with self.SessionLocal() as session:
            return session.query(Document).filter(Document.ticker == symbol).count()

    def apply_once_ticker_reset(self, reset_id: str, tickers: Sequence[str]) -> dict:
        """Delete selected ticker documents once, then persist an idempotency marker."""
        normalized_reset_id = str(reset_id or "").strip()
        normalized_tickers = sorted(
            {
                str(ticker or "").upper().strip()
                for ticker in tickers
                if str(ticker or "").strip()
            }
        )
        empty_result = {
            "applied": False,
            "already_applied": False,
            "reset_id": normalized_reset_id,
            "tickers": normalized_tickers,
            "removed_document_count": 0,
            "removed_chunk_count": 0,
            "removed_accessions": [],
        }
        if not normalized_reset_id or not normalized_tickers:
            return empty_result

        with self.SessionLocal() as session:
            maintenance_jobs = (
                session.query(RagJobStatus)
                .filter(
                    RagJobStatus.job_type == "maintenance",
                    RagJobStatus.status == "succeeded",
                )
                .order_by(RagJobStatus.id.desc())
                .all()
            )
            for job in maintenance_jobs:
                metadata = dict(job.metadata_json or {})
                if metadata.get("reset_id") == normalized_reset_id:
                    return {**empty_result, "already_applied": True}

            documents = (
                session.query(Document)
                .filter(func.upper(Document.ticker).in_(normalized_tickers))
                .order_by(Document.id.asc())
                .all()
            )
            document_ids = [int(document.id) for document in documents]
            removed_chunk_count = 0
            if document_ids:
                removed_chunk_count = int(
                    session.query(func.count(Chunk.id))
                    .filter(Chunk.document_id.in_(document_ids))
                    .scalar()
                    or 0
                )
            removed_accessions = [
                str(document.accession_no)
                for document in documents
                if document.accession_no
            ]
            for document in documents:
                session.delete(document)

            now = datetime.utcnow()
            session.add(
                RagJobStatus(
                    job_type="maintenance",
                    status="succeeded",
                    attempts=1,
                    max_attempts=1,
                    started_at=now,
                    finished_at=now,
                    metadata_json={
                        "operation": "ticker_reset",
                        "reset_id": normalized_reset_id,
                        "tickers": normalized_tickers,
                        "removed_document_count": len(documents),
                        "removed_chunk_count": removed_chunk_count,
                        "removed_accessions": removed_accessions,
                    },
                )
            )
            session.commit()
            return {
                **empty_result,
                "applied": True,
                "removed_document_count": len(documents),
                "removed_chunk_count": removed_chunk_count,
                "removed_accessions": removed_accessions,
            }

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

    def summarize_documents(self) -> dict:
        """Return lightweight library totals and filter facets."""
        with self.SessionLocal() as session:
            total_documents = session.query(Document).count()
            total_chunks = session.query(Chunk).count()
            pending_embeddings = (
                session.query(Chunk)
                .filter(or_(Chunk.embedding == None, Chunk.embedding == ""))
                .count()
            )
            latest_created_at = session.query(func.max(Document.created_at)).scalar()
            latest_published_at = session.query(func.max(Document.published_at)).scalar()

            return {
                "document_count": int(total_documents or 0),
                "chunk_count": int(total_chunks or 0),
                "pending_embedding_count": int(pending_embeddings or 0),
                "latest_created_at": latest_created_at,
                "latest_published_at": latest_published_at,
                "tickers": self._facet_rows(session, Document.ticker),
                "source_types": self._facet_rows(session, Document.source_type),
                "form_types": self._facet_rows(session, Document.form_type),
            }

    def list_documents(
        self,
        ticker: Optional[str] = None,
        source_type: Optional[str] = None,
        form_type: Optional[str] = None,
        query_text: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List document metadata and counts without returning full document text."""
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        with self.SessionLocal() as session:
            query = (
                session.query(
                    Document,
                    func.count(Chunk.id).label("chunk_count"),
                    func.sum(
                        case(
                            (or_(Chunk.embedding == None, Chunk.embedding == ""), 1),
                            else_=0,
                        )
                    ).label("pending_embedding_count"),
                )
                .outerjoin(Chunk)
            )
            query = self._apply_document_filters(
                query,
                ticker=ticker,
                source_type=source_type,
                form_type=form_type,
                query_text=query_text,
            )
            query = query.group_by(Document.id)
            total = query.count()
            rows = (
                query.order_by(
                    Document.published_at.is_(None),
                    Document.published_at.desc(),
                    Document.created_at.desc(),
                    Document.id.desc(),
                )
                .offset(offset)
                .limit(limit)
                .all()
            )
            return {
                "documents": [
                    self._document_summary_dict(
                        doc,
                        chunk_count=chunk_count,
                        pending_embedding_count=pending_embedding_count,
                    )
                    for doc, chunk_count, pending_embedding_count in rows
                ],
                "total": int(total or 0),
                "limit": limit,
                "offset": offset,
            }

    def get_document_detail(self, document_id: int, chunk_limit: int = 12) -> Optional[dict]:
        """Return one document summary plus bounded chunk excerpts."""
        chunk_limit = max(1, min(int(chunk_limit), 50))
        with self.SessionLocal() as session:
            doc = session.get(Document, int(document_id))
            if doc is None:
                return None
            chunk_count = (
                session.query(func.count(Chunk.id))
                .filter(Chunk.document_id == doc.id)
                .scalar()
            )
            pending_embedding_count = (
                session.query(func.count(Chunk.id))
                .filter(
                    Chunk.document_id == doc.id,
                    or_(Chunk.embedding == None, Chunk.embedding == ""),
                )
                .scalar()
            )
            chunks = (
                session.query(Chunk)
                .filter(Chunk.document_id == doc.id)
                .order_by(Chunk.id.asc())
                .limit(chunk_limit)
                .all()
            )
            detail = self._document_summary_dict(
                doc,
                chunk_count=chunk_count,
                pending_embedding_count=pending_embedding_count,
            )
            detail["chunks"] = [
                {
                    "chunk_id": chunk.id,
                    "start_pos": chunk.start_pos,
                    "end_pos": chunk.end_pos,
                    "has_embedding": bool(chunk.embedding),
                    "content": self._preview(chunk.content, 700),
                }
                for chunk in chunks
            ]
            return detail

    def get_document_chunk_id_map(self, document_ids: Sequence[int]) -> dict[int, list[int]]:
        ids = []
        for document_id in document_ids:
            try:
                ids.append(int(document_id))
            except (TypeError, ValueError):
                continue
        if not ids:
            return {}
        with self.SessionLocal() as session:
            rows = (
                session.query(Chunk.document_id, Chunk.id)
                .filter(Chunk.document_id.in_(ids))
                .all()
            )
            result: dict[int, list[int]] = {document_id: [] for document_id in ids}
            for document_id, chunk_id in rows:
                result.setdefault(int(document_id), []).append(int(chunk_id))
            return result

    def get_document_by_accession(self, accession_no: str) -> Optional[Document]:
        with self.SessionLocal() as session:
            return session.query(Document).filter(Document.accession_no == accession_no).first()

    @staticmethod
    def _facet_rows(session, column) -> list[dict]:
        rows = (
            session.query(column, func.count(Document.id))
            .filter(column.isnot(None))
            .group_by(column)
            .order_by(func.count(Document.id).desc(), column.asc())
            .all()
        )
        return [
            {"value": value, "count": int(count or 0)}
            for value, count in rows
            if value
        ]

    @staticmethod
    def _apply_document_filters(
        query,
        ticker: Optional[str] = None,
        source_type: Optional[str] = None,
        form_type: Optional[str] = None,
        query_text: Optional[str] = None,
    ):
        if ticker:
            query = query.filter(Document.ticker == str(ticker).upper().strip())
        if source_type:
            query = query.filter(Document.source_type == str(source_type).strip())
        if form_type:
            query = query.filter(Document.form_type == str(form_type).upper().strip())
        if query_text:
            pattern = f"%{str(query_text).strip()}%"
            query = query.filter(
                or_(
                    Document.title.ilike(pattern),
                    Document.ticker.ilike(pattern),
                    Document.source_type.ilike(pattern),
                    Document.source_name.ilike(pattern),
                    Document.form_type.ilike(pattern),
                    Document.accession_no.ilike(pattern),
                    Document.content.ilike(pattern),
                )
            )
        return query

    @classmethod
    def _document_summary_dict(
        cls,
        doc: Document,
        chunk_count: Optional[int] = None,
        pending_embedding_count: Optional[int] = None,
    ) -> dict:
        content = doc.content or ""
        return {
            "id": doc.id,
            "ticker": doc.ticker,
            "title": doc.title,
            "source_url": doc.source_url,
            "source_type": doc.source_type,
            "source_name": doc.source_name,
            "form_type": doc.form_type,
            "cik": doc.cik,
            "accession_no": doc.accession_no,
            "published_at": doc.published_at,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
            "content_length": len(content),
            "chunk_count": int(chunk_count or 0),
            "pending_embedding_count": int(pending_embedding_count or 0),
            "content_preview": cls._preview(content, 260),
        }

    @staticmethod
    def _preview(value: Optional[str], max_chars: int) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= max_chars:
            return text
        return text[: max(0, max_chars - 3)].rstrip() + "..."

    @staticmethod
    def _normalize_cik(cik: Optional[str]) -> Optional[str]:
        if cik is None:
            return None
        cleaned = str(cik).strip()
        if not cleaned:
            return None
        return cleaned.zfill(10)

    @staticmethod
    def _normalize_accession(accession_no: Optional[str]) -> Optional[str]:
        value = str(accession_no or "").strip()
        return value or None

    @staticmethod
    def _normalize_source_url(source_url: Optional[str]) -> Optional[str]:
        value = str(source_url or "").strip()
        if not value:
            return None
        return value.rstrip("/")

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
                q = q.filter(Document.published_at.isnot(None))
                q = q.filter(Document.published_at <= as_of_date)
            rows = q.all()

            # Vector retrieval path
            if embedding_service is not None and embedding_service.is_available():
                query_embedding = embedding_service.embed_text(query_text)
                scored = self._rank_vector_rows(query_embedding, rows, top_k=top_k)
                if scored:
                    return [
                        {
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
                for score, ch in fallback[:top_k]
            ]

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
