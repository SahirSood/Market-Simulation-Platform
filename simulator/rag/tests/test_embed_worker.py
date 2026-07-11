import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from scripts.embed_worker import embed_once


class FakeRepository:
    def __init__(self):
        self.created = False
        self.calls = []

    def create_tables(self):
        self.created = True

    def embed_missing_chunks(self, embedding_service, limit, batch_size):
        self.calls.append((embedding_service, limit, batch_size))
        return 7


class FakeEmbeddingService:
    def is_available(self):
        return True


def test_embed_once_uses_repository_batch_embedding():
    repo = FakeRepository()
    service = FakeEmbeddingService()

    embedded = embed_once(
        db_url="sqlite:///:memory:",
        limit=100,
        batch_size=16,
        repository=repo,
        embedding_service=service,
    )

    assert embedded == 7
    assert repo.created is True
    assert repo.calls == [(service, 100, 16)]
