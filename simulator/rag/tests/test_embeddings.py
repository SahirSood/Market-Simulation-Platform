import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from simulator.rag.embeddings import (
    DeterministicFakeEmbeddingService,
    get_openai_embedding_service_from_env,
)
from simulator.rag.repository import RagRepository


class ToyEmbeddingService:
    def is_available(self) -> bool:
        return True

    def embed_text(self, text: str):
        t = text.lower()
        if "profit" in t or "revenue" in t:
            return [1.0, 0.0]
        if "lawsuit" in t or "risk" in t:
            return [0.0, 1.0]
        return [0.2, 0.2]


def test_deterministic_fake_embedding_is_stable():
    svc = DeterministicFakeEmbeddingService(dimensions=16)
    a = svc.embed_text("same text")
    b = svc.embed_text("same text")
    c = svc.embed_text("different text")

    assert len(a) == 16
    assert a == b
    assert a != c


def test_openai_service_factory_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    svc = get_openai_embedding_service_from_env()
    assert svc is None


def test_vector_retrieval_and_keyword_fallback():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()

    text = "Profit increased strongly this quarter. Legal lawsuit risk remains elevated."
    chunks = [
        {"content": "Profit increased strongly this quarter.", "start_pos": 0, "end_pos": 40},
        {"content": "Legal lawsuit risk remains elevated.", "start_pos": 41, "end_pos": 80},
    ]
    repo.add_document_with_chunks(
        ticker="AAPL",
        title="Mock 10-Q",
        source_url="http://example.com/mock",
        content=text,
        chunks=chunks,
        source_type="sec_filing",
        form_type="10-Q",
        published_at=datetime(2025, 1, 1),
    )

    toy = ToyEmbeddingService()
    updated = repo.embed_missing_chunks(toy)
    assert updated == 2

    # Vector path should rank profit chunk first for a profit query
    vector_results = repo.retrieve_evidence(
        ticker="AAPL",
        query_text="profit outlook",
        top_k=2,
        embedding_service=toy,
    )
    assert len(vector_results) >= 1
    assert "Profit" in vector_results[0]["content"]

    # No embedding service => keyword fallback path
    fallback_results = repo.retrieve_evidence(
        ticker="AAPL",
        query_text="lawsuit",
        top_k=2,
        embedding_service=None,
    )
    assert len(fallback_results) >= 1
    assert "lawsuit" in fallback_results[0]["content"].lower()


def test_embed_missing_chunks_batches_requests():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()
    repo.add_document_with_chunks(
        ticker="AAPL",
        title="Batch test",
        source_url="http://example.com/batch",
        content="one two three",
        chunks=[
            {"content": "one", "start_pos": 0, "end_pos": 3},
            {"content": "two", "start_pos": 4, "end_pos": 7},
            {"content": "three", "start_pos": 8, "end_pos": 13},
        ],
    )

    class BatchService:
        def __init__(self):
            self.calls = []

        def is_available(self):
            return True

        def embed_texts(self, texts):
            self.calls.append(list(texts))
            return [[float(len(text)), 0.0] for text in texts]

    service = BatchService()
    updated = repo.embed_missing_chunks(service, batch_size=2)

    assert updated == 3
    assert service.calls == [["one", "two"], ["three"]]
    assert repo.get_chunks_without_embeddings() == []
