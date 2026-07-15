"""Phase D evaluation helpers for decisions, evidence, and retrieval quality."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Iterable, Optional


TRADE_ACTIONS = {"BUY", "SELL"}


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


def evaluate_retrieval_cases(
    repository,
    cases: Iterable[dict],
    embedding_service=None,
    default_top_k: int = 5,
) -> dict:
    """
    Run deterministic retrieval quality checks against labeled cases.

    Each case can include expected_chunk_ids and/or expected_document_ids. A case
    is a hit when any expected id appears in the retrieved top-k rows.
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

        hit_rank: Optional[int] = None
        for idx, row in enumerate(rows, start=1):
            chunk_hit = row.get("chunk_id") in expected_chunks
            doc_hit = row.get("document_id") in expected_docs
            if chunk_hit or doc_hit:
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
            "returned_chunk_ids": [row.get("chunk_id") for row in rows],
            "returned_document_ids": [row.get("document_id") for row in rows],
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
