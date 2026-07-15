import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation import (
    compare_model_groups,
    decision_evidence_status,
    evaluate_retrieval_cases,
    summarize_decisions,
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
        "confidence": confidence,
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
