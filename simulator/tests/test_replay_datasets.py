import json
from datetime import datetime
from types import SimpleNamespace
from pathlib import Path

from scripts.run_replay_matrix import build_commands


ROOT = Path(__file__).resolve().parents[2]
REPLAY_EVENTS_DIR = ROOT / "data" / "replay_events"


def _parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_bundled_replay_event_files_are_valid_and_ordered():
    files = sorted(REPLAY_EVENTS_DIR.glob("sample_*.json"))

    assert files, "Expected bundled replay event fixtures"

    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("name")
        assert payload.get("description")
        assert isinstance(payload.get("config"), dict)
        events = payload.get("events")
        assert isinstance(events, list)
        assert len(events) >= 2

        previous_time = None
        for event in events:
            raw_time = event.get("timestamp") or event.get("as_of_time")
            assert raw_time, f"{path.name} event is missing timestamp"
            event_time = _parse_time(raw_time)
            if previous_time is not None:
                assert event_time > previous_time
            previous_time = event_time

            prices = event.get("prices")
            assert isinstance(prices, dict)
            assert prices
            assert all(isinstance(price, (int, float)) for price in prices.values())

            headline_count = (
                len(event.get("trending_headlines") or [])
                + len(event.get("recent_headlines") or [])
                + sum(
                    len(items)
                    for items in (event.get("ticker_headlines") or {}).values()
                )
            )
            assert headline_count > 0


def test_sec_filing_risk_fixture_documents_no_lookahead_intent():
    payload = json.loads(
        (REPLAY_EVENTS_DIR / "sample_sec_filing_risk.json").read_text(
            encoding="utf-8"
        )
    )

    assert "rag_expectation" in payload["config"]
    assert "at or before each event" in payload["config"]["rag_expectation"]


def test_replay_matrix_builds_same_input_provider_commands():
    event_file = REPLAY_EVENTS_DIR / "sample_ai_infrastructure_cycle.json"
    args = SimpleNamespace(
        events=[str(event_file)],
        provider_sets=["claude", "openai"],
        bots="analyst,bear",
        db="sqlite:///replay.db",
        no_orders=True,
    )

    commands = build_commands(args)

    assert len(commands) == 2
    assert all(str(event_file) in command for command in commands)
    assert commands[0][commands[0].index("--providers") + 1] == "claude"
    assert commands[1][commands[1].index("--providers") + 1] == "openai"
    assert all("--no-orders" in command for command in commands)
