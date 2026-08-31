"""Replay standings and human-readable research reports."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


TRADE_ACTIONS = {"BUY", "SELL"}
HORIZONS = ["1d", "3d", "7d"]


def analyze_replay_dataset(
    *,
    dataset_path: str | Path,
    standings_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    model_suite_path: str | Path | None = None,
    benchmark: str = "SPY",
) -> dict:
    rows = _load_rows(dataset_path)
    model_suite = _load_json(model_suite_path) if model_suite_path else None
    analysis = build_replay_analysis(rows, benchmark=benchmark, model_suite=model_suite)
    analysis["dataset"] = str(dataset_path)
    if standings_path:
        path = Path(standings_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    if markdown_path:
        path = Path(markdown_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_replay_report_markdown(analysis), encoding="utf-8")
    return analysis


def build_replay_analysis(rows: list[dict], *, benchmark: str, model_suite: dict | None = None) -> dict:
    groups = {
        "bot_provider": _group_rows(rows, lambda row: row.get("bot_name") or "unknown"),
        "provider": _group_rows(rows, lambda row: row.get("llm_provider") or "unknown"),
        "personality": _group_rows(rows, lambda row: row.get("base_personality") or "unknown"),
        "action": _group_rows(rows, lambda row: row.get("action") or "unknown"),
        "risk_regime": _group_rows(rows, lambda row: row.get("event_risk_regime") or "unknown"),
        "trend_regime": _group_rows(rows, lambda row: row.get("event_trend_regime") or "unknown"),
        "volatility_regime": _group_rows(rows, lambda row: row.get("event_volatility_regime") or "unknown"),
        "confidence_bucket": _group_rows(rows, lambda row: row.get("confidence_bucket") or "unknown"),
        "news_context_quality": _group_rows(rows, lambda row: row.get("news_context_quality") or "unknown"),
    }
    standings = {
        name: [_group_summary(label, part_rows) for label, part_rows in sorted(parts.items())]
        for name, parts in groups.items()
    }
    for values in standings.values():
        values.sort(key=lambda row: (row["intent_mark_pnl_1d"] or 0, row["trade_count"]), reverse=True)

    overall = _group_summary("overall", rows)
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "benchmark": benchmark,
        "overall": overall,
        "standings": standings,
        "cost_summary": _cost_summary(rows),
        "lessons": _lessons(overall, standings, model_suite),
        "model_suite_summary": _model_suite_summary(model_suite),
    }


def render_replay_report_markdown(analysis: dict) -> str:
    overall = analysis["overall"]
    lines = [
        "# Six-Month Replay Research Report",
        "",
        f"Generated: `{analysis['generated_at']}`",
        f"Benchmark: `{analysis['benchmark']}`",
        "",
        "## Executive Summary",
        "",
        f"- Decisions analyzed: `{overall['decision_count']}`.",
        f"- Trades: `{overall['trade_count']}`; holds: `{overall['hold_count']}`.",
        f"- BUY/SELL/HOLD mix: `{overall['buy_count']}` / `{overall['sell_count']}` / `{overall['hold_count']}`.",
        f"- 1d directional accuracy on labeled trades: `{_fmt_rate(overall['directional_accuracy_1d'])}`.",
        f"- 1d beat-benchmark rate on labeled trades: `{_fmt_rate(overall['beat_benchmark_rate_1d'])}`.",
        f"- 1d intent mark PnL: `{_fmt_number(overall['intent_mark_pnl_1d'])}`.",
        f"- HOLD rows that missed a >=2% one-day move somewhere in the universe: `{overall['hold_missed_big_move_count']}`.",
        "",
        "## What Looks Good",
        "",
    ]
    positives = analysis["lessons"].get("positive", [])
    lines.extend([f"- {item}" for item in positives] or ["- No strong positive pattern is decision-grade yet."])
    lines.extend(["", "## What Looks Bad Or Risky", ""])
    negatives = analysis["lessons"].get("negative", [])
    lines.extend([f"- {item}" for item in negatives] or ["- No major risk pattern was detected."])
    lines.extend(["", "## Bot / Provider Standings", ""])
    lines.extend(_markdown_table(
        analysis["standings"]["bot_provider"],
        ["label", "decision_count", "trade_count", "hold_count", "directional_accuracy_1d", "beat_benchmark_rate_1d", "intent_mark_pnl_1d"],
    ))
    lines.extend(["", "## Provider Standings", ""])
    lines.extend(_markdown_table(
        analysis["standings"]["provider"],
        ["label", "decision_count", "trade_count", "directional_accuracy_1d", "beat_benchmark_rate_1d", "intent_mark_pnl_1d"],
    ))
    lines.extend(["", "## Regime Standings", ""])
    lines.extend(_markdown_table(
        analysis["standings"]["risk_regime"],
        ["label", "decision_count", "trade_count", "directional_accuracy_1d", "beat_benchmark_rate_1d", "intent_mark_pnl_1d"],
    ))
    lines.extend(["", "## Cost Snapshot", ""])
    cost_summary = analysis.get("cost_summary") or {}
    if cost_summary.get("available"):
        lines.extend([
            f"- Recorded cost rows: `{cost_summary.get('recorded_cost_count')}`.",
            f"- Total estimated LLM cost: `${cost_summary.get('total_estimated_llm_cost_usd')}`.",
            f"- Total recorded tokens: `{cost_summary.get('total_tokens')}`.",
        ])
    else:
        lines.append(
            "- Exact replay model cost is unavailable for this report because the source replay rows did not store token/cost fields."
        )
    lines.extend(["", "## Model Suite Snapshot", ""])
    model_summary = analysis.get("model_suite_summary") or {}
    if model_summary:
        for target, values in model_summary.items():
            lines.append(
                f"- `{target}`: best test-accuracy model `{values.get('best_model_by_test_accuracy')}`, "
                f"best test-F1 model `{values.get('best_model_by_test_f1')}`, usable rows `{values.get('usable_rows')}`."
            )
    else:
        lines.append("- No model suite report was attached.")
    lines.extend([
        "",
        "## Caveats",
        "",
        "- This is replay/backtest evidence, not live trading history.",
        "- The current run is no-orders mode, so intent PnL is not the same as fully executed PnL.",
        "- GDELT backfill is sampled public metadata, not an exhaustive paid market-news feed.",
        "- HOLD opportunity labels are coarse: they show missed market movement, not necessarily that a bot should have known the winning ticker.",
        "- Model outputs are explanatory and exploratory until we add more labels, costs, and replay-regression validation.",
        "",
        "## Recommended Next Actions",
        "",
        "- Add product-facing replay standings API/UI from this analysis.",
        "- Add cost aggregation before comparing providers as business choices.",
        "- Improve HOLD opportunity labels and longer-horizon labels.",
        "- Run selected intraday replay only after daily standings/reporting are useful.",
    ])
    return "\n".join(lines) + "\n"


def _group_summary(label: str, rows: list[dict]) -> dict:
    actions = Counter(str(row.get("action") or "").upper() for row in rows)
    trade_rows = [row for row in rows if str(row.get("action") or "").upper() in TRADE_ACTIONS]
    summary = {
        "label": label,
        "decision_count": len(rows),
        "trade_count": len(trade_rows),
        "hold_count": actions.get("HOLD", 0),
        "buy_count": actions.get("BUY", 0),
        "sell_count": actions.get("SELL", 0),
        "avg_confidence": _mean(_floats(row.get("confidence") for row in rows)),
        "risk_blocked_count": sum(1 for row in rows if str(row.get("risk_blocked")) == "1"),
        "hold_missed_big_move_count": sum(1 for row in rows if str(row.get("hold_missed_big_move_1d")) == "1"),
    }
    for horizon in HORIZONS:
        labeled = [row for row in trade_rows if str(row.get(f"directional_correct_{horizon}")) in {"0", "1"}]
        bench = [row for row in trade_rows if str(row.get(f"beat_benchmark_{horizon}")) in {"0", "1"}]
        summary[f"labeled_trade_count_{horizon}"] = len(labeled)
        summary[f"directional_accuracy_{horizon}"] = _rate(
            sum(1 for row in labeled if str(row.get(f"directional_correct_{horizon}")) == "1"),
            len(labeled),
        )
        summary[f"beat_benchmark_rate_{horizon}"] = _rate(
            sum(1 for row in bench if str(row.get(f"beat_benchmark_{horizon}")) == "1"),
            len(bench),
        )
        summary[f"intent_mark_pnl_{horizon}"] = _sum(_floats(row.get(f"intent_mark_pnl_{horizon}") for row in trade_rows))
        summary[f"large_loss_count_{horizon}"] = sum(1 for row in trade_rows if str(row.get(f"large_loss_{horizon}")) == "1")
        summary[f"high_confidence_wrong_count_{horizon}"] = sum(
            1 for row in trade_rows if str(row.get(f"high_confidence_wrong_{horizon}")) == "1"
        )
    return summary


def _lessons(overall: dict, standings: dict, model_suite: dict | None) -> dict:
    positive = []
    negative = []
    bot_rows = standings.get("bot_provider", [])
    if bot_rows:
        best = max(bot_rows, key=lambda row: row.get("intent_mark_pnl_1d") or 0)
        worst = min(bot_rows, key=lambda row: row.get("intent_mark_pnl_1d") or 0)
        positive.append(
            f"Best 1d intent PnL group is {best['label']} with {best['trade_count']} trades and PnL {_fmt_number(best['intent_mark_pnl_1d'])}."
        )
        negative.append(
            f"Worst 1d intent PnL group is {worst['label']} with PnL {_fmt_number(worst['intent_mark_pnl_1d'])}."
        )
    if (overall.get("beat_benchmark_rate_1d") or 0) < 0.5:
        negative.append("The aggregate 1d beat-benchmark rate is below 50%, so beating SPY is not proven yet.")
    if overall.get("hold_count", 0) > overall.get("trade_count", 0):
        negative.append("The bots held far more often than they traded; HOLD opportunity-cost labeling needs to improve before pruning quiet bots.")
    if model_suite:
        for target, result in (model_suite.get("targets") or {}).items():
            best = result.get("best_model_by_test_accuracy")
            if best and best != "dummy_majority":
                positive.append(f"Model suite trained for `{target}`; best test-accuracy model was `{best}`.")
            elif best == "dummy_majority":
                negative.append(
                    f"For `{target}`, the dummy majority baseline was hardest to beat on test accuracy; this target needs more data or better features."
                )
    return {"positive": positive, "negative": negative}


def _model_suite_summary(model_suite: dict | None) -> dict:
    if not model_suite:
        return {}
    summary = {}
    for target, result in (model_suite.get("targets") or {}).items():
        summary[target] = {
            "status": result.get("status"),
            "usable_rows": result.get("usable_rows"),
            "label_counts": result.get("label_counts"),
            "best_model_by_test_accuracy": result.get("best_model_by_test_accuracy"),
            "best_model_by_test_f1": result.get("best_model_by_test_f1"),
        }
    return summary


def _cost_summary(rows: list[dict]) -> dict:
    recorded = []
    by_provider = defaultdict(lambda: {
        "recorded_cost_count": 0,
        "total_estimated_llm_cost_usd": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    })
    for row in rows:
        cost = _to_float(row.get("llm_estimated_cost_usd"))
        if cost is None:
            continue
        provider = str(row.get("llm_provider") or "unknown")
        input_tokens = int(_to_float(row.get("llm_input_tokens")) or 0)
        output_tokens = int(_to_float(row.get("llm_output_tokens")) or 0)
        total_tokens = int(_to_float(row.get("llm_total_tokens")) or input_tokens + output_tokens)
        recorded.append((provider, cost, input_tokens, output_tokens, total_tokens))
        by_provider[provider]["recorded_cost_count"] += 1
        by_provider[provider]["total_estimated_llm_cost_usd"] += cost
        by_provider[provider]["input_tokens"] += input_tokens
        by_provider[provider]["output_tokens"] += output_tokens
        by_provider[provider]["total_tokens"] += total_tokens

    provider_rows = {}
    for provider, values in by_provider.items():
        provider_rows[provider] = {
            **values,
            "total_estimated_llm_cost_usd": round(values["total_estimated_llm_cost_usd"], 8),
        }
    return {
        "available": bool(recorded),
        "recorded_cost_count": len(recorded),
        "missing_cost_count": max(0, len(rows) - len(recorded)),
        "total_estimated_llm_cost_usd": round(sum(item[1] for item in recorded), 8) if recorded else None,
        "input_tokens": sum(item[2] for item in recorded),
        "output_tokens": sum(item[3] for item in recorded),
        "total_tokens": sum(item[4] for item in recorded),
        "by_provider": dict(sorted(provider_rows.items())),
    }


def _load_rows(path: str | Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_json(path: str | Path | None) -> dict | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    return json.loads(file_path.read_text(encoding="utf-8"))


def _group_rows(rows: list[dict], key_fn) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for row in rows:
        groups[str(key_fn(row) or "unknown")].append(row)
    return dict(groups)


def _floats(values: Iterable) -> list[float]:
    output = []
    for value in values:
        number = _to_float(value)
        if number is not None:
            output.append(number)
    return output


def _to_float(value) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sum(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values), 6)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _fmt_rate(value) -> str:
    number = _to_float(value)
    return "n/a" if number is None else f"{number * 100:.2f}%"


def _fmt_number(value) -> str:
    number = _to_float(value)
    return "n/a" if number is None else f"{number:,.2f}"


def _markdown_table(rows: list[dict], columns: list[str], limit: int = 20) -> list[str]:
    output = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows[:limit]:
        values = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, float):
                value = f"{value:.4f}"
            values.append(str(value if value is not None else ""))
        output.append("| " + " | ".join(values) + " |")
    return output
