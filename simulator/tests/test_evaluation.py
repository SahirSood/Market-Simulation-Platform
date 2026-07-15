import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation import (
    compare_model_groups,
    compare_replay_runs,
    decision_evidence_status,
    evaluate_retrieval_cases,
    get_bot_behavior_detail,
    summarize_decisions,
    summarize_bot_behavior,
)


def _decision(
    action,
    provider="claude",
    evidence_ids=None,
    speculative=False,
    fill_qty_total=0,
    confidence=0.5,
):
    return {
        "action": action,
        "bot_id": f"bot-{provider}",
        "bot_name": f"Bot {provider}",
        "llm_provider": provider,
        "evidence_ids": evidence_ids or [],
        "evidence_urls": ["https://example.com/filing"] if evidence_ids else [],
        "speculative": speculative,
        "fill_qty_total": fill_qty_total,
        "fill_count": 1 if fill_qty_total else 0,
        "confidence": confidence,
        "portfolio_snapshot": {"cash": 100000, "positions": {}, "cost_basis": {}, "total_value": 100000},
    }


def test_decision_evidence_status_categories():
    assert decision_evidence_status(_decision("HOLD")) == "hold"
    assert decision_evidence_status(_decision("BUY", evidence_ids=[1])) == "evidence_backed"
    assert decision_evidence_status(_decision("SELL", speculative=True)) == "speculative"
    assert (
        decision_evidence_status(_decision("BUY", evidence_ids=[1], speculative=True))
        == "speculative_evidence_backed"
    )
    assert decision_evidence_status(_decision("SELL")) == "unsupported"


def test_summarize_decisions_tracks_citation_speculation_and_provider_groups():
    rows = [
        _decision("BUY", "claude", evidence_ids=[1], fill_qty_total=10, confidence=0.8),
        _decision("SELL", "claude", speculative=True, confidence=0.4),
        _decision("BUY", "openai", confidence=0.6),
        _decision("HOLD", "openai", confidence=0.0),
    ]

    summary = summarize_decisions(rows)
    totals = summary["totals"]

    assert totals["decision_count"] == 4
    assert totals["trade_count"] == 3
    assert totals["evidence_backed_trade_count"] == 1
    assert totals["speculative_trade_count"] == 1
    assert totals["unsupported_trade_count"] == 1
    assert totals["citation_rate"] == 0.3333
    assert totals["fill_rate"] == 0.3333
    assert summary["by_provider"]["claude"]["trade_count"] == 2
    assert summary["by_provider"]["openai"]["hold_count"] == 1


def test_compare_model_groups_orders_provider_rows():
    rows = [
        _decision("BUY", "openai"),
        _decision("BUY", "claude", evidence_ids=[1]),
    ]

    comparison = compare_model_groups(rows)

    assert comparison[0]["group"] == "claude"
    assert comparison[0]["citation_rate"] == 1.0


def test_summarize_bot_behavior_tracks_action_mix_and_risk_rejections():
    rows = [
        {
            **_decision("BUY", evidence_ids=[1], fill_qty_total=10, confidence=0.7),
            "id": 1,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "bot_id": "analyst-001-claude",
            "bot_name": "AnalystBot (Claude)",
            "ticker": "AAPL",
            "portfolio_snapshot": {"cash": 99000, "positions": {"AAPL": 10}, "cost_basis": {"AAPL": 100}, "total_value": 100000},
        },
        {
            **_decision("HOLD", confidence=0.4),
            "id": 2,
            "timestamp": "2026-01-01T00:10:00+00:00",
            "bot_id": "analyst-001-claude",
            "bot_name": "AnalystBot (Claude)",
            "reasoning": "Risk check rejected original order (SELL 10 AAPL): short selling disabled",
            "portfolio_snapshot": {"cash": 99000, "positions": {"AAPL": 10}, "cost_basis": {"AAPL": 100}, "total_value": 100500},
        },
    ]

    result = summarize_bot_behavior(rows)
    bot = result["bots"][0]

    assert result["bot_count"] == 1
    assert bot["action_counts"]["BUY"] == 1
    assert bot["action_counts"]["HOLD"] == 1
    assert bot["ticker_counts"]["AAPL"] == 1
    assert bot["risk_rejection_count"] == 1
    assert bot["confidence_trend"]["latest"] == 0.4
    assert bot["confidence_trend"]["delta"] == -0.3
    assert bot["portfolio"]["latest_total_value"] == 100500.0
    assert bot["portfolio"]["value_change"] == 500.0


def test_get_bot_behavior_detail_returns_chronological_timeline():
    rows = [
        {
            **_decision("SELL", provider="openai", speculative=True, confidence=0.6),
            "id": 2,
            "timestamp": "2026-01-01T00:10:00+00:00",
            "bot_id": "bear-001-openai",
            "bot_name": "BearBot (OpenAI)",
            "ticker": "MSFT",
        },
        {
            **_decision("HOLD", provider="openai", confidence=0.2),
            "id": 1,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "bot_id": "bear-001-openai",
            "bot_name": "BearBot (OpenAI)",
        },
    ]

    result = get_bot_behavior_detail(rows)

    assert result["bot"]["base_personality"] == "BearBot"
    assert [row["id"] for row in result["timeline"]] == [1, 2]
    assert result["timeline"][1]["evidence_status"] == "speculative"


def test_compare_replay_runs_summarizes_shared_input_results():
    runs = [
        {
            "id": "run-claude",
            "name": "Claude replay",
            "status": "completed",
            "input_fingerprint": "same-input",
            "config": {"providers": ["claude"]},
        },
        {
            "id": "run-openai",
            "name": "OpenAI replay",
            "status": "completed",
            "input_fingerprint": "same-input",
            "config": {"providers": ["openai"]},
        },
    ]
    decisions_by_run = {
        "run-claude": [
            {
                **_decision("BUY", "claude", evidence_ids=[1], fill_qty_total=10),
                "id": 1,
                "as_of_time": "2026-01-01T00:00:00+00:00",
                "bot_id": "analyst-001-claude",
                "bot_name": "AnalystBot (Claude)",
                "risk_approved": True,
                "portfolio_snapshot": {"cash": 99000, "positions": {"AAPL": 10}, "cost_basis": {"AAPL": 100}, "total_value": 100500},
            }
        ],
        "run-openai": [
            {
                **_decision("SELL", "openai", speculative=True),
                "id": 2,
                "as_of_time": "2026-01-01T00:00:00+00:00",
                "bot_id": "bear-001-openai",
                "bot_name": "BearBot (OpenAI)",
                "risk_approved": False,
                "portfolio_snapshot": {"cash": 100000, "positions": {}, "cost_basis": {}, "total_value": 100000},
            }
        ],
    }

    result = compare_replay_runs(runs, decisions_by_run)

    assert result["input_fingerprint"] == "same-input"
    assert result["run_count"] == 2
    assert result["runs"][0]["run"]["id"] == "run-claude"
    assert result["runs"][0]["metrics"]["citation_rate"] == 1.0
    assert result["runs"][1]["metrics"]["risk_rejection_rate"] == 1.0
    assert result["by_provider"][0]["provider"] == "claude"
    assert result["by_personality"][0]["base_personality"] == "AnalystBot"


class FakeRepository:
    def retrieve_evidence(self, ticker, query_text, top_k, embedding_service=None, as_of_date=None):
        assert as_of_date is not None
        return [
            {"chunk_id": 10, "document_id": 100},
            {"chunk_id": 11, "document_id": 101},
        ][:top_k]


def test_evaluate_retrieval_cases_computes_recall_and_mrr():
    result = evaluate_retrieval_cases(
        FakeRepository(),
        [
            {
                "name": "margin case",
                "ticker": "AAPL",
                "query_text": "gross margin",
                "expected_chunk_ids": [11],
                "as_of_date": "2026-01-01T00:00:00+00:00",
            }
        ],
    )

    assert result["case_count"] == 1
    assert result["hit_count"] == 1
    assert result["recall_at_k"] == 1.0
    assert result["mean_reciprocal_rank"] == 0.5
