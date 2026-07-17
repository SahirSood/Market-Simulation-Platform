import argparse
import sys

from scripts.rag_jobs import parse_args, run_command
from simulator.rag.repository import RagRepository


def test_rag_jobs_cli_summary_and_requeue():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()
    job_id = repo.start_job("embedding", metadata={"limit": 5}, max_attempts=2)
    repo.update_job_status(job_id, "failed", attempts=2, error="temporary outage")

    summary = run_command(argparse.Namespace(command="summary"), repo)
    assert summary["summary"]["by_status"]["failed"] == 1

    result = run_command(
        argparse.Namespace(
            command="requeue",
            job_type="embedding",
            status=["failed"],
            limit=10,
        ),
        repo,
    )

    assert result["requeued_count"] == 1
    assert result["jobs"][0]["status"] == "queued"
    assert "embed_worker.py" in result["next_step"]


def test_rag_jobs_cli_accepts_json_after_subcommand(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["rag_jobs.py", "summary", "--json"])

    args = parse_args()

    assert args.command == "summary"
    assert args.json is True
