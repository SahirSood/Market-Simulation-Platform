from __future__ import annotations

from abc import ABC, abstractmethod
from hashlib import sha256
import os
from typing import List, Optional, Sequence

try:
    from config import EMBEDDING_MODEL, OPENAI_PROJECT_ID
except ModuleNotFoundError:  # pragma: no cover - package import path
    from simulator.config import EMBEDDING_MODEL, OPENAI_PROJECT_ID


class EmbeddingService(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.embed_text(text) for text in texts]


class DeterministicFakeEmbeddingService(EmbeddingService):
    """Deterministic embedding for tests/local fallback without API keys."""

    def __init__(self, dimensions: int = 32):
        self.dimensions = dimensions

    def is_available(self) -> bool:
        return True

    def embed_text(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self.dimensions
        values: List[float] = []
        seed = text
        while len(values) < self.dimensions:
            digest = sha256(seed.encode("utf-8")).digest()
            for b in digest:
                values.append((b / 255.0) * 2.0 - 1.0)
                if len(values) >= self.dimensions:
                    break
            seed = seed + "|next"
        return values


class OpenAIEmbeddingService(EmbeddingService):
    def __init__(self, api_key: str, model: str = EMBEDDING_MODEL, project_id: str | None = None):
        self.api_key = api_key
        self.model = model
        self.project_id = project_id
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is not None:
            return self._client
        from openai import OpenAI

        self._client = OpenAI(api_key=self.api_key, project=self.project_id)
        return self._client

    def embed_text(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        client = self._get_client()
        resp = client.embeddings.create(model=self.model, input=list(texts))
        return [item.embedding for item in resp.data]


def get_openai_embedding_service_from_env() -> Optional[OpenAIEmbeddingService]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAIEmbeddingService(api_key=api_key, project_id=OPENAI_PROJECT_ID)
