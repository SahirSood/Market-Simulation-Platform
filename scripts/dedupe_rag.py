"""Safely find or remove duplicate RAG document ingestions.

Duplicates are grouped only when they share a stable SEC accession number,
normalized source URL, or exact content hash. The lowest document id is kept.
The default is a dry run; pass --apply to delete duplicate documents and their
cascaded chunks.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
for path in (ROOT, SIM_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rag.repository import RagRepository  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find or remove duplicate RAG ingestions.")
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL") or "sqlite:///rag.db",
        help="SQLAlchemy database URL. Defaults to DATABASE_URL or sqlite:///rag.db.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete duplicates. Without this flag the command is read-only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = RagRepository(args.db)
    repository.create_tables()
    result = repository.deduplicate_documents(dry_run=not args.apply)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
