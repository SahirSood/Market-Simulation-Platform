import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml_dataset import build_replay_ml_rows, summarize_replay_ml_rows, write_feature_dictionary


def test_build_replay_ml_rows_adds_next_event_and_benchmark_labels(tmp_path):
    runs = [
        {
            "id": "run-1",
            "name": "Six-month replay [claude]",
            "status": "completed",
            "input_fingerprint": "same-input",
            "decision_count": 2,
        }
    ]
    decisions_by_run = {
        "run-1": [
            {
                "id": 1,
                "run_id": "run-1",
                "event_index": 0,
                "as_of_time": "2026-01-01T21:00:00+00:00",
                "bot_id": "analyst-001-claude",
                "bot_name": "AnalystBot (Claude)",
                "llm_provider": "claude",
                "llm_input_tokens": 1000,
                "llm_output_tokens": 80,
                "llm_total_tokens": 1080,
                "llm_estimated_cost_usd": 0.02,
                "action": "BUY",
                "ticker": "AAPL",
                "quantity": 10,
                "confidence": 0.8,
                "evidence_ids": [1],
                "evidence_urls": ["https://example.com/aapl"],
                "model_metadata": {
                    "model": "claude-test",
                    "prompt_version": "v1",
                    "prompt_hash": "abc",
                    "base_personality": "AnalystBot",
                },
                "risk_approved": True,
                "event_payload": {
                    "prices": {"AAPL": 100.0, "SPY": 400.0},
                    "ticker_headlines": {
                        "AAPL": [
                            {
                                "title": "AAPL earnings beat expectations",
                                "source": "newswire",
                                "age_minutes": 30,
                            }
                        ]
                    },
                    "recent_headlines": [
                        {
                            "title": "FOMC minutes keep rates steady",
                            "source": "Federal Reserve",
                            "age_minutes": 120,
                        }
                    ],
                    "news_coverage": {
                        "headline_count": 2,
                        "real_headline_count": 2,
                        "synthetic_headline_count": 0,
                        "has_real_news": True,
                        "has_synthetic_market_summary": False,
                    },
                    "market_regime": {
                        "spy_return_1d": 0.01,
                        "risk_regime": "risk_on",
                        "trend_regime": "up",
                        "volatility_regime": "normal",
                    },
                    "generated_features": {
                        "AAPL": {
                            "return_1d": 0.02,
                            "return_5d": 0.04,
                            "rolling_volatility_20d": 0.2,
                        }
                    },
                },
            },
            {
                "id": 2,
                "run_id": "run-1",
                "event_index": 1,
                "as_of_time": "2026-01-02T21:00:00+00:00",
                "bot_id": "analyst-001-claude",
                "bot_name": "AnalystBot (Claude)",
                "llm_provider": "claude",
                "action": "HOLD",
                "hold_cause": "no_edge",
                "event_payload": {
                    "prices": {"AAPL": 110.0, "SPY": 404.0},
                    "news_coverage": {
                        "headline_count": 1,
                        "real_headline_count": 1,
                        "synthetic_headline_count": 0,
                    },
                },
            },
        ]
    }

    rows = build_replay_ml_rows(runs, decisions_by_run, benchmark="SPY")
    buy = rows[0]
    hold = rows[1]

    assert buy["current_price"] == 100.0
    assert buy["next_event_price"] == 110.0
    assert buy["directional_correct_next_event"] == 1
    assert buy["intent_mark_pnl_next_event"] == 100.0
    assert buy["benchmark_return_next_event"] == 0.01
    assert buy["excess_return_vs_benchmark_next_event"] == 0.09
    assert buy["beat_benchmark_next_event"] == 1
    assert buy["future_return_1d"] == 0.1
    assert buy["directional_correct_1d"] == 1
    assert buy["profitable_1d"] == 1
    assert buy["beat_benchmark_1d"] == 1
    assert buy["high_confidence_wrong_1d"] == 0
    assert buy["confidence_bucket"] == "high"
    assert buy["llm_input_tokens"] == 1000
    assert buy["llm_estimated_cost_usd"] == 0.02
    assert buy["event_best_long_ticker_1d"] == "AAPL"
    assert buy["event_best_long_return_1d"] == 0.1
    assert buy["headline_count"] == 2
    assert buy["ticker_headline_count"] == 1
    assert buy["macro_headline_count"] == 1
    assert buy["earnings_headline_count"] == 1
    assert buy["news_context_quality"] == "news_enriched"
    assert buy["ticker_return_5d"] == 0.04
    assert hold["directional_correct_next_event"] == ""
    assert hold["hold_cause"] == "no_edge"

    summary = summarize_replay_ml_rows(rows, runs, benchmark="SPY")
    assert summary["row_count"] == 2
    assert summary["trade_row_count"] == 1
    assert summary["directional_accuracy"] == 1.0
    assert summary["horizon_summary"]["1d"]["directional_accuracy"] == 1.0
    assert summary["cost_summary"]["available"] is True
    assert summary["cost_summary"]["recorded_cost_count"] == 1
    assert summary["cost_summary"]["total_estimated_llm_cost_usd"] == 0.02

    dictionary_path = tmp_path / "feature_dictionary.md"
    write_feature_dictionary(dictionary_path)
    dictionary = dictionary_path.read_text(encoding="utf-8")
    assert "`directional_correct_next_event`" in dictionary
    assert "`llm_estimated_cost_usd`" in dictionary
    assert "must not be used as" in dictionary
