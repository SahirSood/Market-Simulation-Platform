import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import scan_tracked_secrets


def test_secret_scan_detects_common_tokens_without_returning_values():
    text = """
OPENAI_API_KEY=sk-proj-thisIsASecretLookingToken1234567890
DATABASE_URL=postgresql://user:password@db.internal.test/marketsim
"""

    findings = scan_tracked_secrets._scan_text("settings.py", text)

    assert {finding["pattern"] for finding in findings} == {
        "openai_key",
        "postgres_url_with_password",
    }
    assert all("sk-proj" not in str(finding) for finding in findings)
    assert all("user:password@" not in str(finding) for finding in findings)


def test_secret_scan_allows_placeholder_examples():
    text = """
OPENAI_API_KEY=your_openai_key_here
DATABASE_URL=postgresql://user:password@example-host:5432/marketsim
"""

    assert scan_tracked_secrets._scan_text(".env.example", text) == []


def test_secret_scan_main_prints_metadata_only(monkeypatch, capsys):
    monkeypatch.setattr(
        scan_tracked_secrets,
        "scan_tracked_files",
        lambda include_docs=False: [{"path": "app.py", "line": 4, "pattern": "openai_key"}],
    )
    monkeypatch.setattr(sys, "argv", ["scan_tracked_secrets.py"])

    assert scan_tracked_secrets.main() == 1
    output = capsys.readouterr().out
    assert "app.py:4" in output
    assert "openai_key" in output
    assert "sk-" not in output
