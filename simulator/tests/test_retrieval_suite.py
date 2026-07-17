import json
from pathlib import Path

from scripts.run_retrieval_suite import (
    evaluate_case_file,
    resolve_case_files,
    summarize_suite,
)


class FakeRepository:
    def retrieve_evidence(self, ticker, query_text, top_k, embedding_service=None, as_of_date=None):
        rows = [
            {
                "chunk_id": 1,
                "document_id": 10,
                "ticker": ticker,
                "source_url": "https://example.com/sec",
                "accession_no": "0001",
                "content": "cash liquidity revenue margin",
            }
        ]
        return rows[:top_k]


def _write_cases(path: Path, expected_text: str) -> None:
    path.write_text(
        json.dumps(
            {
                "name": path.stem,
                "cases": [
                    {
                        "name": f"{path.stem} case",
                        "ticker": "AAPL",
                        "query_text": "cash liquidity",
                        "expected_text_contains": [expected_text],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_retrieval_suite_resolves_and_summarizes_case_files(tmp_path):
    hit_file = tmp_path / "hit.json"
    miss_file = tmp_path / "miss.json"
    _write_cases(hit_file, "liquidity")
    _write_cases(miss_file, "inventory")

    files = resolve_case_files(tmp_path)
    results = [
        evaluate_case_file(FakeRepository(), path, top_k=3)
        for path in files
    ]
    suite = summarize_suite(results, database_url="sqlite:///:memory:", embedding_enabled=False)

    assert [path.name for path in files] == ["hit.json", "miss.json"]
    assert suite["file_count"] == 2
    assert suite["case_count"] == 2
    assert suite["hit_count"] == 1
    assert suite["miss_count"] == 1
    assert suite["recall_at_k"] == 0.5
    assert suite["missed_cases"][0]["name"] == "miss case"
