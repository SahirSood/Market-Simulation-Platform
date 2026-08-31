"""Phase D evaluation helpers for decisions, evidence, and retrieval quality."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean
from typing import Iterable, Optional


TRADE_ACTIONS = {"BUY", "SELL"}
ACTION_BUCKETS = ("BUY", "SELL", "HOLD")
HOLD_CAUSE_BUCKETS = (
    "no_edge",
    "weak_evidence",
    "risk_reward",
    "risk_limit",
    "cost_control",
    "market_hours",
    "budget",
    "invalid_output",
    "guardrail",
    "error",
    "unknown",
)
_HOLD_CAUSE_SET = set(HOLD_CAUSE_BUCKETS)
RISK_REJECTION_MARKERS = (
    "risk check rejected",
    "risk rejected",
    "rejected original order",
)


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _is_trade(decision: dict) -> bool:
    return str(decision.get("action", "")).upper() in TRADE_ACTIONS


def decision_evidence_status(decision: dict) -> str:
    """
    Classify a decision by how it used evidence.

    The categories are intentionally small enough for dashboards:
    - hold: no trade attempted
    - evidence_backed: trade cites evidence and is not marked speculative
    - speculative_evidence_backed: trade cites evidence but is still speculative
    - speculative: trade is explicitly speculative and cites no evidence
    - unsupported: trade cites no evidence and is not marked speculative
    """
    if not _is_trade(decision):
        return "hold"

    has_citation = bool(_as_list(decision.get("evidence_ids")))
    speculative = bool(decision.get("speculative", False))

    if has_citation and speculative:
        return "speculative_evidence_backed"
    if has_citation:
        return "evidence_backed"
    if speculative:
        return "speculative"
    return "unsupported"


def summarize_decisions(decisions: Iterable[dict]) -> dict:
    """Return aggregate evidence/citation metrics for logged bot decisions."""
    rows = list(decisions)
    totals = _summarize_group(rows)

    by_provider = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("llm_provider") or "unknown")].append(row)
    for provider, provider_rows in sorted(grouped.items()):
        by_provider[provider] = _summarize_group(provider_rows)

    by_bot = {}
    bot_grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = str(row.get("bot_id") or row.get("bot_name") or "unknown")
        bot_grouped[key].append(row)
    for bot_id, bot_rows in sorted(bot_grouped.items()):
        bot_summary = _summarize_group(bot_rows)
        bot_summary["bot_name"] = bot_rows[0].get("bot_name")
        bot_summary["llm_provider"] = bot_rows[0].get("llm_provider")
        by_bot[bot_id] = bot_summary

    return {
        "totals": totals,
        "by_provider": by_provider,
        "by_bot": by_bot,
    }


def _summarize_group(rows: list[dict]) -> dict:
    trade_rows = [row for row in rows if _is_trade(row)]
    hold_count = len(rows) - len(trade_rows)

    status_counts = {
        "hold": 0,
        "evidence_backed": 0,
        "speculative_evidence_backed": 0,
        "speculative": 0,
        "unsupported": 0,
    }
    for row in rows:
        status_counts[decision_evidence_status(row)] += 1
    hold_cause_counts = _hold_cause_counts(rows)

    cited_trade_count = sum(
        1 for row in trade_rows if bool(_as_list(row.get("evidence_ids")))
    )
    evidence_backed_trade_count = (
        status_counts["evidence_backed"]
        + status_counts["speculative_evidence_backed"]
    )
    speculative_trade_count = (
        status_counts["speculative"]
        + status_counts["speculative_evidence_backed"]
    )
    filled_trade_count = sum(
        1 for row in trade_rows if int(row.get("fill_qty_total") or 0) > 0
    )

    confidences = [
        float(row["confidence"])
        for row in rows
        if row.get("confidence") is not None
    ]
    unique_evidence_urls = {
        url
        for row in rows
        for url in _as_list(row.get("evidence_urls"))
        if url
    }

    return {
        "decision_count": len(rows),
        "trade_count": len(trade_rows),
        "hold_count": hold_count,
        "evidence_backed_trade_count": evidence_backed_trade_count,
        "speculative_trade_count": speculative_trade_count,
        "unsupported_trade_count": status_counts["unsupported"],
        "citation_count": sum(len(_as_list(row.get("evidence_ids"))) for row in rows),
        "unique_evidence_url_count": len(unique_evidence_urls),
        "citation_rate": _rate(cited_trade_count, len(trade_rows)),
        "unsupported_trade_rate": _rate(status_counts["unsupported"], len(trade_rows)),
        "speculative_trade_rate": _rate(speculative_trade_count, len(trade_rows)),
        "fill_rate": _rate(filled_trade_count, len(trade_rows)),
        "avg_confidence": round(mean(confidences), 4) if confidences else None,
        "status_counts": status_counts,
        "hold_cause_counts": hold_cause_counts,
    }


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def compare_model_groups(decisions: Iterable[dict], group_by: str = "llm_provider") -> list[dict]:
    """Compare evidence and trading metrics across providers or other fields."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in decisions:
        grouped[str(row.get(group_by) or "unknown")].append(row)

    comparison = []
    for group, rows in sorted(grouped.items()):
        summary = _summarize_group(rows)
        comparison.append({"group": group, **summary})
    comparison.sort(
        key=lambda row: (
            row["citation_rate"],
            -row["unsupported_trade_rate"],
            row["fill_rate"],
        ),
        reverse=True,
    )
    return comparison


def summarize_bot_behavior(decisions: Iterable[dict]) -> dict:
    """Return per-bot behavior analytics for logged decisions."""
    rows = list(decisions)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = str(row.get("bot_id") or row.get("bot_name") or "unknown")
        grouped[key].append(row)

    bots = [
        _summarize_bot_behavior_group(bot_id, bot_rows)
        for bot_id, bot_rows in grouped.items()
    ]
    bots.sort(
        key=lambda row: (
            row["decision_count"],
            _timestamp_sort_value(row.get("last_decision_at")),
            row["bot_id"],
        ),
        reverse=True,
    )

    return {
        "bot_count": len(bots),
        "decision_count": len(rows),
        "bots": bots,
    }


def get_bot_behavior_detail(decisions: Iterable[dict]) -> dict:
    """Return one bot's aggregate behavior plus a chronological decision timeline."""
    rows = list(decisions)
    if not rows:
        return {
            "bot": None,
            "timeline": [],
        }

    bot_id = str(rows[0].get("bot_id") or rows[0].get("bot_name") or "unknown")
    chronological = _chronological(rows)
    summary = _summarize_bot_behavior_group(bot_id, rows)
    timeline = [_timeline_row(row) for row in chronological]
    return {
        "bot": summary,
        "timeline": timeline,
    }


def list_risk_rejections(decisions: Iterable[dict], limit: int = 100) -> dict:
    """Return recent decisions whose reasoning indicates scheduler/tool rejection."""
    rows = [
        _timeline_row(row)
        for row in _chronological(list(decisions))
        if _is_risk_rejection(row)
    ]
    rows.reverse()
    return {
        "risk_rejection_count": len(rows),
        "decisions": rows[:limit],
    }


def compare_replay_runs(runs: Iterable[dict], decisions_by_run: dict[str, list[dict]]) -> dict:
    """Compare replay runs that share the same input fingerprint."""
    run_rows = list(runs)
    run_comparisons = []
    provider_rows = []
    personality_rows = []

    for run in run_rows:
        run_id = str(run.get("id"))
        decisions = decisions_by_run.get(run_id, [])
        run_summary = _summarize_replay_run(run, decisions)
        run_comparisons.append(run_summary)

        for provider, rows in _group_by(decisions, "llm_provider").items():
            provider_summary = _summarize_group(rows)
            replay_summary = _summarize_replay_decisions(rows)
            provider_rows.append({
                "run_id": run_id,
                "run_name": run.get("name"),
                "provider": provider,
                **provider_summary,
                **replay_summary,
            })

        personality_groups: dict[str, list[dict]] = defaultdict(list)
        for row in decisions:
            personality_groups[_base_personality(row.get("bot_name")) or "unknown"].append(row)
        for personality, rows in sorted(personality_groups.items()):
            personality_summary = _summarize_group(rows)
            replay_summary = _summarize_replay_decisions(rows)
            personality_rows.append({
                "run_id": run_id,
                "run_name": run.get("name"),
                "base_personality": personality,
                **personality_summary,
                **replay_summary,
            })

    run_comparisons.sort(
        key=lambda row: (
            row["metrics"]["final_portfolio_value"] is not None,
            row["metrics"]["final_portfolio_value"] or 0.0,
            row["metrics"]["citation_rate"],
            -row["metrics"]["unsupported_trade_rate"],
        ),
        reverse=True,
    )

    return {
        "input_fingerprint": run_rows[0].get("input_fingerprint") if run_rows else None,
        "run_count": len(run_rows),
        "runs": run_comparisons,
        "by_provider": provider_rows,
        "by_personality": personality_rows,
    }


def _summarize_replay_run(run: dict, decisions: list[dict]) -> dict:
    evidence_summary = _summarize_group(decisions)
    replay_summary = _summarize_replay_decisions(decisions)
    return {
        "run": run,
        "metrics": {
            **evidence_summary,
            **replay_summary,
        },
        "provider_comparison": compare_model_groups(decisions, group_by="llm_provider"),
    }


def _summarize_replay_decisions(rows: list[dict]) -> dict:
    risk_checked = [
        row for row in rows if row.get("risk_approved") is not None
    ]
    risk_rejected = [
        row for row in risk_checked if row.get("risk_approved") is False
    ]
    filled_quantity = sum(int(row.get("fill_qty_total") or 0) for row in rows)
    portfolio_summary = _portfolio_comparison_summary(rows)
    action_counts = {bucket: 0 for bucket in ACTION_BUCKETS}
    for action, count in Counter(_action(row) for row in rows).items():
        action_counts[action] = count
    return {
        "action_counts": action_counts,
        "risk_checked_count": len(risk_checked),
        "risk_rejection_count": len(risk_rejected),
        "risk_rejection_rate": _rate(len(risk_rejected), len(risk_checked)),
        "filled_quantity": filled_quantity,
        **_replay_directional_summary(rows),
        **portfolio_summary,
    }


def _replay_directional_summary(rows: list[dict]) -> dict:
    scored = []
    skipped = 0
    for row in rows:
        scored_row = _score_replay_decision(row, rows)
        if scored_row is None:
            if _is_trade(row):
                skipped += 1
            continue
        scored.append(scored_row)

    approved = [row for row in scored if row["risk_approved"] is not False]
    rejected = [row for row in scored if row["risk_approved"] is False]
    correct = [row for row in scored if row["correct"]]
    approved_correct = [row for row in approved if row["correct"]]

    return {
        "directional_scored_count": len(scored),
        "directional_skipped_count": skipped,
        "directional_correct_count": len(correct),
        "directional_accuracy": _rate(len(correct), len(scored)),
        "approved_directional_scored_count": len(approved),
        "approved_directional_correct_count": len(approved_correct),
        "approved_directional_accuracy": _rate(len(approved_correct), len(approved)),
        "intent_mark_pnl": round(sum(row["mark_pnl"] for row in scored), 4),
        "approved_intent_mark_pnl": round(sum(row["mark_pnl"] for row in approved), 4),
        "risk_blocked_mark_pnl": round(sum(row["mark_pnl"] for row in rejected), 4),
    }


def _score_replay_decision(row: dict, rows: list[dict]) -> dict | None:
    action = _action(row)
    if action not in TRADE_ACTIONS:
        return None
    ticker = str(row.get("ticker") or "").upper().strip()
    quantity = int(row.get("quantity") or 0)
    if not ticker or quantity <= 0:
        return None

    current_price = _event_price(row, ticker)
    next_price = _next_replay_price(row, rows, ticker)
    if current_price is None or next_price is None:
        return None

    if action == "BUY":
        mark_pnl = (next_price - current_price) * quantity
    else:
        mark_pnl = (current_price - next_price) * quantity
    return {
        "action": action,
        "ticker": ticker,
        "quantity": quantity,
        "current_price": current_price,
        "next_price": next_price,
        "mark_pnl": round(mark_pnl, 4),
        "correct": mark_pnl > 0,
        "risk_approved": row.get("risk_approved"),
    }


def _next_replay_price(row: dict, rows: list[dict], ticker: str) -> float | None:
    event_index = _safe_int(row.get("event_index"))
    if event_index is None:
        return None
    candidates = []
    for candidate in rows:
        candidate_index = _safe_int(candidate.get("event_index"))
        if candidate_index is None or candidate_index <= event_index:
            continue
        price = _event_price(candidate, ticker)
        if price is not None:
            candidates.append((candidate_index, price))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _event_price(row: dict, ticker: str) -> float | None:
    payload = row.get("event_payload") or {}
    prices = payload.get("prices") if isinstance(payload, dict) else {}
    if not isinstance(prices, dict):
        return None
    value = prices.get(ticker) or prices.get(str(ticker).upper()) or prices.get(str(ticker).lower())
    return _to_float(value)


def _portfolio_comparison_summary(rows: list[dict]) -> dict:
    by_bot: dict[str, list[dict]] = defaultdict(list)
    for row in _chronological(rows):
        by_bot[str(row.get("bot_id") or row.get("bot_name") or "unknown")].append(row)

    starting_value = 0.0
    final_value = 0.0
    values_found = False
    per_bot = []
    for bot_id, bot_rows in sorted(by_bot.items()):
        series = _portfolio_series(bot_rows)
        if not series:
            continue
        values_found = True
        start = series[0]["total_value"]
        final = series[-1]["total_value"]
        starting_value += start
        final_value += final
        per_bot.append({
            "bot_id": bot_id,
            "bot_name": bot_rows[-1].get("bot_name"),
            "starting_value": start,
            "final_value": final,
            "value_change": round(final - start, 4),
        })

    if not values_found:
        return {
            "starting_portfolio_value": None,
            "final_portfolio_value": None,
            "portfolio_value_change": None,
            "max_drawdown": None,
            "portfolio_by_bot": [],
        }

    aggregate_points = []
    for row in _chronological(rows):
        value = _portfolio_value(row.get("portfolio_snapshot") or {})
        if value is not None:
            aggregate_points.append(value)
    peak = aggregate_points[0] if aggregate_points else final_value
    max_drawdown = 0.0
    for value in aggregate_points:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value - peak)

    return {
        "starting_portfolio_value": round(starting_value, 4),
        "final_portfolio_value": round(final_value, 4),
        "portfolio_value_change": round(final_value - starting_value, 4),
        "max_drawdown": round(max_drawdown, 4),
        "portfolio_by_bot": per_bot,
    }


def _summarize_bot_behavior_group(bot_id: str, rows: list[dict]) -> dict:
    summary = _summarize_group(rows)
    chronological = _chronological(rows)
    first_row = chronological[0] if chronological else {}
    last_row = chronological[-1] if chronological else {}

    action_counts = {bucket: 0 for bucket in ACTION_BUCKETS}
    for action, count in Counter(_action(row) for row in rows).items():
        action_counts[action] = count

    ticker_counts = Counter(
        str(row.get("ticker")).upper()
        for row in rows
        if row.get("ticker")
    )
    confidence_series = [
        {
            "timestamp": row.get("timestamp"),
            "confidence": _to_float(row.get("confidence")),
        }
        for row in chronological
        if row.get("confidence") is not None
    ]
    portfolio_series = _portfolio_series(chronological)
    evidence_status_counts = {
        status: 0
        for status in (
            "hold",
            "evidence_backed",
            "speculative_evidence_backed",
            "speculative",
            "unsupported",
        )
    }
    for row in rows:
        evidence_status_counts[decision_evidence_status(row)] += 1

    return {
        "bot_id": bot_id,
        "bot_name": first_row.get("bot_name"),
        "llm_provider": first_row.get("llm_provider"),
        "base_personality": _base_personality(first_row.get("bot_name")),
        "decision_count": summary["decision_count"],
        "trade_count": summary["trade_count"],
        "hold_count": summary["hold_count"],
        "action_counts": action_counts,
        "action_rates": {
            action: _rate(count, summary["decision_count"])
            for action, count in action_counts.items()
        },
        "ticker_counts": dict(ticker_counts.most_common()),
        "top_ticker": ticker_counts.most_common(1)[0][0] if ticker_counts else None,
        "evidence_status_counts": evidence_status_counts,
        "citation_count": summary["citation_count"],
        "unique_evidence_url_count": summary["unique_evidence_url_count"],
        "citation_rate": summary["citation_rate"],
        "unsupported_trade_rate": summary["unsupported_trade_rate"],
        "speculative_trade_rate": summary["speculative_trade_rate"],
        "fill_rate": summary["fill_rate"],
        "filled_quantity": sum(int(row.get("fill_qty_total") or 0) for row in rows),
        "avg_confidence": summary["avg_confidence"],
        "confidence_trend": _confidence_trend(confidence_series),
        "risk_rejection_count": sum(1 for row in rows if _is_risk_rejection(row)),
        "hold_cause_counts": summary["hold_cause_counts"],
        "portfolio": _portfolio_summary(portfolio_series),
        "first_decision_at": first_row.get("timestamp"),
        "last_decision_at": last_row.get("timestamp"),
    }


def _timeline_row(row: dict) -> dict:
    portfolio_value = _portfolio_value(row.get("portfolio_snapshot") or {})
    return {
        "id": row.get("id"),
        "timestamp": row.get("timestamp"),
        "bot_id": row.get("bot_id"),
        "bot_name": row.get("bot_name"),
        "llm_provider": row.get("llm_provider"),
        "action": _action(row),
        "ticker": row.get("ticker"),
        "quantity": row.get("quantity"),
        "limit_price": row.get("limit_price"),
        "reasoning": row.get("reasoning"),
        "headline_used": row.get("headline_used"),
        "confidence": _to_float(row.get("confidence")),
        "evidence_ids": _as_list(row.get("evidence_ids")),
        "evidence_urls": _as_list(row.get("evidence_urls")),
        "evidence_count": len(_as_list(row.get("evidence_ids"))),
        "evidence_status": decision_evidence_status(row),
        "hold_cause": _hold_cause(row),
        "speculative": bool(row.get("speculative", False)),
        "fill_count": int(row.get("fill_count") or 0),
        "fill_qty_total": int(row.get("fill_qty_total") or 0),
        "fill_avg_price": _to_float(row.get("fill_avg_price")),
        "risk_rejected": _is_risk_rejection(row),
        "portfolio_value": portfolio_value,
    }


def _chronological(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: _timestamp_sort_value(row.get("timestamp") or row.get("as_of_time")),
    )


def _group_by(rows: list[dict], field: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)
    return dict(sorted(grouped.items()))


def _action(row: dict) -> str:
    action = str(row.get("action") or "HOLD").upper()
    return action if action in ACTION_BUCKETS else action


def _hold_cause(row: dict) -> str | None:
    if _action(row) != "HOLD":
        return None
    cause = str(row.get("hold_cause") or "unknown").strip().lower()
    return cause if cause in _HOLD_CAUSE_SET else "unknown"


def _hold_cause_counts(rows: list[dict]) -> dict[str, int]:
    counts = {cause: 0 for cause in HOLD_CAUSE_BUCKETS}
    for row in rows:
        cause = _hold_cause(row)
        if cause:
            counts[cause] += 1
    return counts


def _base_personality(bot_name) -> Optional[str]:
    if not bot_name:
        return None
    return str(bot_name).split(" (", 1)[0]


def _is_risk_rejection(row: dict) -> bool:
    if _hold_cause(row) == "risk_limit":
        return True
    reasoning = str(row.get("reasoning") or "").lower()
    return any(marker in reasoning for marker in RISK_REJECTION_MARKERS)


def _confidence_trend(series: list[dict]) -> dict:
    if not series:
        return {
            "latest": None,
            "previous": None,
            "delta": None,
        }
    latest = series[-1]["confidence"]
    previous = series[-2]["confidence"] if len(series) > 1 else None
    delta = round(latest - previous, 4) if latest is not None and previous is not None else None
    return {
        "latest": latest,
        "previous": previous,
        "delta": delta,
    }


def _portfolio_series(rows: list[dict]) -> list[dict]:
    series = []
    first_value = None
    for row in rows:
        snapshot = row.get("portfolio_snapshot") or {}
        value = _portfolio_value(snapshot)
        if value is None:
            continue
        if first_value is None:
            first_value = value
        series.append({
            "timestamp": row.get("timestamp"),
            "total_value": value,
            "cash": _to_float(snapshot.get("cash")),
            "pnl": round(value - first_value, 4),
        })
    return series


def _portfolio_summary(series: list[dict]) -> dict:
    if not series:
        return {
            "latest_total_value": None,
            "starting_total_value": None,
            "value_change": None,
            "max_drawdown": None,
            "series": [],
        }
    start = series[0]["total_value"]
    latest = series[-1]["total_value"]
    peak = start
    max_drawdown = 0.0
    for point in series:
        value = point["total_value"]
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value - peak)
    return {
        "latest_total_value": latest,
        "starting_total_value": start,
        "value_change": round(latest - start, 4),
        "max_drawdown": round(max_drawdown, 4),
        "series": series,
    }


def _portfolio_value(snapshot: dict) -> Optional[float]:
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("total_value") is not None:
        return _to_float(snapshot.get("total_value"))
    cash = _to_float(snapshot.get("cash"))
    positions = snapshot.get("positions") or {}
    cost_basis = snapshot.get("cost_basis") or {}
    if cash is None or not isinstance(positions, dict):
        return None
    position_value = 0.0
    for ticker, quantity in positions.items():
        basis = _to_float(cost_basis.get(ticker)) or 0.0
        position_value += basis * int(quantity or 0)
    return round(cash + position_value, 4)


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _timestamp_sort_value(value) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def evaluate_retrieval_cases(
    repository,
    cases: Iterable[dict],
    embedding_service=None,
    default_top_k: int = 5,
) -> dict:
    """
    Run deterministic retrieval quality checks against labeled cases.

    Each case can include expected_chunk_ids, expected_document_ids,
    expected_accession_nos, expected_source_urls, or expected_text_contains. A
    case is a hit when any expected label appears in the retrieved top-k rows.
    """
    results = []
    for case in cases:
        top_k = int(case.get("top_k") or default_top_k)
        rows = repository.retrieve_evidence(
            ticker=case.get("ticker"),
            query_text=case.get("query_text") or case.get("query") or "",
            top_k=top_k,
            embedding_service=embedding_service,
            as_of_date=_parse_datetime(case.get("as_of_date")),
        )
        expected_chunks = {int(v) for v in case.get("expected_chunk_ids", []) or []}
        expected_docs = {int(v) for v in case.get("expected_document_ids", []) or []}
        expected_accessions = {
            str(v) for v in case.get("expected_accession_nos", []) or []
        }
        expected_urls = {str(v) for v in case.get("expected_source_urls", []) or []}
        expected_text = [
            str(v).lower()
            for v in case.get("expected_text_contains", []) or []
            if str(v).strip()
        ]

        hit_rank: Optional[int] = None
        for idx, row in enumerate(rows, start=1):
            chunk_hit = row.get("chunk_id") in expected_chunks
            doc_hit = row.get("document_id") in expected_docs
            accession_hit = str(row.get("accession_no")) in expected_accessions
            url_hit = str(row.get("source_url")) in expected_urls
            content = str(row.get("content") or "").lower()
            text_hit = any(expected in content for expected in expected_text)
            if chunk_hit or doc_hit or accession_hit or url_hit or text_hit:
                hit_rank = idx
                break

        results.append({
            "name": case.get("name") or case.get("query_text") or "case",
            "ticker": case.get("ticker"),
            "top_k": top_k,
            "hit": hit_rank is not None,
            "hit_rank": hit_rank,
            "reciprocal_rank": round(1 / hit_rank, 4) if hit_rank else 0.0,
            "expected_chunk_ids": sorted(expected_chunks),
            "expected_document_ids": sorted(expected_docs),
            "expected_accession_nos": sorted(expected_accessions),
            "expected_source_urls": sorted(expected_urls),
            "expected_text_contains": expected_text,
            "returned_chunk_ids": [row.get("chunk_id") for row in rows],
            "returned_document_ids": [row.get("document_id") for row in rows],
            "returned_accession_nos": [row.get("accession_no") for row in rows],
            "returned_source_urls": [row.get("source_url") for row in rows],
        })

    case_count = len(results)
    hits = sum(1 for row in results if row["hit"])
    mrr = mean([row["reciprocal_rank"] for row in results]) if results else 0.0
    return {
        "case_count": case_count,
        "hit_count": hits,
        "recall_at_k": _rate(hits, case_count),
        "mean_reciprocal_rank": round(mrr, 4),
        "cases": results,
    }


def _parse_datetime(value) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None
