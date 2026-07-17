"""Inspect and requeue local RAG ingestion/embedding job rows."""
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
    parser = argparse.ArgumentParser(description="Inspect local RAG job status.")
    parser.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL") or "sqlite:///rag.db",
        help="SQLAlchemy database URL for RAG tables.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List recent job rows.")
    list_parser.add_argument("--job-type", default=None, help="Filter by ingestion or embedding.")
    list_parser.add_argument("--status", default=None, help="Filter by job status.")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    summary_parser = subparsers.add_parser("summary", help="Show grouped job counts.")
    summary_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    requeue_parser = subparsers.add_parser("requeue", help="Mark failed or skipped jobs as queued.")
    requeue_parser.add_argument("--job-type", default=None, help="Filter by ingestion or embedding.")
    requeue_parser.add_argument(
        "--status",
        action="append",
        default=None,
        help="Status to requeue. Can be repeated. Defaults to failed.",
    )
    requeue_parser.add_argument("--limit", type=int, default=20)
    requeue_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    return parser.parse_args()


def repository_from_args(args: argparse.Namespace) -> RagRepository:
    repository = RagRepository(args.db)
    repository.create_tables()
    return repository


def run_command(args: argparse.Namespace, repository: RagRepository) -> dict:
    if args.command == "list":
        return {
            "jobs": repository.list_job_status(
                job_type=args.job_type,
                status=args.status,
                limit=args.limit,
            )
        }
    if args.command == "summary":
        return {"summary": repository.summarize_job_status()}
    if args.command == "requeue":
        statuses = args.status or ["failed"]
        jobs = repository.requeue_jobs(
            job_type=args.job_type,
            statuses=statuses,
            limit=args.limit,
        )
        return {
            "requeued_count": len(jobs),
            "jobs": jobs,
            "next_step": _next_step(args.job_type),
        }
    raise ValueError(f"Unknown command: {args.command}")


def _next_step(job_type: str | None) -> str:
    if job_type == "embedding":
        return "Run scripts/embed_worker.py with the same database to process queued chunks."
    if job_type == "ingestion":
        return "Run scripts/ingest_poller.py with the same database and tickers/forms from job metadata."
    return "Run the relevant ingestion or embedding worker with the same database."


def print_human(result: dict, command: str) -> None:
    if command == "summary":
        summary = result["summary"]
        print(f"jobs={summary['total']} by_status={summary['by_status']}")
        for job_type, statuses in sorted(summary["by_type"].items()):
            print(f"- {job_type}: {statuses}")
        return

    jobs = result.get("jobs", [])
    if command == "requeue":
        print(f"requeued={result['requeued_count']}")
        print(result["next_step"])
    if not jobs:
        print("No jobs found.")
        return
    for row in jobs:
        print(
            f"- #{row['id']} {row['job_type']} {row['status']} "
            f"attempts={row['attempts']}/{row['max_attempts']}"
        )


def main() -> int:
    args = parse_args()
    repository = repository_from_args(args)
    result = run_command(args, repository)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_human(result, args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
