"""Scan tracked source files for common secret-looking tokens.

The scanner reports only file/line/pattern metadata, never the matching value.
It is intentionally small and dependency-free so CI can run it before builds.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = {
    # Match current prefixed OpenAI keys and legacy high-entropy keys without
    # flagging ordinary URL slugs such as `sk-hynix`.
    "openai_key": re.compile(
        r"\bsk-(?:(?:proj|admin|org|svcacct|live|test)-[A-Za-z0-9_-]{20,}|[A-Za-z0-9]{40,})\b"
    ),
    "anthropic_key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "news_api_key": re.compile(r"\bNEWS_API_KEY\s*=\s*[A-Za-z0-9]{16,}\b"),
    "postgres_url_with_password": re.compile(r"\bpostgres(?:ql)?://[^:\s/@]+:[^@\s]+@"),
    "neon_password_token": re.compile(r"\bnpg_[A-Za-z0-9]{12,}\b"),
}

DEFAULT_EXCLUDES = {
    ".env.example",
    ".env.production.example",
    "README.md",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan git-tracked files for secret-looking values")
    parser.add_argument(
        "--include-docs",
        action="store_true",
        help="Also scan Markdown docs and example env files",
    )
    args = parser.parse_args()

    findings = scan_tracked_files(include_docs=args.include_docs)
    if findings:
        for finding in findings:
            print(
                f"ERROR: possible secret in {finding['path']}:{finding['line']} "
                f"({finding['pattern']})"
            )
        return 1
    print("Tracked secret scan passed")
    return 0


def scan_tracked_files(include_docs: bool = False) -> list[dict]:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    findings: list[dict] = []
    for relative_path in paths:
        if _skip_path(relative_path, include_docs=include_docs):
            continue
        full_path = ROOT / relative_path
        try:
            text = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        except OSError:
            continue
        findings.extend(_scan_text(relative_path.as_posix(), text))
    return findings


def _scan_text(path: str, text: str) -> list[dict]:
    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _allowlisted_line(line):
            continue
        for name, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append({"path": path, "line": line_no, "pattern": name})
    return findings


def _skip_path(path: Path, include_docs: bool) -> bool:
    path_text = path.as_posix()
    if path_text in DEFAULT_EXCLUDES and not include_docs:
        return True
    if "/tests/" in f"/{path_text}":
        return True
    if path.suffix.lower() in {".md", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf"} and not include_docs:
        return True
    if path_text.startswith(("frontend/dist/", "node_modules/", ".git/")):
        return True
    return False


def _allowlisted_line(line: str) -> bool:
    lowered = line.lower()
    return any(token in lowered for token in ("your_", "example", "placeholder", "<your", "test-", "test_"))


if __name__ == "__main__":
    raise SystemExit(main())
