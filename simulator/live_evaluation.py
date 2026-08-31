"""No-LLM reporting for the focused live trading arena.

The report deliberately keeps live observations separate from replay runs. It
is a monitoring instrument until enough labeled outcomes exist for the chosen
horizon; it does not turn a small sample into a trading recommendation.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable

from config import BENCHMARK_TICKERS, TRADABLE_TICKERS
from evaluation import summarize_decisions
from outcomes import OUTCOME_HORIZONS, summarize_outcomes


DEFAULT_REPORT_HORIZON = "1d"
DEFAULT_REPORT_LOOKBACK_DAYS = 7
DEFAULT_REPORT_MIN_SAMPLES = 50
DEFAULT_REPORT_LIMIT = 10000
_COUNTERFACTUAL_STATUSES = {"profitable", "unprofitable", "flat"}
_RISK_MARKERS = (
    "risk check rejected",
    "risk rejected",
    "rejected original order",
    "risk limit",
)


def generate_live_evaluation_report(
    reasoning_log,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    period_days: int = DEFAULT_REPORT_LOOKBACK_DAYS,
    min_samples: int = DEFAULT_REPORT_MIN_SAMPLES,
    decision_limit: int = DEFAULT_REPORT_LIMIT,
    outcome_limit: int | None = None,
    horizon: str = DEFAULT_REPORT_HORIZON,
    now: datetime | None = None,
    include_markdown: bool = True,
    universe: Iterable[str] | None = None,
    benchmarks: Iterable[str] | None = None,
) -> dict:
    """Read stored live rows and build a report without calling an LLM."""
    report_now = _as_utc(now or datetime.now(timezone.utc))
    window_since, window_until = _resolve_window(
        since=since,
        until=until,
        now=report_now,
        period_days=period_days,
    )
    decision_limit = max(1, int(decision_limit or DEFAULT_REPORT_LIMIT))
    outcome_limit = max(1, int(outcome_limit or decision_limit * 5))
    decisions = _read_decisions(
        reasoning_log,
        limit=decision_limit,
        since=window_since,
        until=window_until,
    )
    outcomes = _read_outcomes(
        reasoning_log,
        limit=outcome_limit,
        since=window_since,
        until=window_until,
    )
    report = build_live_evaluation_report(
        decisions,
        outcomes,
        since=window_since,
        until=window_until,
        period_days=period_days,
        min_samples=min_samples,
        horizon=horizon,
        generated_at=report_now,
        universe=universe,
        benchmarks=benchmarks,
    )
    if include_markdown:
        report["markdown"] = render_live_evaluation_markdown(report)
    return report


def build_live_evaluation_report(
    decisions: Iterable[dict],
    outcomes: Iterable[dict],
    *,
    since: datetime,
    until: datetime,
    period_days: int = DEFAULT_REPORT_LOOKBACK_DAYS,
    min_samples: int = DEFAULT_REPORT_MIN_SAMPLES,
    horizon: str = DEFAULT_REPORT_HORIZON,
    generated_at: datetime | None = None,
    universe: Iterable[str] | None = None,
    benchmarks: Iterable[str] | None = None,
) -> dict:
    """Build a JSON-safe report from already loaded live decision rows."""
    generated = _as_utc(generated_at or datetime.now(timezone.utc))
    window_since = _as_utc(since)
    window_until = _as_utc(until)
    decision_rows = _filter_rows(decisions, "timestamp", window_since, window_until)
    outcome_rows = _filter_rows(
        outcomes,
        "observed_at",
        window_since,
        window_until,
        fallback_field="decision_timestamp",
    )
    selected_horizon = _normalize_horizon(horizon)
    selected_outcomes = (
        outcome_rows
        if selected_horizon == "all"
        else [row for row in outcome_rows if str(row.get("horizon") or "").lower() == selected_horizon]
    )

    decision_summary = summarize_decisions(decision_rows)
    outcome_summary = summarize_outcomes(outcome_rows)
    selected_outcome_summary = summarize_outcomes(selected_outcomes)
    labeled_ids = {
        str(row.get("decision_id"))
        for row in selected_outcomes
        if row.get("decision_id") is not None
    }
    labeled_count = len(labeled_ids) or len(selected_outcomes)
    decision_count = len(decision_rows)
    min_samples = max(1, int(min_samples or DEFAULT_REPORT_MIN_SAMPLES))
    sample_sufficient = labeled_count >= min_samples
    scope_universe = _symbols(universe or TRADABLE_TICKERS)
    scope_benchmarks = _symbols(benchmarks or BENCHMARK_TICKERS)

    report = {
        "report_type": "live_evaluation",
        "source": "live_decisions_and_outcomes",
        "mode": "decision_grade" if sample_sufficient else "monitoring_only",
        "generated_at": generated.isoformat(),
        "window": {
            "since": window_since.isoformat(),
            "until": window_until.isoformat(),
            "period_days": int(period_days or 0),
        },
        "sample": {
            "decision_count": decision_count,
            "outcome_label_count": len(selected_outcomes),
            "labeled_decision_count": labeled_count,
            "min_samples": min_samples,
            "sample_basis": "unique_decisions_with_selected_horizon_labels",
            "sample_sufficient": sample_sufficient,
            "remaining_labels_needed": max(0, min_samples - labeled_count),
        },
        "scope": {
            "tradable_tickers": scope_universe,
            "benchmark_tickers": scope_benchmarks,
            "observed_tradable_tickers": _observed_symbols(
                decision_rows, outcome_rows, scope_universe
            ),
            "observed_benchmark_tickers": _observed_symbols(
                decision_rows, outcome_rows, scope_benchmarks
            ),
        },
        "decisions": decision_summary,
        "outcomes": {
            "selected_horizon": selected_horizon,
            "selected": selected_outcome_summary,
            "all_horizons": outcome_summary,
        },
        "by_bot": _combined_groups(
            decision_summary.get("by_bot", {}),
            selected_outcome_summary.get("by_bot", {}),
        ),
        "by_provider": _combined_groups(
            decision_summary.get("by_provider", {}),
            selected_outcome_summary.get("by_provider", {}),
        ),
        "prompt_versions": _prompt_version_summary(decision_rows),
        "costs": _cost_summary(decision_rows),
        "risk_blocked": _risk_blocked_summary(decision_rows, outcome_rows),
        "benchmark_comparison": _benchmark_summary(
            outcome_rows,
            benchmarks=scope_benchmarks,
        ),
        "replay_reference": {
            "available": False,
            "status": "data_limited",
            "reason": (
                "Live rows are kept separate from replay runs; a same-input "
                "live/replay baseline has not been attached to this report."
            ),
        },
    }
    report["conclusion"] = _conclusion(report)
    return report


def write_live_evaluation_report(
    report: dict,
    output_dir: str | Path,
    *,
    basename: str | None = None,
) -> dict:
    """Write the report as JSON and Markdown and return the two paths."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    name = basename or _report_basename(report)
    json_path = directory / f"{name}.json"
    markdown_path = directory / f"{name}.md"
    payload = {key: value for key, value in report.items() if key != "markdown"}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    markdown = report.get("markdown") or render_live_evaluation_markdown(report)
    markdown_path.write_text(markdown, encoding="utf-8")
    return {
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def render_live_evaluation_markdown(report: dict) -> str:
    """Render a compact human-readable report from the JSON payload."""
    sample = report.get("sample") or {}
    window = report.get("window") or {}
    decisions = (report.get("decisions") or {}).get("totals") or {}
    outcomes = ((report.get("outcomes") or {}).get("selected") or {}).get("totals") or {}
    costs = report.get("costs") or {}
    status = str(report.get("mode") or "monitoring_only").replace("_", " ").title()
    outcome_win_rate = outcomes.get("win_rate") if outcomes.get("evaluated_trade_count", 0) else None
    outcome_net = outcomes.get("total_net_after_llm_cost") if outcomes.get("outcome_count", 0) else None
    lines = [
        "# Live Evaluation Report",
        "",
        f"**Status:** {status}",
        f"**Window:** {window.get('since', 'n/a')} to {window.get('until', 'n/a')}",
        (
            f"**Sample:** {sample.get('labeled_decision_count', 0)} labeled decisions "
            f"of {sample.get('decision_count', 0)} decisions; "
            f"minimum {sample.get('min_samples', 0)}"
        ),
        "",
        "## Decision Summary",
        "",
        "| Decisions | Trades | Holds | Cited trades | Filled trades |",
        "| ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {decisions.get('decision_count', 0)} | {decisions.get('trade_count', 0)} | "
            f"{decisions.get('hold_count', 0)} | "
            f"{_pct(decisions.get('citation_rate'))} | {_pct(decisions.get('fill_rate'))} |"
        ),
        "",
        f"## Outcomes ({report.get('outcomes', {}).get('selected_horizon', 'n/a')})",
        "",
        "| Labels | Evaluated trades | Wins | Losses | Win rate | Net after cost |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {outcomes.get('outcome_count', 0)} | {outcomes.get('evaluated_trade_count', 0)} | "
            f"{outcomes.get('profitable_count', 0)} | {outcomes.get('unprofitable_count', 0)} | "
            f"{_pct(outcome_win_rate)} | {_money(outcome_net)} |"
        ),
        "",
        "## Bot / Provider Readout",
        "",
        "| Group | Decisions | Trades | Labels | Win rate | Net after cost |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    group_rows = list((report.get("by_bot") or {}).items())
    if not group_rows:
        group_rows = list((report.get("by_provider") or {}).items())
    if group_rows:
        for group, row in group_rows:
            decisions_row = row.get("decisions") or {}
            outcomes_row = row.get("outcomes") or {}
            lines.append(
                f"| {group} | {decisions_row.get('decision_count', 0)} | "
                f"{decisions_row.get('trade_count', 0)} | {outcomes_row.get('outcome_count', 0)} | "
                f"{_pct(outcomes_row.get('win_rate'))} | {_money(outcomes_row.get('total_net_after_llm_cost'))} |"
            )
    else:
        lines.append("| No rows yet | 0 | 0 | 0 | n/a | n/a |")

    lines.extend([
        "",
        "## Cost",
        "",
        (
            f"Estimated LLM spend: **{_money(costs.get('total_estimated_cost_usd'), 4)}** "
            f"across {costs.get('llm_call_count', 0)} calls "
            f"({_money(costs.get('average_cost_per_call_usd'), 4)} per call)."
        ),
        "",
        "## Caveats",
        "",
        f"- {report.get('conclusion', {}).get('message', 'Monitoring only.')}",
        f"- {((report.get('risk_blocked') or {}).get('reason'))}",
        f"- {((report.get('benchmark_comparison') or {}).get('reason'))}",
        f"- {((report.get('replay_reference') or {}).get('reason'))}",
        "",
    ])
    return "\n".join(lines)


def _read_decisions(reasoning_log, *, limit: int, since: datetime, until: datetime) -> list[dict]:
    getter = getattr(reasoning_log, "get_decisions", None)
    if not callable(getter):
        return []
    return _call_getter(
        getter,
        {
            "bot_id": None,
            "action": None,
            "limit": limit,
            "since": since,
            "before": until,
        },
        fallback_kwargs={"limit": limit},
    )


def _read_outcomes(reasoning_log, *, limit: int, since: datetime, until: datetime) -> list[dict]:
    getter = getattr(reasoning_log, "get_decision_outcomes", None)
    if not callable(getter):
        return []
    return _call_getter(
        getter,
        {
            "bot_id": None,
            "horizon": None,
            "status": None,
            "limit": limit,
            "since": since,
            "before": until,
        },
        fallback_kwargs={"limit": limit},
    )


def _call_getter(getter, kwargs: dict, *, fallback_kwargs: dict) -> list[dict]:
    try:
        rows = getter(**kwargs)
    except TypeError:
        rows = getter(**fallback_kwargs)
    return [row for row in (rows or []) if isinstance(row, dict)]


def _resolve_window(*, since, until, now: datetime, period_days: int) -> tuple[datetime, datetime]:
    resolved_until = _as_utc(until or now)
    resolved_since = _as_utc(
        since or resolved_until - timedelta(days=max(1, int(period_days or DEFAULT_REPORT_LOOKBACK_DAYS)))
    )
    if resolved_since >= resolved_until:
        raise ValueError("live evaluation report window must have since before until")
    return resolved_since, resolved_until


def _filter_rows(
    rows: Iterable[dict],
    timestamp_field: str,
    since: datetime,
    until: datetime,
    *,
    fallback_field: str | None = None,
) -> list[dict]:
    selected = []
    for row in rows or []:
        timestamp = _as_utc(row.get(timestamp_field)) if row.get(timestamp_field) else None
        if timestamp is None and fallback_field:
            timestamp = _as_utc(row.get(fallback_field)) if row.get(fallback_field) else None
        if timestamp is None or not (since <= timestamp < until):
            continue
        selected.append(row)
    selected.sort(
        key=lambda row: _timestamp_value(
            row.get(timestamp_field) or (row.get(fallback_field) if fallback_field else None)
        ),
        reverse=True,
    )
    return selected


def _combined_groups(decision_groups: dict, outcome_groups: dict) -> dict:
    result = {}
    for key in sorted(set(decision_groups) | set(outcome_groups)):
        result[key] = {
            "decisions": decision_groups.get(key) or {},
            "outcomes": outcome_groups.get(key) or {},
        }
    return result


def _prompt_version_summary(decisions: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    labels = {}
    for row in decisions:
        metadata = row.get("model_metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        version = str(metadata.get("prompt_version") or "unknown")
        grouped[version].append(row)
        labels[version] = {
            "prompt_version": version,
            "model": metadata.get("model"),
            "provider": row.get("llm_provider") or metadata.get("provider"),
        }
    result = {}
    for version, rows in sorted(grouped.items()):
        result[version] = {
            **labels[version],
            **summarize_decisions(rows).get("totals", {}),
        }
    return result


def _cost_summary(decisions: list[dict]) -> dict:
    calls = [row for row in decisions if row.get("llm_call_made", True) is not False]
    known_values = []
    missing_count = 0
    for row in calls:
        value = row.get("llm_estimated_cost_usd")
        if value is None:
            missing_count += 1
            continue
        try:
            known_values.append(float(value))
        except (TypeError, ValueError):
            missing_count += 1
    total = sum(known_values)
    return {
        "llm_call_count": len(calls),
        "cost_observation_count": len(known_values),
        "missing_cost_count": missing_count,
        "cost_data_status": "complete" if not missing_count else "partial",
        "total_estimated_cost_usd": round(total, 8),
        "average_cost_per_call_usd": round(total / len(known_values), 8) if known_values else None,
        "cost_per_decision_usd": round(total / len(decisions), 8) if decisions else None,
    }


def _risk_blocked_summary(decisions: list[dict], outcomes: list[dict]) -> dict:
    records = {}
    for row in decisions:
        if not _is_risk_blocked(row):
            continue
        key = str(row.get("id") or f"decision-{len(records) + 1}")
        records[key] = _risk_record(row, outcome=None)
    for row in outcomes:
        if str(row.get("outcome_status") or "").lower() != "risk_rejected":
            continue
        key = str(row.get("decision_id") or f"outcome-{len(records) + 1}")
        records.setdefault(key, _risk_record(row, outcome=row))

    counterfactuals = []
    for row in outcomes:
        if str(row.get("outcome_status") or "").lower() != "risk_rejected":
            continue
        metadata = row.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("counterfactual_pnl") is not None:
            try:
                counterfactuals.append(float(metadata["counterfactual_pnl"]))
            except (TypeError, ValueError):
                pass
    return {
        "blocked_count": len(records),
        "available": bool(counterfactuals),
        "winner_count": sum(1 for value in counterfactuals if value > 0),
        "loser_count": sum(1 for value in counterfactuals if value < 0),
        "flat_count": sum(1 for value in counterfactuals if value == 0),
        "records": list(records.values())[:20],
        "reason": (
            "Counterfactual winner/loser marks are unavailable until risk-rejected "
            "orders store a forward mark; blocked orders are listed for review."
            if not counterfactuals
            else "Counterfactual marks were supplied by the outcome metadata."
        ),
    }


def _risk_record(row: dict, *, outcome: dict | None) -> dict:
    metadata = row.get("metadata") or {}
    risk_reason = row.get("risk_reason")
    if not risk_reason and isinstance(metadata, dict):
        risk_reason = metadata.get("risk_reason")
    return {
        "decision_id": row.get("id") if outcome is None else row.get("decision_id"),
        "timestamp": _iso_or_none(row.get("timestamp") or row.get("observed_at")),
        "bot_id": row.get("bot_id"),
        "bot_name": row.get("bot_name"),
        "llm_provider": row.get("llm_provider"),
        "action": row.get("action"),
        "ticker": row.get("ticker"),
        "hold_cause": row.get("hold_cause") or (metadata.get("hold_cause") if isinstance(metadata, dict) else None),
        "risk_reason": str(risk_reason or "unspecified")[:240],
    }


def _benchmark_summary(outcomes: list[dict], *, benchmarks: list[str]) -> dict:
    observations = []
    by_benchmark = {}
    comparison_count = 0
    for row in outcomes:
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            continue
        benchmark_returns = metadata.get("benchmark_returns")
        if not isinstance(benchmark_returns, dict):
            continue
        observations.append(benchmark_returns)
        trade_return = _trade_return(row)
        for benchmark in benchmarks:
            key = str(benchmark).upper()
            observation = benchmark_returns.get(key)
            if not isinstance(observation, dict):
                continue
            benchmark_return = _float_or_none(observation.get("return"))
            if benchmark_return is None:
                continue
            summary = by_benchmark.setdefault(key, {
                "observation_count": 0,
                "comparison_count": 0,
                "beat_count": 0,
                "lag_count": 0,
                "flat_count": 0,
                "_benchmark_returns": [],
                "_trade_returns": [],
                "_excess_returns": [],
            })
            summary["observation_count"] += 1
            summary["_benchmark_returns"].append(benchmark_return)
            if trade_return is None:
                continue
            excess_return = trade_return - benchmark_return
            comparison_count += 1
            summary["comparison_count"] += 1
            summary["_trade_returns"].append(trade_return)
            summary["_excess_returns"].append(excess_return)
            if excess_return > 0:
                summary["beat_count"] += 1
            elif excess_return < 0:
                summary["lag_count"] += 1
            else:
                summary["flat_count"] += 1

    for summary in by_benchmark.values():
        benchmark_values = summary.pop("_benchmark_returns")
        trade_values = summary.pop("_trade_returns")
        excess_values = summary.pop("_excess_returns")
        summary["beat_rate"] = _rate(summary["beat_count"], summary["comparison_count"])
        summary["avg_benchmark_return"] = round(mean(benchmark_values), 8) if benchmark_values else None
        summary["avg_trade_return"] = round(mean(trade_values), 8) if trade_values else None
        summary["avg_excess_return"] = round(mean(excess_values), 8) if excess_values else None

    if comparison_count:
        status = "available"
        reason = "Benchmark snapshots and evaluated trade returns were available for comparison."
    elif observations:
        status = "observations_only"
        reason = "Benchmark snapshots exist, but the window has no evaluated filled trades to compare."
    else:
        status = "data_limited"
        reason = "Live outcome rows do not yet store SPY/QQQ snapshots for this window, so beat/lag is not claimed."
    return {
        "available": bool(comparison_count),
        "status": status,
        "benchmarks": benchmarks,
        "observations": observations[:20],
        "comparison_count": comparison_count,
        "by_benchmark": by_benchmark,
        "reason": reason,
    }


def _trade_return(row: dict) -> float | None:
    if str(row.get("outcome_status") or "").lower() not in _COUNTERFACTUAL_STATUSES:
        return None
    pnl = _float_or_none(row.get("position_pnl"))
    entry_price = _float_or_none(row.get("entry_price"))
    filled_quantity = _float_or_none(row.get("filled_quantity"))
    if pnl is None or entry_price is None or filled_quantity is None:
        return None
    notional = abs(entry_price * filled_quantity)
    if notional <= 0:
        return None
    return pnl / notional


def _float_or_none(value) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _conclusion(report: dict) -> dict:
    sample = report.get("sample") or {}
    if not sample.get("sample_sufficient"):
        remaining = sample.get("remaining_labels_needed", 0)
        return {
            "status": "monitoring_only",
            "message": (
                f"Monitoring only: collect at least {remaining} more labeled "
                f"{report.get('outcomes', {}).get('selected_horizon', 'selected-horizon')} decisions "
                "before treating standings as decision-grade."
            ),
        }
    return {
        "status": "decision_grade_with_caveats",
        "message": (
            "The selected outcome-label threshold is met. Use bot/provider and "
            "prompt-version results as a live readout; benchmark and replay "
            "comparisons remain data-limited where marked."
        ),
    }


def _is_risk_blocked(row: dict) -> bool:
    if row.get("risk_approved") is False:
        return True
    hold_cause = str(row.get("hold_cause") or "").lower()
    if hold_cause == "risk_limit":
        return True
    metadata = row.get("metadata") or {}
    risk_reason = row.get("risk_reason")
    if isinstance(metadata, dict):
        risk_reason = risk_reason or metadata.get("risk_reason")
    text = " ".join(str(value or "").lower() for value in (row.get("reasoning"), risk_reason))
    return any(marker in text for marker in _RISK_MARKERS)


def _observed_symbols(decisions: list[dict], outcomes: list[dict], allowed: list[str]) -> list[str]:
    observed = {
        str(row.get("ticker") or "").upper()
        for row in [*decisions, *outcomes]
        if row.get("ticker")
    }
    return [ticker for ticker in allowed if ticker in observed]


def _symbols(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value).upper().strip() for value in values if str(value).strip()))


def _normalize_horizon(value: str | None) -> str:
    key = str(value or DEFAULT_REPORT_HORIZON).lower().strip()
    if key == "all" or key in OUTCOME_HORIZONS or key == "immediate":
        return key
    raise ValueError(f"unsupported live evaluation horizon: {value}")


def _as_utc(value) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        result = datetime.fromisoformat(text)
    else:
        raise ValueError(f"expected datetime, got {type(value).__name__}")
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _timestamp_value(value) -> float:
    try:
        return _as_utc(value).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _iso_or_none(value) -> str | None:
    if value is None:
        return None
    try:
        return _as_utc(value).isoformat()
    except (TypeError, ValueError):
        return str(value)


def _pct(value) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def _money(value, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    try:
        return f"${float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _report_basename(report: dict) -> str:
    generated = str(report.get("generated_at") or "")[:10] or "report"
    return f"live_evaluation_{generated}"
