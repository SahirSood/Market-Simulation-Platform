"""Minimal smoke checks for the API container image."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
for path in (ROOT, SIM_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check API container imports")
    parser.add_argument("--require-native", action="store_true", help="Fail if pybind engine is unavailable")
    args = parser.parse_args()

    from engine_adapter import EngineAdapter, is_native_engine_module
    import api.server  # noqa: F401

    required_data_files = [
        ROOT / "data" / "retrieval_cases" / "sec_basic_cases.json",
        ROOT / "data" / "replay_events" / "sample_earnings_beat.json",
    ]
    missing_data_files = [str(path) for path in required_data_files if not path.exists()]
    if missing_data_files:
        raise RuntimeError(f"required runtime data files are missing: {missing_data_files}")

    adapter = EngineAdapter()
    if args.require_native and adapter._engine is None:
        raise RuntimeError("native engine module is unavailable")

    print({
        "api_import": True,
        "native_engine": adapter._engine is not None and is_native_engine_module(adapter._engine),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
