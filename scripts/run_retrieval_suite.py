"""Run every labeled retrieval case file as one local regression suite."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
DEFAULT_CASES_DIR = ROOT / "data" / "retrieval_cases"
for path in (ROOT, SIM_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from evaluation import evaluate_retrieval_cases  # noqa: E402
from rag.embeddings import get_openai_embedding_service_from_env  # noqa: E402
from rag.repository import RagRepository  # noqa: E402
from scripts.eval_retrieval import append_history, load_cases  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SEC retrieval benchmark suite.")
    parser.add_argument(
        "--cases-dir",
        default=str(DEFAULT_CASES_DIR),
        help="Directory containing retrieval case JSON files.",
    )
    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Optional case files or file names inside --cases-dir. Defaults to all *.json files.",
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
    parser.add_argument("--record", action="store_true", help="Append each case-file run to retrieval history.")
    parser.add_argument("--allow-misses", action="store_true", help="Exit 0 even when cases miss.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    return parser.parse_args()


def resolve_case_files(cases_dir: str | Path, cases: list[str] | None = None) -> list[Path]:
    base = Path(cases_dir)
    if cases:
        paths = []
        for raw_path in cases:
            path = Path(raw_path)
            if not path.exists() and not path.is_absolute():
                path = base / raw_path
            paths.append(path)
    else:
        paths = sorted(base.glob("*.json"))
    return [path for path in paths if path.name.lower() != "readme.md"]


def evaluate_case_file(
    repository,
    path: str | Path,
    *,
    top_k: int | None = None,
    embedding_service=None,
) -> dict:
    metadata, cases = load_cases(path)
    if top_k is not None:
        cases = [{**case, "top_k": top_k} for case in cases]
    result = evaluate_retrieval_cases(repository, cases, embedding_service=embedding_service)
    return {
        "case_file": str(path),
        "metadata": metadata,
        **result,
    }


def summarize_suite(results: list[dict], *, database_url: str, embedding_enabled: bool) -> dict:
    case_count = sum(int(result["case_count"]) for result in results)
    hit_count = sum(int(result["hit_count"]) for result in results)
    reciprocal_ranks = [
        float(case["reciprocal_rank"])
        for result in results
        for case in result.get("cases", [])
    ]
    missed_cases = [
        {
            "case_file": result["case_file"],
            "name": case["name"],
            "ticker": case.get("ticker"),
        }
        for result in results
        for case in result.get("cases", [])
        if not case.get("hit")
    ]
    return {
        "database_url": database_url,
        "embedding_enabled": embedding_enabled,
        "file_count": len(results),
        "case_count": case_count,
        "hit_count": hit_count,
        "miss_count": case_count - hit_count,
        "recall_at_k": round(hit_count / case_count, 4) if case_count else 0.0,
        "mean_reciprocal_rank": round(mean(reciprocal_ranks), 4) if reciprocal_ranks else 0.0,
        "missed_cases": missed_cases,
        "files": results,
    }


def main() -> int:
    args = parse_args()
    files = resolve_case_files(args.cases_dir, args.cases)
    repository = RagRepository(args.db)
    repository.create_tables()
    embedding_service = get_openai_embedding_service_from_env() if args.use_embeddings else None
    embedding_enabled = bool(embedding_service and embedding_service.is_available())

    results = [
        evaluate_case_file(
            repository,
            path,
            top_k=args.top_k,
            embedding_service=embedding_service,
        )
        for path in files
    ]
    suite = summarize_suite(
        results,
        database_url=args.db,
        embedding_enabled=embedding_enabled,
    )
    if args.record:
        for result in results:
            append_history(
                result["case_file"],
                {
                    **result,
                    "embedding_enabled": embedding_enabled,
                },
            )

    if args.json:
        print(json.dumps(suite, indent=2, default=str))
    else:
        print(
            "Retrieval suite: "
            f"files={suite['file_count']} cases={suite['case_count']} "
            f"hits={suite['hit_count']} recall@k={suite['recall_at_k']:.2f} "
            f"mrr={suite['mean_reciprocal_rank']:.2f}"
        )
        for result in results:
            name = result["metadata"].get("name") or Path(result["case_file"]).name
            print(
                f"- {Path(result['case_file']).name}: {result['hit_count']}/{result['case_count']} "
                f"{name}"
            )
        if suite["missed_cases"]:
            print("Missed cases:")
            for case in suite["missed_cases"]:
                ticker = f" [{case['ticker']}]" if case.get("ticker") else ""
                print(f"- {Path(case['case_file']).name}: {case['name']}{ticker}")

    return 0 if args.allow_misses or suite["miss_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
