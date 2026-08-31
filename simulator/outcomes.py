"""Decision outcome labeling for live bot decisions.

The reasoning log records what an agent proposed and what filled. This module
turns those records into horizon-based labels such as profitable, unprofitable,
risk_rejected, and not_filled.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Iterable

from config import BENCHMARK_TICKERS


OUTCOME_HORIZONS = {
    "1h": 60 * 60,
    "6h": 6 * 60 * 60,
    "1d": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
}

TERMINAL_NON_TRADE_STATUSES = {"risk_rejected", "no_trade", "execution_error"}
EVALUATED_TRADE_STATUSES = {"profitable", "unprofitable", "flat"}


def evaluate_due_outcomes(
    reasoning_log,
    price_feed,
    *,
    horizons: Iterable[str] | None = None,
    now: datetime | None = None,
    decision_limit: int = 1000,
) -> dict:
    """Create missing horizon outcome rows for decisions old enough to observe."""
    selected = _selected_horizons(horizons)
    now = _as_utc_datetime(now or datetime.now(timezone.utc))
    decisions = reasoning_log.get_decisions(limit=decision_limit)
    existing = reasoning_log.get_decision_outcomes(
        limit=max(decision_limit * (len(selected) + 1), 1000),
    )
    existing_keys = {
        (int(row["decision_id"]), str(row["horizon"]))
        for row in existing
        if row.get("decision_id") is not None
    }
    immediate_by_decision = {
        int(row["decision_id"]): row
        for row in existing
        if row.get("decision_id") is not None and row.get("horizon") == "immediate"
    }

    created = []
    skipped_not_due = 0
    skipped_existing = 0
    skipped_invalid = 0
    for decision in decisions:
        decision_id = _safe_int(decision.get("id"))
        decision_ts = _as_utc_datetime(decision.get("timestamp"))
        if decision_id is None:
            skipped_invalid += 1
            continue
        age_seconds = max(0.0, (now - decision_ts).total_seconds())
        immediate = immediate_by_decision.get(decision_id) or _fallback_immediate(decision)

        for horizon, horizon_seconds in selected.items():
            if age_seconds < horizon_seconds:
                skipped_not_due += 1
                continue
            key = (decision_id, horizon)
            if key in existing_keys:
                skipped_existing += 1
                continue

            payload = build_outcome_payload(
                decision,
                immediate,
                price_feed,
                horizon=horizon,
                horizon_seconds=horizon_seconds,
                observed_at=now,
            )
            if payload is None:
                skipped_invalid += 1
                continue
            outcome_id = reasoning_log.record_decision_outcome(**payload)
            if outcome_id is not None:
                payload["id"] = outcome_id
                created.append(payload)
                existing_keys.add(key)

    return {
        "created_count": len(created),
        "skipped_existing": skipped_existing,
        "skipped_not_due": skipped_not_due,
        "skipped_invalid": skipped_invalid,
        "horizons": selected,
        "outcomes": created,
    }


def build_outcome_payload(
    decision: dict,
    immediate: dict,
    price_feed,
    *,
    horizon: str,
    horizon_seconds: int,
    observed_at: datetime,
) -> dict | None:
    """Build one persisted outcome payload for a decision and horizon."""
    decision_id = _safe_int(decision.get("id"))
    if decision_id is None:
        return None

    action = str(immediate.get("action") or decision.get("action") or "HOLD").upper()
    ticker = _normalize_ticker(immediate.get("ticker") or decision.get("ticker"))
    filled_quantity = max(
        _safe_int(decision.get("fill_qty_total")) or 0,
        _safe_int(immediate.get("filled_quantity")) or 0,
    )
    entry_price = _safe_float(decision.get("fill_avg_price"))
    if entry_price is None:
        entry_price = _safe_float(immediate.get("entry_price"))
    mark_price = _mark_price(price_feed, ticker)
    baseline_value = _safe_float(immediate.get("portfolio_value_at_decision"))
    if baseline_value is None:
        baseline_value = _portfolio_value(decision.get("portfolio_snapshot") or {})
    llm_cost = (
        _safe_float(decision.get("llm_estimated_cost_usd"))
        if decision.get("llm_estimated_cost_usd") is not None
        else _safe_float(immediate.get("llm_estimated_cost_usd"))
    ) or 0.0

    base_status = str(immediate.get("outcome_status") or "").lower()
    if base_status in TERMINAL_NON_TRADE_STATUSES:
        outcome_status = base_status
        position_pnl = 0.0
    elif filled_quantity <= 0 or entry_price is None:
        outcome_status = "not_filled"
        position_pnl = 0.0
    else:
        position_pnl = _position_pnl(
            action=action,
            filled_quantity=filled_quantity,
            entry_price=entry_price,
            mark_price=mark_price,
        )
        outcome_status = _profit_status(position_pnl)

    portfolio_delta = position_pnl
    observed_value = (
        round(baseline_value + portfolio_delta, 8)
        if baseline_value is not None and portfolio_delta is not None
        else None
    )
    return {
        "decision_id": decision_id,
        "bot_id": decision.get("bot_id") or immediate.get("bot_id"),
        "bot_name": decision.get("bot_name") or immediate.get("bot_name"),
        "llm_provider": decision.get("llm_provider") or immediate.get("llm_provider"),
        "decision_timestamp": decision.get("timestamp") or immediate.get("decision_timestamp"),
        "horizon": horizon,
        "horizon_seconds": horizon_seconds,
        "observed_at": observed_at,
        "action": action,
        "ticker": ticker,
        "quantity": decision.get("quantity") or immediate.get("quantity"),
        "entry_price": entry_price,
        "mark_price": mark_price,
        "portfolio_value_at_decision": baseline_value,
        "portfolio_value_at_observation": observed_value,
        "position_pnl": position_pnl,
        "portfolio_delta": portfolio_delta,
        "llm_estimated_cost_usd": llm_cost,
        "net_after_llm_cost": (
            round(portfolio_delta - llm_cost, 8)
            if portfolio_delta is not None
            else None
        ),
        "filled_quantity": filled_quantity,
        "risk_approved": immediate.get("risk_approved"),
        "outcome_status": outcome_status,
        "metadata": _outcome_metadata(immediate, price_feed),
    }


def summarize_outcomes(outcomes: Iterable[dict]) -> dict:
    """Aggregate persisted outcome rows into dashboard/API metrics."""
    rows = list(outcomes)
    by_provider = {}
    for provider, provider_rows in _group_by(rows, "llm_provider").items():
        by_provider[provider] = _summarize_outcome_group(provider_rows)

    by_bot = {}
    for bot_id, bot_rows in _group_by(rows, "bot_id").items():
        summary = _summarize_outcome_group(bot_rows)
        summary["bot_name"] = bot_rows[0].get("bot_name") if bot_rows else None
        summary["llm_provider"] = bot_rows[0].get("llm_provider") if bot_rows else None
        by_bot[bot_id] = summary

    by_horizon = {}
    for horizon, horizon_rows in _group_by(rows, "horizon").items():
        by_horizon[horizon] = _summarize_outcome_group(horizon_rows)

    return {
        "totals": _summarize_outcome_group(rows),
        "by_provider": by_provider,
        "by_bot": by_bot,
        "by_horizon": by_horizon,
    }


def _summarize_outcome_group(rows: list[dict]) -> dict:
    status_counts = Counter(str(row.get("outcome_status") or "unknown") for row in rows)
    evaluated = [
        row for row in rows
        if str(row.get("outcome_status") or "") in EVALUATED_TRADE_STATUSES
    ]
    profitable = [
        row for row in evaluated
        if str(row.get("outcome_status")) == "profitable"
    ]
    pnl_values = [
        float(row.get("position_pnl"))
        for row in evaluated
        if row.get("position_pnl") is not None
    ]
    net_values = [
        float(row.get("net_after_llm_cost"))
        for row in rows
        if row.get("net_after_llm_cost") is not None
    ]
    total_cost = sum(float(row.get("llm_estimated_cost_usd") or 0.0) for row in rows)
    return {
        "outcome_count": len(rows),
        "evaluated_trade_count": len(evaluated),
        "profitable_count": status_counts.get("profitable", 0),
        "unprofitable_count": status_counts.get("unprofitable", 0),
        "flat_count": status_counts.get("flat", 0),
        "not_filled_count": status_counts.get("not_filled", 0),
        "risk_rejected_count": status_counts.get("risk_rejected", 0),
        "no_trade_count": status_counts.get("no_trade", 0),
        "execution_error_count": status_counts.get("execution_error", 0),
        "win_rate": _rate(len(profitable), len(evaluated)),
        "avg_position_pnl": round(mean(pnl_values), 8) if pnl_values else None,
        "total_position_pnl": round(sum(pnl_values), 8),
        "avg_net_after_llm_cost": round(mean(net_values), 8) if net_values else None,
        "total_net_after_llm_cost": round(sum(net_values), 8),
        "total_llm_estimated_cost_usd": round(total_cost, 8),
        "cost_per_profitable_decision": (
            round(total_cost / len(profitable), 8)
            if profitable else None
        ),
        "status_counts": dict(status_counts),
    }


def _fallback_immediate(decision: dict) -> dict:
    action = str(decision.get("action") or "HOLD").upper()
    filled_quantity = _safe_int(decision.get("fill_qty_total")) or 0
    if action == "HOLD":
        status = "no_trade"
    elif filled_quantity > 0:
        status = "filled"
    else:
        status = "not_filled"
    return {
        "decision_id": decision.get("id"),
        "bot_id": decision.get("bot_id"),
        "bot_name": decision.get("bot_name"),
        "llm_provider": decision.get("llm_provider"),
        "decision_timestamp": decision.get("timestamp"),
        "horizon": "immediate",
        "horizon_seconds": 0,
        "action": action,
        "ticker": decision.get("ticker"),
        "quantity": decision.get("quantity"),
        "entry_price": decision.get("fill_avg_price"),
        "filled_quantity": filled_quantity,
        "risk_approved": None,
        "outcome_status": status,
        "portfolio_value_at_decision": _portfolio_value(decision.get("portfolio_snapshot") or {}),
        "llm_estimated_cost_usd": decision.get("llm_estimated_cost_usd"),
    }


def _selected_horizons(horizons: Iterable[str] | None) -> dict[str, int]:
    if horizons is None:
        return dict(OUTCOME_HORIZONS)
    selected = {}
    for value in horizons:
        key = str(value or "").lower().strip()
        if key in OUTCOME_HORIZONS:
            selected[key] = OUTCOME_HORIZONS[key]
    return selected or dict(OUTCOME_HORIZONS)


def _group_by(rows: list[dict], field: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)
    return dict(sorted(grouped.items()))


def _benchmark_prices_from_immediate(immediate: dict) -> dict[str, float]:
    metadata = immediate.get("metadata") or {}
    if not isinstance(metadata, dict):
        return {}
    prices = metadata.get("benchmark_prices_at_decision") or {}
    if not isinstance(prices, dict):
        return {}
    result = {}
    for ticker in BENCHMARK_TICKERS:
        value = _safe_float(prices.get(ticker))
        if value is not None and value > 0:
            result[str(ticker).upper()] = value
    return result


def _benchmark_prices(price_feed) -> dict[str, float]:
    getter = getattr(price_feed, "get_price", None)
    if not callable(getter):
        return {}
    prices = {}
    for ticker in BENCHMARK_TICKERS:
        try:
            value = float(getter(ticker))
        except Exception:
            continue
        if value > 0:
            prices[str(ticker).upper()] = round(value, 8)
    return prices


def _benchmark_returns(start_prices: dict, end_prices: dict) -> dict[str, dict]:
    returns = {}
    for ticker in BENCHMARK_TICKERS:
        key = str(ticker).upper()
        start = _safe_float(start_prices.get(key))
        end = _safe_float(end_prices.get(key))
        if start is None or end is None or start <= 0:
            continue
        returns[key] = {
            "start_price": round(start, 8),
            "end_price": round(end, 8),
            "return": round((end / start) - 1.0, 8),
        }
    return returns


def _outcome_metadata(immediate: dict, price_feed) -> dict:
    metadata = {
        "source": "outcome_evaluator",
        "immediate_outcome_status": immediate.get("outcome_status"),
    }
    benchmark_prices_at_decision = _benchmark_prices_from_immediate(immediate)
    benchmark_prices_at_observation = _benchmark_prices(price_feed)
    benchmark_returns = _benchmark_returns(
        benchmark_prices_at_decision,
        benchmark_prices_at_observation,
    )
    if benchmark_prices_at_decision:
        metadata["benchmark_prices_at_decision"] = benchmark_prices_at_decision
    if benchmark_prices_at_observation:
        metadata["benchmark_prices_at_observation"] = benchmark_prices_at_observation
    if benchmark_returns:
        metadata["benchmark_returns"] = benchmark_returns
    return metadata


def _profit_status(position_pnl: float | None) -> str:
    if position_pnl is None:
        return "pending"
    if position_pnl > 0:
        return "profitable"
    if position_pnl < 0:
        return "unprofitable"
    return "flat"


def _position_pnl(
    *,
    action: str,
    filled_quantity: int,
    entry_price: float | None,
    mark_price: float | None,
) -> float | None:
    if entry_price is None or mark_price is None or filled_quantity <= 0:
        return None
    side = str(action or "").upper()
    if side not in {"BUY", "SELL"}:
        return None
    signed_quantity = filled_quantity if side == "BUY" else -filled_quantity
    return round((float(mark_price) - float(entry_price)) * signed_quantity, 8)


def _mark_price(price_feed, ticker: str | None) -> float | None:
    if not ticker:
        return None
    try:
        return round(float(price_feed.get_price(ticker)), 8)
    except Exception:
        return None


def _portfolio_value(snapshot: dict) -> float | None:
    if not isinstance(snapshot, dict):
        return None
    value = _safe_float(snapshot.get("total_value"))
    if value is not None:
        return round(value, 8)
    cash = _safe_float(snapshot.get("cash"))
    positions = snapshot.get("positions") or {}
    cost_basis = snapshot.get("cost_basis") or {}
    if cash is None or not isinstance(positions, dict):
        return None
    total = cash
    for ticker, quantity in positions.items():
        basis = _safe_float(cost_basis.get(ticker)) or 0.0
        total += basis * int(quantity or 0)
    return round(total, 8)


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_ticker(value) -> str | None:
    if value is None:
        return None
    ticker = str(value).upper().strip()
    return ticker if ticker else None


def _as_utc_datetime(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)
