"""Minimal RAG storage package.
Exports simple models and a repository for documents and chunks.
"""
from .models import Base, Document, Chunk
from .repository import RagRepository, create_tables

__all__ = ["Base", "Document", "Chunk", "RagRepository", "create_tables"]
