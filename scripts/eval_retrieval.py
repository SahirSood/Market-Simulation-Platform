"""Run labeled retrieval benchmark cases against the local RAG store."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
HISTORY_PATH = ROOT / "data" / "retrieval_runs" / "history.jsonl"
if str(SIM_DIR) not in sys.path:
    sys.path.insert(0, str(SIM_DIR))

from evaluation import evaluate_retrieval_cases  # noqa: E402
from rag.embeddings import get_openai_embedding_service_from_env  # noqa: E402
from rag.repository import RagRepository  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality.")
    parser.add_argument(
        "--cases",
        default=str(ROOT / "data" / "retrieval_cases" / "sec_basic_cases.json"),
        help="Path to retrieval case JSON.",
    )
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL") or "sqlite:///rag.db",
        help="SQLAlchemy database URL for RAG tables.",
    )
    parser.add_argument("--top-k", type=int, default=None, help="Override top_k for every case.")
    parser.add_argument(
        "--use-embeddings",
        action="store_true",
        help="Use OpenAI embeddings when OPENAI_API_KEY is configured.",
    )
    parser.add_argument("--record", action="store_true", help="Append this run to retrieval history.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    return parser.parse_args()


def load_cases(path: str | Path) -> tuple[dict, list[dict]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return {}, payload
    if not isinstance(payload, dict):
        raise ValueError("Retrieval case file must be a JSON list or object.")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Retrieval case object must contain a cases list.")
    return {k: v for k, v in payload.items() if k != "cases"}, cases


def main() -> int:
    args = parse_args()
    metadata, cases = load_cases(args.cases)
    if args.top_k is not None:
        for case in cases:
            case["top_k"] = args.top_k

    repository = RagRepository(args.db)
    repository.create_tables()
    embedding_service = get_openai_embedding_service_from_env() if args.use_embeddings else None
    result = {
        "metadata": metadata,
        "database_url": args.db,
        "embedding_enabled": bool(embedding_service and embedding_service.is_available()),
        **evaluate_retrieval_cases(repository, cases, embedding_service=embedding_service),
    }
    if args.record:
        append_history(args.cases, result)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    print(f"Retrieval eval: {metadata.get('name') or Path(args.cases).name}")
    print(
        f"cases={result['case_count']} hits={result['hit_count']} "
        f"recall@k={result['recall_at_k']:.2f} mrr={result['mean_reciprocal_rank']:.2f}"
    )
    for row in result["cases"]:
        status = "hit" if row["hit"] else "miss"
        rank = row["hit_rank"] if row["hit_rank"] is not None else "-"
        print(f"- {status:4} rank={rank} {row['name']}")
    return 0 if result["hit_count"] == result["case_count"] else 1


def append_history(case_path: str, result: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ran_at": datetime.utcnow().isoformat() + "Z",
        "case_file": str(case_path),
        "case_count": result["case_count"],
        "hit_count": result["hit_count"],
        "recall_at_k": result["recall_at_k"],
        "mean_reciprocal_rank": result["mean_reciprocal_rank"],
        "embedding_enabled": result["embedding_enabled"],
    }
    with HISTORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, default=str) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
