"""Replay-to-ML dataset export helpers.

The exporter intentionally derives labels from replay event payloads instead of
mutating replay records. Features come from the decision timestamp or earlier;
future prices are used only for label columns.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import select

from replay import ReplayDecisionRecord, ReplayRunRecord, ReplayStore


TRADE_ACTIONS = {"BUY", "SELL"}
DEFAULT_BENCHMARK = "SPY"
DEFAULT_HORIZONS = {"1d": 1, "3d": 3, "7d": 7}
HIGH_CONFIDENCE_THRESHOLD = 0.7
BIG_MOVE_THRESHOLD = 0.02
LARGE_LOSS_THRESHOLD = -0.02
BENCHMARK_LIKE_SYMBOLS = {
    "SPY", "QQQ", "TLT", "GLD", "IEF", "IWM", "XLF", "XLK", "XLE", "XLV", "XLY",
    "^GSPC", "^IXIC", "^RUT",
}

REPLAY_ML_COLUMNS = [
    "decision_id",
    "run_id",
    "run_name",
    "run_status",
    "input_fingerprint",
    "event_index",
    "as_of_time",
    "mode",
    "bot_id",
    "bot_name",
    "base_personality",
    "llm_provider",
    "llm_input_tokens",
    "llm_output_tokens",
    "llm_total_tokens",
    "llm_estimated_cost_usd",
    "model",
    "prompt_version",
    "prompt_hash",
    "action",
    "hold_cause",
    "ticker",
    "quantity",
    "limit_price",
    "confidence",
    "speculative",
    "reasoning_length",
    "headline_used",
    "evidence_count",
    "evidence_url_count",
    "risk_checked",
    "risk_approved",
    "risk_blocked",
    "risk_reason",
    "fill_count",
    "fill_qty_total",
    "fill_avg_price",
    "current_price",
    "next_event_price",
    "return_next_event",
    "signed_return_next_event",
    "directional_correct_next_event",
    "intent_mark_pnl_next_event",
    "benchmark_symbol",
    "benchmark_price",
    "benchmark_next_event_price",
    "benchmark_return_next_event",
    "excess_return_vs_benchmark_next_event",
    "beat_benchmark_next_event",
    "future_price_1d",
    "future_return_1d",
    "future_signed_return_1d",
    "directional_correct_1d",
    "profitable_1d",
    "intent_mark_pnl_1d",
    "benchmark_future_price_1d",
    "benchmark_return_1d",
    "excess_return_vs_benchmark_1d",
    "beat_benchmark_1d",
    "large_loss_1d",
    "high_confidence_wrong_1d",
    "future_price_3d",
    "future_return_3d",
    "future_signed_return_3d",
    "directional_correct_3d",
    "profitable_3d",
    "intent_mark_pnl_3d",
    "benchmark_future_price_3d",
    "benchmark_return_3d",
    "excess_return_vs_benchmark_3d",
    "beat_benchmark_3d",
    "large_loss_3d",
    "high_confidence_wrong_3d",
    "future_price_7d",
    "future_return_7d",
    "future_signed_return_7d",
    "directional_correct_7d",
    "profitable_7d",
    "intent_mark_pnl_7d",
    "benchmark_future_price_7d",
    "benchmark_return_7d",
    "excess_return_vs_benchmark_7d",
    "beat_benchmark_7d",
    "large_loss_7d",
    "high_confidence_wrong_7d",
    "confidence_bucket",
    "event_best_long_ticker_1d",
    "event_best_long_return_1d",
    "event_worst_ticker_1d",
    "event_worst_return_1d",
    "event_best_abs_ticker_1d",
    "event_best_abs_return_1d",
    "hold_missed_big_move_1d",
    "headline_count",
    "real_headline_count",
    "synthetic_headline_count",
    "ticker_headline_count",
    "macro_headline_count",
    "filing_headline_count",
    "earnings_headline_count",
    "headline_source_count",
    "headline_sources",
    "headline_age_minutes_min",
    "headline_age_minutes_avg",
    "has_real_news",
    "has_synthetic_market_summary",
    "news_context_quality",
    "event_spy_return_1d",
    "event_qqq_return_1d",
    "event_tlt_return_1d",
    "event_gld_return_1d",
    "event_risk_regime",
    "event_trend_regime",
    "event_volatility_regime",
    "event_breadth_proxy",
    "ticker_return_1d",
    "ticker_return_5d",
    "ticker_return_20d",
    "ticker_rolling_volatility_20d",
    "ticker_volume_ratio_20d",
    "ticker_gap_from_previous_close",
    "ticker_distance_from_20d_ma",
]


COLUMN_DICTIONARY = {
    "decision_id": ("integer", "replay decision row", "Stable replay decision row id.", "none"),
    "run_id": ("string", "replay run", "Replay run id.", "none"),
    "run_name": ("string", "replay run", "Human-readable replay run name.", "none"),
    "run_status": ("string", "replay run", "Run status at export time.", "none"),
    "input_fingerprint": ("string", "replay run", "Hash of replay input events for same-input comparison.", "none"),
    "event_index": ("integer", "replay decision", "Zero-based replay event index.", "none"),
    "as_of_time": ("timestamp", "replay decision", "Decision timestamp used as the no-lookahead cutoff.", "none"),
    "mode": ("string", "constant", "Dataset mode; currently replay.", "none"),
    "bot_id": ("string", "replay decision", "Provider-specific bot id.", "none"),
    "bot_name": ("string", "replay decision", "Display bot name.", "none"),
    "base_personality": ("string", "derived", "Bot name without provider suffix.", "none"),
    "llm_provider": ("string", "replay decision", "LLM provider used for the decision.", "none"),
    "llm_input_tokens": ("integer", "replay decision", "Recorded prompt/input token count when provider usage was available.", "metric"),
    "llm_output_tokens": ("integer", "replay decision", "Recorded completion/output token count when provider usage was available.", "metric"),
    "llm_total_tokens": ("integer", "replay decision", "Recorded total token count when provider usage was available.", "metric"),
    "llm_estimated_cost_usd": ("float", "replay decision", "Estimated model-call cost for this replay decision when captured.", "metric"),
    "model": ("string", "model metadata", "Model name recorded with the replay decision.", "none"),
    "prompt_version": ("string", "model metadata", "Prompt version recorded with the replay decision.", "none"),
    "prompt_hash": ("string", "model metadata", "Prompt hash recorded with the replay decision.", "none"),
    "action": ("string", "replay decision", "BUY, SELL, HOLD, or sanitized action.", "none"),
    "hold_cause": ("string", "replay decision", "Public structured reason for a HOLD decision, when present.", "none"),
    "ticker": ("string", "replay decision", "Decision ticker if a trade was proposed.", "none"),
    "quantity": ("integer", "replay decision", "Proposed order quantity.", "none"),
    "limit_price": ("float", "replay decision", "Proposed limit price when present.", "none"),
    "confidence": ("float", "replay decision", "Model confidence score after parsing.", "none"),
    "speculative": ("boolean", "replay decision", "Whether the model marked the idea speculative.", "none"),
    "reasoning_length": ("integer", "derived", "Character length of stored public reasoning.", "none"),
    "headline_used": ("string", "replay decision", "Headline cited by the model, if any.", "none"),
    "evidence_count": ("integer", "replay decision", "Number of cited evidence ids.", "none"),
    "evidence_url_count": ("integer", "replay decision", "Number of cited evidence URLs.", "none"),
    "risk_checked": ("boolean", "replay decision", "Whether deterministic risk ran for this row.", "none"),
    "risk_approved": ("boolean", "replay decision", "Risk approval result when checked.", "none"),
    "risk_blocked": ("boolean", "derived", "True when risk checked and rejected the proposal.", "none"),
    "risk_reason": ("string", "replay decision", "Risk approval or rejection reason.", "none"),
    "fill_count": ("integer", "replay decision", "Recorded fill count.", "none"),
    "fill_qty_total": ("integer", "replay decision", "Total filled quantity.", "none"),
    "fill_avg_price": ("float", "replay decision", "Average fill price when filled.", "none"),
    "current_price": ("float", "event payload", "Ticker price at decision time.", "feature"),
    "next_event_price": ("float", "future event payload", "Ticker price at the next replay event.", "label"),
    "return_next_event": ("float", "future event payload", "Raw ticker return from current to next replay event.", "label"),
    "signed_return_next_event": ("float", "future event payload", "Return aligned to BUY or SELL direction.", "label"),
    "directional_correct_next_event": ("boolean", "derived label", "True when signed next-event return is positive.", "label"),
    "intent_mark_pnl_next_event": ("float", "derived label", "Intent PnL using proposed quantity and next-event mark.", "label"),
    "benchmark_symbol": ("string", "export argument", "Benchmark used for relative labels.", "none"),
    "benchmark_price": ("float", "event payload", "Benchmark price at decision time.", "feature"),
    "benchmark_next_event_price": ("float", "future event payload", "Benchmark price at next replay event.", "label"),
    "benchmark_return_next_event": ("float", "future event payload", "Benchmark return to next replay event.", "label"),
    "excess_return_vs_benchmark_next_event": ("float", "derived label", "Signed return minus benchmark return.", "label"),
    "beat_benchmark_next_event": ("boolean", "derived label", "True when signed return beats benchmark return.", "label"),
    "future_price_1d": ("float", "future event payload", "Ticker price one trading event after decision time.", "label"),
    "future_return_1d": ("float", "future event payload", "Raw ticker return one trading event after decision time.", "label"),
    "future_signed_return_1d": ("float", "derived label", "One-event return aligned to BUY or SELL direction.", "label"),
    "directional_correct_1d": ("boolean", "derived label", "True when one-event signed return is positive.", "label"),
    "profitable_1d": ("boolean", "derived label", "Alias for whether the one-event trade intent made money before costs.", "label"),
    "intent_mark_pnl_1d": ("float", "derived label", "Intent PnL using proposed quantity and one-event mark.", "label"),
    "benchmark_future_price_1d": ("float", "future event payload", "Benchmark price one trading event after decision time.", "label"),
    "benchmark_return_1d": ("float", "future event payload", "Benchmark return one trading event after decision time.", "label"),
    "excess_return_vs_benchmark_1d": ("float", "derived label", "One-event signed return minus benchmark return.", "label"),
    "beat_benchmark_1d": ("boolean", "derived label", "True when one-event signed return beats benchmark return.", "label"),
    "large_loss_1d": ("boolean", "derived label", "True when one-event signed return is below the large-loss threshold.", "label"),
    "high_confidence_wrong_1d": ("boolean", "derived label", "True when confidence is high and one-event direction is wrong.", "label"),
    "future_price_3d": ("float", "future event payload", "Ticker price three trading events after decision time.", "label"),
    "future_return_3d": ("float", "future event payload", "Raw ticker return three trading events after decision time.", "label"),
    "future_signed_return_3d": ("float", "derived label", "Three-event return aligned to BUY or SELL direction.", "label"),
    "directional_correct_3d": ("boolean", "derived label", "True when three-event signed return is positive.", "label"),
    "profitable_3d": ("boolean", "derived label", "Whether the three-event trade intent made money before costs.", "label"),
    "intent_mark_pnl_3d": ("float", "derived label", "Intent PnL using proposed quantity and three-event mark.", "label"),
    "benchmark_future_price_3d": ("float", "future event payload", "Benchmark price three trading events after decision time.", "label"),
    "benchmark_return_3d": ("float", "future event payload", "Benchmark return three trading events after decision time.", "label"),
    "excess_return_vs_benchmark_3d": ("float", "derived label", "Three-event signed return minus benchmark return.", "label"),
    "beat_benchmark_3d": ("boolean", "derived label", "True when three-event signed return beats benchmark return.", "label"),
    "large_loss_3d": ("boolean", "derived label", "True when three-event signed return is below the large-loss threshold.", "label"),
    "high_confidence_wrong_3d": ("boolean", "derived label", "True when confidence is high and three-event direction is wrong.", "label"),
    "future_price_7d": ("float", "future event payload", "Ticker price seven trading events after decision time.", "label"),
    "future_return_7d": ("float", "future event payload", "Raw ticker return seven trading events after decision time.", "label"),
    "future_signed_return_7d": ("float", "derived label", "Seven-event return aligned to BUY or SELL direction.", "label"),
    "directional_correct_7d": ("boolean", "derived label", "True when seven-event signed return is positive.", "label"),
    "profitable_7d": ("boolean", "derived label", "Whether the seven-event trade intent made money before costs.", "label"),
    "intent_mark_pnl_7d": ("float", "derived label", "Intent PnL using proposed quantity and seven-event mark.", "label"),
    "benchmark_future_price_7d": ("float", "future event payload", "Benchmark price seven trading events after decision time.", "label"),
    "benchmark_return_7d": ("float", "future event payload", "Benchmark return seven trading events after decision time.", "label"),
    "excess_return_vs_benchmark_7d": ("float", "derived label", "Seven-event signed return minus benchmark return.", "label"),
    "beat_benchmark_7d": ("boolean", "derived label", "True when seven-event signed return beats benchmark return.", "label"),
    "large_loss_7d": ("boolean", "derived label", "True when seven-event signed return is below the large-loss threshold.", "label"),
    "high_confidence_wrong_7d": ("boolean", "derived label", "True when confidence is high and seven-event direction is wrong.", "label"),
    "confidence_bucket": ("string", "derived feature", "Confidence bucket known at decision time.", "feature"),
    "event_best_long_ticker_1d": ("string", "future event payload", "Ticker with the best one-event long return in the replay universe.", "label"),
    "event_best_long_return_1d": ("float", "future event payload", "Best one-event long return in the replay universe.", "label"),
    "event_worst_ticker_1d": ("string", "future event payload", "Ticker with the worst one-event long return in the replay universe.", "label"),
    "event_worst_return_1d": ("float", "future event payload", "Worst one-event long return in the replay universe.", "label"),
    "event_best_abs_ticker_1d": ("string", "future event payload", "Ticker with the largest one-event absolute move.", "label"),
    "event_best_abs_return_1d": ("float", "future event payload", "Largest one-event absolute move in the replay universe.", "label"),
    "hold_missed_big_move_1d": ("boolean", "derived label", "For HOLD rows, true when the event had a large available move.", "label"),
    "headline_count": ("integer", "event payload", "Headline/context count visible at decision time.", "feature"),
    "real_headline_count": ("integer", "event payload", "Non-synthetic headline/context count.", "feature"),
    "synthetic_headline_count": ("integer", "event payload", "Synthetic headline/context count.", "feature"),
    "ticker_headline_count": ("integer", "event payload", "Visible headline count for the selected ticker.", "feature"),
    "macro_headline_count": ("integer", "derived", "Visible context rows classified as macro.", "feature"),
    "filing_headline_count": ("integer", "derived", "Visible context rows classified as SEC/filing context.", "feature"),
    "earnings_headline_count": ("integer", "derived", "Visible context rows classified as earnings context.", "feature"),
    "headline_source_count": ("integer", "derived", "Number of distinct visible headline sources.", "feature"),
    "headline_sources": ("string", "derived", "Semicolon-separated visible headline sources.", "feature"),
    "headline_age_minutes_min": ("float", "event payload", "Minimum visible headline age in minutes.", "feature"),
    "headline_age_minutes_avg": ("float", "event payload", "Average visible headline age in minutes.", "feature"),
    "has_real_news": ("boolean", "event payload", "Whether real context was visible.", "feature"),
    "has_synthetic_market_summary": ("boolean", "event payload", "Whether synthetic market summary text was visible.", "feature"),
    "news_context_quality": ("string", "derived", "no_context, synthetic_only, mixed, or news_enriched.", "feature"),
    "event_spy_return_1d": ("float", "market regime", "SPY one-day return known at event time.", "feature"),
    "event_qqq_return_1d": ("float", "market regime", "QQQ one-day return known at event time.", "feature"),
    "event_tlt_return_1d": ("float", "market regime", "TLT one-day return known at event time.", "feature"),
    "event_gld_return_1d": ("float", "market regime", "GLD one-day return known at event time.", "feature"),
    "event_risk_regime": ("string", "market regime", "Risk-on/risk-off classification.", "feature"),
    "event_trend_regime": ("string", "market regime", "Broad trend classification.", "feature"),
    "event_volatility_regime": ("string", "market regime", "Broad volatility classification.", "feature"),
    "event_breadth_proxy": ("float", "market regime", "Breadth proxy known at event time.", "feature"),
    "ticker_return_1d": ("float", "generated features", "Ticker one-day return known at event time.", "feature"),
    "ticker_return_5d": ("float", "generated features", "Ticker five-day return known at event time.", "feature"),
    "ticker_return_20d": ("float", "generated features", "Ticker twenty-day return known at event time.", "feature"),
    "ticker_rolling_volatility_20d": ("float", "generated features", "Ticker rolling volatility known at event time.", "feature"),
    "ticker_volume_ratio_20d": ("float", "generated features", "Ticker volume ratio known at event time.", "feature"),
    "ticker_gap_from_previous_close": ("float", "generated features", "Ticker gap from previous close known at event time.", "feature"),
    "ticker_distance_from_20d_ma": ("float", "generated features", "Ticker distance from 20-day MA known at event time.", "feature"),
}


def export_replay_ml_dataset(
    *,
    database_url: str,
    output_path: str | Path,
    dictionary_path: str | Path | None = None,
    summary_path: str | Path | None = None,
    run_ids: Optional[Iterable[str]] = None,
    input_fingerprint: Optional[str] = None,
    benchmark: str = DEFAULT_BENCHMARK,
    include_incomplete: bool = False,
) -> dict:
    """Load replay decisions, write a CSV dataset, and return a summary."""
    runs, decisions_by_run = load_replay_rows(
        database_url=database_url,
        run_ids=run_ids,
        input_fingerprint=input_fingerprint,
        include_incomplete=include_incomplete,
    )
    rows = build_replay_ml_rows(runs, decisions_by_run, benchmark=benchmark)
    write_replay_ml_csv(rows, output_path)
    if dictionary_path:
        write_feature_dictionary(dictionary_path)
    summary = summarize_replay_ml_rows(rows, runs, benchmark=benchmark)
    if summary_path:
        path = Path(summary_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary


def load_replay_rows(
    *,
    database_url: str,
    run_ids: Optional[Iterable[str]] = None,
    input_fingerprint: Optional[str] = None,
    include_incomplete: bool = False,
) -> tuple[list[dict], dict[str, list[dict]]]:
    """Read replay runs and decisions from the configured replay store."""
    store = ReplayStore(database_url)
    selected_ids = [str(run_id) for run_id in (run_ids or []) if str(run_id).strip()]

    with store.SessionLocal() as session:
        run_query = select(ReplayRunRecord)
        if selected_ids:
            run_query = run_query.where(ReplayRunRecord.id.in_(selected_ids))
        if input_fingerprint:
            run_query = run_query.where(ReplayRunRecord.input_fingerprint == input_fingerprint)
        if not include_incomplete:
            run_query = run_query.where(ReplayRunRecord.status == "completed")
        run_query = run_query.order_by(ReplayRunRecord.started_at.asc())
        run_records = list(session.scalars(run_query).all())

        runs = [_run_to_dict(row) for row in run_records]
        decisions_by_run: dict[str, list[dict]] = {}
        for run in run_records:
            decision_query = (
                select(ReplayDecisionRecord)
                .where(ReplayDecisionRecord.run_id == run.id)
                .order_by(
                    ReplayDecisionRecord.event_index.asc(),
                    ReplayDecisionRecord.id.asc(),
                )
            )
            decisions_by_run[run.id] = [
                _decision_to_dict(row)
                for row in session.scalars(decision_query).all()
            ]

    return runs, decisions_by_run


def build_replay_ml_rows(
    runs: Iterable[dict],
    decisions_by_run: dict[str, list[dict]],
    *,
    benchmark: str = DEFAULT_BENCHMARK,
) -> list[dict]:
    """Flatten replay decisions into one ML row per decision."""
    rows: list[dict] = []
    benchmark = str(benchmark or DEFAULT_BENCHMARK).upper()

    for run in runs:
        run_id = str(run.get("id"))
        decisions = decisions_by_run.get(run_id, [])
        event_payloads = _event_payloads_by_index(decisions)
        for decision in decisions:
            event = _as_dict(decision.get("event_payload"))
            event_index = _safe_int(decision.get("event_index"))
            future_events = {
                suffix: _future_event_payload(event_index, event_payloads, offset)
                for suffix, offset in DEFAULT_HORIZONS.items()
            }
            row = _decision_ml_row(run, decision, event, future_events, benchmark)
            rows.append({column: row.get(column, "") for column in REPLAY_ML_COLUMNS})

    rows.sort(key=lambda row: (str(row.get("as_of_time")), str(row.get("run_id")), int(row.get("decision_id") or 0)))
    return rows


def write_replay_ml_csv(rows: list[dict], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPLAY_ML_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in REPLAY_ML_COLUMNS})


def write_feature_dictionary(path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Replay ML Feature Dictionary v1",
        "",
        "Rows represent one replay decision. Feature columns are available at the",
        "decision timestamp. Label columns use future prices and must not be used as",
        "training features.",
        "",
        "| Column | Type | Source | Description | Leakage Risk |",
        "| --- | --- | --- | --- | --- |",
    ]
    for column in REPLAY_ML_COLUMNS:
        dtype, source, description, leakage = COLUMN_DICTIONARY[column]
        lines.append(f"| `{column}` | {dtype} | {source} | {description} | {leakage} |")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_replay_ml_rows(rows: list[dict], runs: Iterable[dict], *, benchmark: str) -> dict:
    run_rows = list(runs)
    action_counts = Counter(str(row.get("action") or "") for row in rows)
    provider_counts = Counter(str(row.get("llm_provider") or "unknown") for row in rows)
    trade_rows = [row for row in rows if str(row.get("action")).upper() in TRADE_ACTIONS]
    labeled_rows = [
        row
        for row in trade_rows
        if str(row.get("directional_correct_next_event")) in {"0", "1"}
    ]
    correct = sum(1 for row in labeled_rows if str(row.get("directional_correct_next_event")) == "1")
    beat_benchmark = [
        row for row in labeled_rows if str(row.get("beat_benchmark_next_event")) in {"0", "1"}
    ]
    horizon_summary = {}
    for suffix in DEFAULT_HORIZONS:
        direction_rows = [
            row for row in trade_rows if str(row.get(f"directional_correct_{suffix}")) in {"0", "1"}
        ]
        benchmark_rows = [
            row for row in trade_rows if str(row.get(f"beat_benchmark_{suffix}")) in {"0", "1"}
        ]
        pnl_values = [_to_float(row.get(f"intent_mark_pnl_{suffix}")) for row in trade_rows]
        pnl_values = [value for value in pnl_values if value is not None]
        horizon_summary[suffix] = {
            "labeled_trade_count": len(direction_rows),
            "directional_accuracy": _rate(
                sum(1 for row in direction_rows if str(row.get(f"directional_correct_{suffix}")) == "1"),
                len(direction_rows),
            ),
            "beat_benchmark_rate": _rate(
                sum(1 for row in benchmark_rows if str(row.get(f"beat_benchmark_{suffix}")) == "1"),
                len(benchmark_rows),
            ),
            "intent_mark_pnl": round(sum(pnl_values), 6) if pnl_values else None,
        }
    hold_rows = [row for row in rows if str(row.get("action")).upper() == "HOLD"]
    cost_summary = _cost_summary(rows)
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "mode": "replay",
        "benchmark": benchmark,
        "run_count": len(run_rows),
        "runs": [
            {
                "id": run.get("id"),
                "name": run.get("name"),
                "status": run.get("status"),
                "input_fingerprint": run.get("input_fingerprint"),
                "decision_count": run.get("decision_count"),
            }
            for run in run_rows
        ],
        "row_count": len(rows),
        "trade_row_count": len(trade_rows),
        "labeled_trade_row_count": len(labeled_rows),
        "directional_accuracy": _rate(correct, len(labeled_rows)),
        "beat_benchmark_rate": _rate(
            sum(1 for row in beat_benchmark if str(row.get("beat_benchmark_next_event")) == "1"),
            len(beat_benchmark),
        ),
        "horizon_summary": horizon_summary,
        "hold_row_count": len(hold_rows),
        "hold_missed_big_move_count": sum(
            1 for row in hold_rows if str(row.get("hold_missed_big_move_1d")) == "1"
        ),
        "action_counts": dict(sorted(action_counts.items())),
        "provider_counts": dict(sorted(provider_counts.items())),
        "cost_summary": cost_summary,
        "earliest_as_of_time": min((str(row.get("as_of_time")) for row in rows if row.get("as_of_time")), default=None),
        "latest_as_of_time": max((str(row.get("as_of_time")) for row in rows if row.get("as_of_time")), default=None),
    }


def _decision_ml_row(run: dict, decision: dict, event: dict, future_events: dict[str, dict | None], benchmark: str) -> dict:
    action = str(decision.get("action") or "HOLD").upper()
    ticker = str(decision.get("ticker") or "").upper().strip()
    quantity = _safe_int(decision.get("quantity")) or 0
    current_price = _event_price(event, ticker) if ticker else None
    next_event = future_events.get("1d")
    next_price = _event_price(next_event, ticker) if ticker and next_event else None
    ticker_return = _return(current_price, next_price)
    signed_return = _signed_return(action, ticker_return)
    mark_pnl = (
        round(float(signed_return) * float(current_price) * quantity, 6)
        if signed_return is not None and current_price is not None and quantity > 0
        else None
    )

    benchmark_price = _event_price(event, benchmark)
    benchmark_next_price = _event_price(next_event, benchmark) if next_event else None
    benchmark_return = _return(benchmark_price, benchmark_next_price)
    excess_return = (
        round(signed_return - benchmark_return, 8)
        if signed_return is not None and benchmark_return is not None
        else None
    )

    model_metadata = _as_dict(decision.get("model_metadata"))
    news = _news_features(event, ticker)
    market = _as_dict(event.get("market_regime"))
    ticker_features = _ticker_features(event, ticker)
    risk_approved = decision.get("risk_approved")
    confidence = _to_float(decision.get("confidence"))
    horizon_labels = _horizon_label_values(
        event=event,
        future_events=future_events,
        ticker=ticker,
        action=action,
        quantity=quantity,
        benchmark=benchmark,
        confidence=confidence,
    )
    opportunity = _event_opportunity_labels(event, next_event)

    return {
        "decision_id": decision.get("id"),
        "run_id": run.get("id"),
        "run_name": run.get("name"),
        "run_status": run.get("status"),
        "input_fingerprint": run.get("input_fingerprint"),
        "event_index": decision.get("event_index"),
        "as_of_time": _timestamp_string(decision.get("as_of_time")),
        "mode": "replay",
        "bot_id": decision.get("bot_id"),
        "bot_name": decision.get("bot_name"),
        "base_personality": model_metadata.get("base_personality") or _base_personality(decision.get("bot_name")),
        "llm_provider": decision.get("llm_provider"),
        "llm_input_tokens": _optional_int(decision.get("llm_input_tokens")),
        "llm_output_tokens": _optional_int(decision.get("llm_output_tokens")),
        "llm_total_tokens": _optional_int(decision.get("llm_total_tokens")),
        "llm_estimated_cost_usd": _round(decision.get("llm_estimated_cost_usd"), 8),
        "model": model_metadata.get("model"),
        "prompt_version": model_metadata.get("prompt_version"),
        "prompt_hash": model_metadata.get("prompt_hash"),
        "action": action,
        "hold_cause": decision.get("hold_cause") or "",
        "ticker": ticker,
        "quantity": quantity or "",
        "limit_price": _round(decision.get("limit_price")),
        "confidence": _round(confidence),
        "speculative": _bool_int(decision.get("speculative")),
        "reasoning_length": len(str(decision.get("reasoning") or "")),
        "headline_used": decision.get("headline_used") or "",
        "evidence_count": len(_as_list(decision.get("evidence_ids"))),
        "evidence_url_count": len(_as_list(decision.get("evidence_urls"))),
        "risk_checked": _bool_int(risk_approved is not None),
        "risk_approved": _bool_int(risk_approved) if risk_approved is not None else "",
        "risk_blocked": _bool_int(risk_approved is False),
        "risk_reason": decision.get("risk_reason") or "",
        "fill_count": _safe_int(decision.get("fill_count")) or 0,
        "fill_qty_total": _safe_int(decision.get("fill_qty_total")) or 0,
        "fill_avg_price": _round(decision.get("fill_avg_price")),
        "current_price": _round(current_price),
        "next_event_price": _round(next_price),
        "return_next_event": _round(ticker_return, 8),
        "signed_return_next_event": _round(signed_return, 8),
        "directional_correct_next_event": _bool_int(signed_return > 0) if signed_return is not None and action in TRADE_ACTIONS else "",
        "intent_mark_pnl_next_event": _round(mark_pnl),
        "benchmark_symbol": benchmark,
        "benchmark_price": _round(benchmark_price),
        "benchmark_next_event_price": _round(benchmark_next_price),
        "benchmark_return_next_event": _round(benchmark_return, 8),
        "excess_return_vs_benchmark_next_event": _round(excess_return, 8),
        "beat_benchmark_next_event": _bool_int(excess_return > 0) if excess_return is not None else "",
        **horizon_labels,
        "confidence_bucket": _confidence_bucket(confidence),
        **opportunity,
        "hold_missed_big_move_1d": _bool_int(
            action == "HOLD"
            and _to_float(opportunity.get("event_best_abs_return_1d")) is not None
            and abs(float(opportunity.get("event_best_abs_return_1d"))) >= BIG_MOVE_THRESHOLD
        ),
        **news,
        "event_spy_return_1d": _round(market.get("spy_return_1d"), 8),
        "event_qqq_return_1d": _round(market.get("qqq_return_1d"), 8),
        "event_tlt_return_1d": _round(market.get("tlt_return_1d"), 8),
        "event_gld_return_1d": _round(market.get("gld_return_1d"), 8),
        "event_risk_regime": market.get("risk_regime") or "",
        "event_trend_regime": market.get("trend_regime") or "",
        "event_volatility_regime": market.get("volatility_regime") or "",
        "event_breadth_proxy": _round(market.get("breadth_proxy"), 8),
        **ticker_features,
    }


def _event_payloads_by_index(decisions: list[dict]) -> dict[int, dict]:
    payloads = {}
    for decision in decisions:
        index = _safe_int(decision.get("event_index"))
        if index is None or index in payloads:
            continue
        payload = _as_dict(decision.get("event_payload"))
        if payload:
            payloads[index] = payload
    return payloads


def _future_event_payload(event_index: int | None, payloads: dict[int, dict], offset: int) -> dict | None:
    if event_index is None:
        return None
    ordered = sorted(payloads)
    future_indices = [index for index in ordered if index > event_index]
    if len(future_indices) < offset:
        return None
    return payloads.get(future_indices[offset - 1])


def _next_event_payload(event_index: int | None, payloads: dict[int, dict]) -> dict | None:
    return _future_event_payload(event_index, payloads, 1)


def _horizon_label_values(
    *,
    event: dict,
    future_events: dict[str, dict | None],
    ticker: str,
    action: str,
    quantity: int,
    benchmark: str,
    confidence: float | None,
) -> dict:
    output = {}
    current_price = _event_price(event, ticker) if ticker else None
    benchmark_price = _event_price(event, benchmark)
    for suffix, future_event in future_events.items():
        future_price = _event_price(future_event, ticker) if ticker and future_event else None
        ticker_return = _return(current_price, future_price)
        signed_return = _signed_return(action, ticker_return)
        mark_pnl = (
            round(float(signed_return) * float(current_price) * quantity, 6)
            if signed_return is not None and current_price is not None and quantity > 0
            else None
        )
        benchmark_future_price = _event_price(future_event, benchmark) if future_event else None
        benchmark_return = _return(benchmark_price, benchmark_future_price)
        excess_return = (
            round(signed_return - benchmark_return, 8)
            if signed_return is not None and benchmark_return is not None
            else None
        )
        directional_correct = signed_return > 0 if signed_return is not None and action in TRADE_ACTIONS else None
        output.update({
            f"future_price_{suffix}": _round(future_price),
            f"future_return_{suffix}": _round(ticker_return, 8),
            f"future_signed_return_{suffix}": _round(signed_return, 8),
            f"directional_correct_{suffix}": _bool_int(directional_correct) if directional_correct is not None else "",
            f"profitable_{suffix}": _bool_int(directional_correct) if directional_correct is not None else "",
            f"intent_mark_pnl_{suffix}": _round(mark_pnl),
            f"benchmark_future_price_{suffix}": _round(benchmark_future_price),
            f"benchmark_return_{suffix}": _round(benchmark_return, 8),
            f"excess_return_vs_benchmark_{suffix}": _round(excess_return, 8),
            f"beat_benchmark_{suffix}": _bool_int(excess_return > 0) if excess_return is not None else "",
            f"large_loss_{suffix}": _bool_int(signed_return <= LARGE_LOSS_THRESHOLD) if signed_return is not None else "",
            f"high_confidence_wrong_{suffix}": _bool_int(
                confidence is not None
                and confidence >= HIGH_CONFIDENCE_THRESHOLD
                and directional_correct is False
            ) if directional_correct is not None else "",
        })
    return output


def _event_opportunity_labels(event: dict, future_event: dict | None) -> dict:
    prices = _as_dict(event.get("prices"))
    returns = []
    for symbol, current_price in prices.items():
        ticker = str(symbol or "").upper()
        if not ticker or ticker in BENCHMARK_LIKE_SYMBOLS:
            continue
        future_price = _event_price(future_event, ticker) if future_event else None
        value = _return(_to_float(current_price), future_price)
        if value is not None:
            returns.append((ticker, value))
    if not returns:
        return {
            "event_best_long_ticker_1d": "",
            "event_best_long_return_1d": "",
            "event_worst_ticker_1d": "",
            "event_worst_return_1d": "",
            "event_best_abs_ticker_1d": "",
            "event_best_abs_return_1d": "",
        }
    best_long = max(returns, key=lambda item: item[1])
    worst = min(returns, key=lambda item: item[1])
    best_abs = max(returns, key=lambda item: abs(item[1]))
    return {
        "event_best_long_ticker_1d": best_long[0],
        "event_best_long_return_1d": _round(best_long[1], 8),
        "event_worst_ticker_1d": worst[0],
        "event_worst_return_1d": _round(worst[1], 8),
        "event_best_abs_ticker_1d": best_abs[0],
        "event_best_abs_return_1d": _round(abs(best_abs[1]), 8),
    }


def _confidence_bucket(confidence: float | None) -> str:
    if confidence is None:
        return "missing"
    if confidence < 0.4:
        return "low"
    if confidence < 0.7:
        return "medium"
    return "high"


def _news_features(event: dict, ticker: str) -> dict:
    coverage = _as_dict(event.get("news_coverage"))
    headlines = _collect_headlines(event, ticker)
    source_counter = Counter(
        str(item.get("source") or "").strip()
        for item in headlines
        if str(item.get("source") or "").strip()
    )
    ages = [
        float(item.get("age_minutes"))
        for item in headlines
        if _to_float(item.get("age_minutes")) is not None
    ]
    real_count = _safe_int(coverage.get("real_headline_count"))
    synthetic_count = _safe_int(coverage.get("synthetic_headline_count"))
    if real_count is None:
        real_count = sum(1 for item in headlines if not _is_synthetic_headline(item))
    if synthetic_count is None:
        synthetic_count = sum(1 for item in headlines if _is_synthetic_headline(item))
    headline_count = _safe_int(coverage.get("headline_count"))
    if headline_count is None:
        headline_count = len(headlines)

    return {
        "headline_count": headline_count,
        "real_headline_count": real_count,
        "synthetic_headline_count": synthetic_count,
        "ticker_headline_count": len(_ticker_headlines(event, ticker)) if ticker else 0,
        "macro_headline_count": _classified_count(headlines, ("federal reserve", "fomc", "cpi", "pce", "jobs", "payroll", "bureau of economic analysis", "bls", "rates", "macro")),
        "filing_headline_count": _classified_count(headlines, ("sec", "edgar", "10-k", "10-q", "8-k", "filing", "form ")),
        "earnings_headline_count": _classified_count(headlines, ("earnings", "quarter", "revenue", "guidance", "profit", "eps")),
        "headline_source_count": len(source_counter),
        "headline_sources": ";".join(sorted(source_counter)),
        "headline_age_minutes_min": _round(min(ages), 4) if ages else "",
        "headline_age_minutes_avg": _round(sum(ages) / len(ages), 4) if ages else "",
        "has_real_news": _bool_int(coverage.get("has_real_news") if "has_real_news" in coverage else real_count > 0),
        "has_synthetic_market_summary": _bool_int(
            coverage.get("has_synthetic_market_summary")
            if "has_synthetic_market_summary" in coverage
            else synthetic_count > 0
        ),
        "news_context_quality": _news_quality(real_count, synthetic_count),
    }


def _collect_headlines(event: dict, ticker: str) -> list[dict]:
    rows = []
    rows.extend(_headline_dicts(event.get("trending_headlines")))
    rows.extend(_headline_dicts(event.get("recent_headlines")))
    for value in (_as_dict(event.get("ticker_headlines")) or {}).values():
        rows.extend(_headline_dicts(value))
    rows.extend(_headline_dicts(event.get("source_events")))
    return _dedupe_headlines(rows)


def _ticker_headlines(event: dict, ticker: str) -> list[dict]:
    if not ticker:
        return []
    by_ticker = _as_dict(event.get("ticker_headlines"))
    value = by_ticker.get(ticker) or by_ticker.get(ticker.upper()) or by_ticker.get(ticker.lower())
    return _headline_dicts(value)


def _headline_dicts(value) -> list[dict]:
    rows = []
    for item in _as_list(value):
        if isinstance(item, str):
            rows.append({"title": item})
        elif isinstance(item, dict):
            rows.append(item)
    return rows


def _dedupe_headlines(rows: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for row in rows:
        key = (
            str(row.get("title") or ""),
            str(row.get("published_at") or ""),
            str(row.get("url") or ""),
            str(row.get("source") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _classified_count(headlines: list[dict], terms: tuple[str, ...]) -> int:
    count = 0
    for item in headlines:
        text = " ".join(
            str(item.get(key) or "")
            for key in ("title", "source", "replay_source", "form_type", "source_type")
        ).lower()
        if any(term in text for term in terms):
            count += 1
    return count


def _ticker_features(event: dict, ticker: str) -> dict:
    generated = _as_dict(event.get("generated_features"))
    features = _as_dict(generated.get(ticker) if ticker else {})
    return {
        "ticker_return_1d": _round(features.get("return_1d"), 8),
        "ticker_return_5d": _round(features.get("return_5d"), 8),
        "ticker_return_20d": _round(features.get("return_20d"), 8),
        "ticker_rolling_volatility_20d": _round(features.get("rolling_volatility_20d"), 8),
        "ticker_volume_ratio_20d": _round(features.get("volume_ratio_20d"), 8),
        "ticker_gap_from_previous_close": _round(features.get("gap_from_previous_close"), 8),
        "ticker_distance_from_20d_ma": _round(features.get("distance_from_20d_ma"), 8),
    }


def _event_price(event: dict | None, ticker: str) -> float | None:
    payload = _as_dict(event)
    prices = _as_dict(payload.get("prices"))
    benchmarks = _as_dict(payload.get("benchmark_prices"))
    ticker = str(ticker or "").upper()
    value = (
        prices.get(ticker)
        or prices.get(ticker.lower())
        or benchmarks.get(ticker)
        or benchmarks.get(ticker.lower())
    )
    return _to_float(value)


def _return(current: float | None, future: float | None) -> float | None:
    if current is None or future is None or current == 0:
        return None
    return round((future - current) / current, 8)


def _signed_return(action: str, ticker_return: float | None) -> float | None:
    if ticker_return is None or action not in TRADE_ACTIONS:
        return None
    return ticker_return if action == "BUY" else -ticker_return


def _news_quality(real_count: int, synthetic_count: int) -> str:
    if real_count > 0 and synthetic_count <= 0:
        return "news_enriched"
    if real_count > 0 and synthetic_count > 0:
        return "mixed"
    if synthetic_count > 0:
        return "synthetic_only"
    return "no_context"


def _is_synthetic_headline(row: dict) -> bool:
    return bool(row.get("synthetic")) or str(row.get("replay_source") or "").lower() == "derived_from_ohlcv"


def _base_personality(bot_name) -> str:
    if not bot_name:
        return ""
    return str(bot_name).split(" (", 1)[0]


def _run_to_dict(record: ReplayRunRecord) -> dict:
    return {
        "id": record.id,
        "name": record.name,
        "status": record.status,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "config": _as_dict(record.config),
        "input_fingerprint": record.input_fingerprint,
        "notes": record.notes,
        "decision_count": len(record.decisions or []),
    }


def _decision_to_dict(record: ReplayDecisionRecord) -> dict:
    return {
        "id": record.id,
        "run_id": record.run_id,
        "event_index": record.event_index,
        "as_of_time": record.as_of_time,
        "bot_id": record.bot_id,
        "bot_name": record.bot_name,
        "llm_provider": record.llm_provider,
        "action": record.action,
        "hold_cause": getattr(record, "hold_cause", None),
        "ticker": record.ticker,
        "quantity": record.quantity,
        "limit_price": record.limit_price,
        "reasoning": record.reasoning,
        "headline_used": record.headline_used,
        "confidence": record.confidence,
        "llm_input_tokens": getattr(record, "llm_input_tokens", None),
        "llm_output_tokens": getattr(record, "llm_output_tokens", None),
        "llm_total_tokens": getattr(record, "llm_total_tokens", None),
        "llm_estimated_cost_usd": getattr(record, "llm_estimated_cost_usd", None),
        "evidence_ids": _json_or_value(record.evidence_ids, []),
        "evidence_urls": _json_or_value(record.evidence_urls, []),
        "speculative": record.speculative == "true" if isinstance(record.speculative, str) else bool(record.speculative),
        "risk_approved": record.risk_approved,
        "risk_reason": record.risk_reason,
        "order_id": record.order_id,
        "fill_count": record.fill_count,
        "fill_qty_total": record.fill_qty_total,
        "fill_avg_price": record.fill_avg_price,
        "model_metadata": _json_or_value(record.model_metadata, {}),
        "portfolio_snapshot": _json_or_value(record.portfolio_snapshot, {}),
        "event_payload": _json_or_value(record.event_payload, {}),
    }


def _json_or_value(value, fallback):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return value if value is not None else fallback


def _as_dict(value) -> dict:
    value = _json_or_value(value, {})
    return value if isinstance(value, dict) else {}


def _as_list(value) -> list:
    value = _json_or_value(value, [])
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _to_float(value) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    if value in ("", None):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value):
    number = _safe_int(value)
    return number if number is not None else ""


def _round(value, digits: int = 6):
    number = _to_float(value)
    if number is None:
        return ""
    return round(number, digits)


def _bool_int(value) -> int:
    if isinstance(value, str):
        return 1 if value.lower() in {"1", "true", "yes"} else 0
    return 1 if bool(value) else 0


def _cost_summary(rows: list[dict]) -> dict:
    recorded_rows = []
    by_provider = {}
    for row in rows:
        cost = _to_float(row.get("llm_estimated_cost_usd"))
        if cost is None:
            continue
        provider = str(row.get("llm_provider") or "unknown")
        input_tokens = _safe_int(row.get("llm_input_tokens")) or 0
        output_tokens = _safe_int(row.get("llm_output_tokens")) or 0
        total_tokens = _safe_int(row.get("llm_total_tokens")) or input_tokens + output_tokens
        recorded_rows.append((provider, cost, input_tokens, output_tokens, total_tokens))
        provider_row = by_provider.setdefault(
            provider,
            {
                "recorded_cost_count": 0,
                "total_estimated_llm_cost_usd": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            },
        )
        provider_row["recorded_cost_count"] += 1
        provider_row["total_estimated_llm_cost_usd"] += cost
        provider_row["input_tokens"] += input_tokens
        provider_row["output_tokens"] += output_tokens
        provider_row["total_tokens"] += total_tokens

    for provider_row in by_provider.values():
        provider_row["total_estimated_llm_cost_usd"] = round(
            provider_row["total_estimated_llm_cost_usd"],
            8,
        )

    total_cost = sum(row[1] for row in recorded_rows)
    return {
        "available": bool(recorded_rows),
        "recorded_cost_count": len(recorded_rows),
        "missing_cost_count": max(0, len(rows) - len(recorded_rows)),
        "total_estimated_llm_cost_usd": round(total_cost, 8) if recorded_rows else None,
        "input_tokens": sum(row[2] for row in recorded_rows),
        "output_tokens": sum(row[3] for row in recorded_rows),
        "total_tokens": sum(row[4] for row in recorded_rows),
        "by_provider": dict(sorted(by_provider.items())),
    }


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def _timestamp_string(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)
