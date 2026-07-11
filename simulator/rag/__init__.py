"""Minimal RAG storage package.
Exports simple models and a repository for documents and chunks.
"""
from .models import Base, Document, Chunk
from .repository import RagRepository, create_tables
from .sec_ingestion import SecEdgarIngestionService
from .embeddings import (
	EmbeddingService,
	DeterministicFakeEmbeddingService,
	OpenAIEmbeddingService,
	get_openai_embedding_service_from_env,
)

__all__ = [
	"Base",
	"Document",
	"Chunk",
	"RagRepository",
	"create_tables",
	"SecEdgarIngestionService",
	"EmbeddingService",
	"DeterministicFakeEmbeddingService",
	"OpenAIEmbeddingService",
	"get_openai_embedding_service_from_env",
]

