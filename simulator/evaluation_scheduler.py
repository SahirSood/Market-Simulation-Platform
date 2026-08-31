"""Background scheduler for outcome labels and replay matrices."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from config import (
    DATABASE_URL,
    EVALUATION_SCHEDULER_ENABLED,
    EVALUATION_SCHEDULER_STARTUP_DELAY_SECS,
    LIVE_EVALUATION_REPORT_DECISION_LIMIT,
    LIVE_EVALUATION_REPORT_DIR,
    LIVE_EVALUATION_REPORT_ENABLED,
    LIVE_EVALUATION_REPORT_HORIZON,
    LIVE_EVALUATION_REPORT_INTERVAL_HOURS,
    LIVE_EVALUATION_REPORT_LOOKBACK_DAYS,
    LIVE_EVALUATION_REPORT_MIN_SAMPLES,
    LIVE_EVALUATION_REPORT_STARTUP_DELAY_SECS,
    OUTCOME_LABELING_DECISION_LIMIT,
    OUTCOME_LABELING_ENABLED,
    OUTCOME_LABELING_HORIZONS,
    OUTCOME_LABELING_INTERVAL_MINS,
    REPLAY_MATRIX_BOTS,
    REPLAY_MATRIX_EXECUTE_ORDERS,
    REPLAY_MATRIX_FIXTURES,
    REPLAY_MATRIX_INTERVAL_HOURS,
    REPLAY_MATRIX_MAX_FIXTURES_PER_RUN,
    REPLAY_MATRIX_PROVIDER_SETS,
    REPLAY_MATRIX_SCHEDULE_ENABLED,
    REPLAY_MATRIX_STARTUP_DELAY_SECS,
)
from outcomes import evaluate_due_outcomes
from live_evaluation import generate_live_evaluation_report, write_live_evaluation_report
from replay_workflow import (
    DEFAULT_BOTS,
    DEFAULT_PROVIDERS,
    REPLAY_EVENTS_DIR,
    load_replay_event_file,
    run_historical_replay,
    selected_values,
)

logger = logging.getLogger(__name__)


class EvaluationScheduler:
    """Run cheap outcome labeling, live reports, and opt-in replay matrices."""

    def __init__(
        self,
        *,
        reasoning_log,
        price_feed,
        replay_store,
        rag_repository=None,
        database_url: str | None = None,
        enabled: bool = EVALUATION_SCHEDULER_ENABLED,
        startup_delay_secs: float = EVALUATION_SCHEDULER_STARTUP_DELAY_SECS,
        outcome_enabled: bool = OUTCOME_LABELING_ENABLED,
        outcome_interval_mins: float = OUTCOME_LABELING_INTERVAL_MINS,
        outcome_horizons: Iterable[str] = OUTCOME_LABELING_HORIZONS,
        outcome_decision_limit: int = OUTCOME_LABELING_DECISION_LIMIT,
        live_report_enabled: bool = LIVE_EVALUATION_REPORT_ENABLED,
        live_report_interval_hours: float = LIVE_EVALUATION_REPORT_INTERVAL_HOURS,
        live_report_startup_delay_secs: float = LIVE_EVALUATION_REPORT_STARTUP_DELAY_SECS,
        live_report_lookback_days: int = LIVE_EVALUATION_REPORT_LOOKBACK_DAYS,
        live_report_min_samples: int = LIVE_EVALUATION_REPORT_MIN_SAMPLES,
        live_report_decision_limit: int = LIVE_EVALUATION_REPORT_DECISION_LIMIT,
        live_report_horizon: str = LIVE_EVALUATION_REPORT_HORIZON,
        live_report_dir: str | Path = LIVE_EVALUATION_REPORT_DIR,
        replay_enabled: bool = REPLAY_MATRIX_SCHEDULE_ENABLED,
        replay_interval_hours: float = REPLAY_MATRIX_INTERVAL_HOURS,
        replay_startup_delay_secs: float = REPLAY_MATRIX_STARTUP_DELAY_SECS,
        replay_fixtures: Iterable[str] = REPLAY_MATRIX_FIXTURES,
        replay_provider_sets: Iterable[str] = REPLAY_MATRIX_PROVIDER_SETS,
        replay_bots: Iterable[str] = REPLAY_MATRIX_BOTS,
        replay_execute_orders: bool = REPLAY_MATRIX_EXECUTE_ORDERS,
        replay_max_fixtures_per_run: int = REPLAY_MATRIX_MAX_FIXTURES_PER_RUN,
    ):
        self.reasoning_log = reasoning_log
        self.price_feed = price_feed
        self.replay_store = replay_store
        self.rag_repository = rag_repository
        self.database_url = database_url or DATABASE_URL or "sqlite:///replay.db"
        self.enabled = bool(enabled)
        self.startup_delay_secs = max(0.0, float(startup_delay_secs or 0.0))
        self.outcome_enabled = bool(outcome_enabled)
        self.outcome_interval_secs = max(60.0, float(outcome_interval_mins or 60.0) * 60)
        self.outcome_horizons = _normalize_horizons(outcome_horizons)
        self.outcome_decision_limit = max(1, int(outcome_decision_limit or 1))
        self.live_report_enabled = bool(live_report_enabled)
        self.live_report_interval_secs = max(
            3600.0,
            float(live_report_interval_hours or 168.0) * 3600,
        )
        self.live_report_startup_delay_secs = max(
            0.0,
            float(live_report_startup_delay_secs or 0.0),
        )
        self.live_report_lookback_days = max(1, int(live_report_lookback_days or 1))
        self.live_report_min_samples = max(1, int(live_report_min_samples or 1))
        self.live_report_decision_limit = max(1, int(live_report_decision_limit or 1))
        self.live_report_horizon = str(live_report_horizon or "1d").lower().strip()
        self.live_report_dir = Path(live_report_dir)
        self.replay_enabled = bool(replay_enabled)
        self.replay_interval_secs = max(3600.0, float(replay_interval_hours or 24.0) * 3600)
        self.replay_startup_delay_secs = max(0.0, float(replay_startup_delay_secs or 0.0))
        self.replay_fixtures = _normalize_fixture_names(replay_fixtures)
        self.replay_provider_sets = _normalize_provider_sets(replay_provider_sets)
        self.replay_bots = _normalize_bots(replay_bots)
        self.replay_execute_orders = bool(replay_execute_orders)
        self.replay_max_fixtures_per_run = max(1, int(replay_max_fixtures_per_run or 1))

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()
        self._next_outcome_at: float | None = None
        self._next_live_report_at: float | None = None
        self._next_replay_at: float | None = None
        self._fixture_cursor = 0
        self._last_outcome_run: dict | None = None
        self._last_live_report_run: dict | None = None
        self._last_replay_run: dict | None = None
        self._failures: list[dict] = []

    def start(self) -> None:
        if not self.enabled:
            logger.info("[EvaluationScheduler] disabled")
            return
        if self._thread and self._thread.is_alive():
            return
        now = time.time()
        self._next_outcome_at = (
            now + self.startup_delay_secs if self.outcome_enabled else None
        )
        self._next_live_report_at = (
            now + self.live_report_startup_delay_secs
            if self.live_report_enabled
            else None
        )
        self._next_replay_at = (
            now + self.replay_startup_delay_secs if self.replay_enabled else None
        )
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="evaluation-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "[EvaluationScheduler] started: outcomes=%s live_report=%s replay=%s",
            self.outcome_enabled,
            self.live_report_enabled,
            self.replay_enabled,
        )

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("[EvaluationScheduler] stopped")

    def status(self) -> dict:
        with self._lock:
            return {
                "enabled": self.enabled,
                "running": self._running and bool(self._thread and self._thread.is_alive()),
                "outcome_labeling": {
                    "enabled": self.outcome_enabled,
                    "interval_seconds": self.outcome_interval_secs,
                    "horizons": list(self.outcome_horizons),
                    "decision_limit": self.outcome_decision_limit,
                    "next_run_at": _iso_from_ts(self._next_outcome_at),
                    "last_run": self._last_outcome_run,
                },
                "live_report": {
                    "enabled": self.live_report_enabled,
                    "interval_seconds": self.live_report_interval_secs,
                    "lookback_days": self.live_report_lookback_days,
                    "min_samples": self.live_report_min_samples,
                    "decision_limit": self.live_report_decision_limit,
                    "horizon": self.live_report_horizon,
                    "output_dir": str(self.live_report_dir),
                    "next_run_at": _iso_from_ts(self._next_live_report_at),
                    "last_run": self._last_live_report_run,
                },
                "replay_matrix": {
                    "enabled": self.replay_enabled,
                    "interval_seconds": self.replay_interval_secs,
                    "fixtures": list(self.replay_fixtures),
                    "provider_sets": [",".join(row) for row in self.replay_provider_sets],
                    "bots": list(self.replay_bots),
                    "execute_orders": self.replay_execute_orders,
                    "max_fixtures_per_run": self.replay_max_fixtures_per_run,
                    "next_run_at": _iso_from_ts(self._next_replay_at),
                    "last_run": self._last_replay_run,
                },
                "recent_failures": list(self._failures[-5:]),
            }

    def run_outcome_update_once(self) -> dict:
        started = datetime.now(timezone.utc)
        try:
            result = evaluate_due_outcomes(
                self.reasoning_log,
                self.price_feed,
                horizons=self.outcome_horizons,
                decision_limit=self.outcome_decision_limit,
            )
            payload = {
                "status": "succeeded",
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "created_count": result.get("created_count", 0),
                "skipped_existing": result.get("skipped_existing", 0),
                "skipped_not_due": result.get("skipped_not_due", 0),
                "skipped_invalid": result.get("skipped_invalid", 0),
                "horizons": list((result.get("horizons") or {}).keys()),
            }
            with self._lock:
                self._last_outcome_run = payload
            logger.info("[EvaluationScheduler] outcome labels: %s", payload)
            return payload
        except Exception as exc:
            payload = self._record_failure("outcome_labeling", started, exc)
            with self._lock:
                self._last_outcome_run = payload
            return payload

    def run_live_report_once(self) -> dict:
        """Build and persist the current live report without an LLM call."""
        started = datetime.now(timezone.utc)
        try:
            report = generate_live_evaluation_report(
                self.reasoning_log,
                period_days=self.live_report_lookback_days,
                min_samples=self.live_report_min_samples,
                decision_limit=self.live_report_decision_limit,
                horizon=self.live_report_horizon,
                include_markdown=False,
            )
            paths = write_live_evaluation_report(report, self.live_report_dir)
            sample = report.get("sample") or {}
            payload = {
                "status": "succeeded",
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "mode": report.get("mode"),
                "horizon": report.get("outcomes", {}).get("selected_horizon"),
                "decision_count": sample.get("decision_count", 0),
                "outcome_label_count": sample.get("outcome_label_count", 0),
                "labeled_decision_count": sample.get("labeled_decision_count", 0),
                "sample_sufficient": sample.get("sample_sufficient", False),
                **paths,
            }
            with self._lock:
                self._last_live_report_run = payload
            logger.info("[EvaluationScheduler] live report: %s", payload)
            return payload
        except Exception as exc:
            payload = self._record_failure("live_report", started, exc)
            with self._lock:
                self._last_live_report_run = payload
            return payload

    def run_replay_matrix_once(self) -> dict:
        started = datetime.now(timezone.utc)
        selected_fixtures = self._next_replay_fixtures()
        run_results = []
        try:
            for fixture_name in selected_fixtures:
                name, file_config, events = load_replay_event_file(
                    fixture_name,
                    root=REPLAY_EVENTS_DIR,
                )
                for provider_set in self.replay_provider_sets:
                    run_name = f"{name or Path(fixture_name).stem} [{','.join(provider_set)} scheduled]"
                    result = run_historical_replay(
                        database_url=self.database_url,
                        events=events,
                        name=run_name,
                        config={
                            **file_config,
                            "source": "evaluation_scheduler",
                            "event_file": fixture_name,
                            "scheduled": True,
                        },
                        providers=provider_set,
                        bot_names=self.replay_bots,
                        execute_orders=self.replay_execute_orders,
                        notes="scheduled replay matrix run",
                        replay_store=self.replay_store,
                        rag_repository=self.rag_repository,
                    )
                    run_results.append({
                        "fixture": fixture_name,
                        "provider_set": list(provider_set),
                        "run_id": result.get("run_id"),
                        "status": result.get("status"),
                        "decision_count": result.get("decision_count"),
                        "input_fingerprint": result.get("input_fingerprint"),
                    })

            payload = {
                "status": "succeeded",
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "fixture_count": len(selected_fixtures),
                "run_count": len(run_results),
                "runs": run_results,
            }
            with self._lock:
                self._last_replay_run = payload
            logger.info("[EvaluationScheduler] replay matrix: %s", payload)
            return payload
        except Exception as exc:
            payload = self._record_failure("replay_matrix", started, exc)
            with self._lock:
                self._last_replay_run = payload
            return payload

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            now = time.time()
            due_tasks = []
            if self.outcome_enabled and self._next_outcome_at is not None and now >= self._next_outcome_at:
                due_tasks.append("outcomes")
            if self.live_report_enabled and self._next_live_report_at is not None and now >= self._next_live_report_at:
                due_tasks.append("live_report")
            if self.replay_enabled and self._next_replay_at is not None and now >= self._next_replay_at:
                due_tasks.append("replay")

            for task in due_tasks:
                if self._stop_event.is_set():
                    break
                if task == "outcomes":
                    self.run_outcome_update_once()
                    with self._lock:
                        self._next_outcome_at = time.time() + self.outcome_interval_secs
                elif task == "live_report":
                    self.run_live_report_once()
                    with self._lock:
                        self._next_live_report_at = time.time() + self.live_report_interval_secs
                elif task == "replay":
                    self.run_replay_matrix_once()
                    with self._lock:
                        self._next_replay_at = time.time() + self.replay_interval_secs

            wait_seconds = self._seconds_until_next_task()
            self._stop_event.wait(wait_seconds)

    def _seconds_until_next_task(self) -> float:
        candidates = [
            value for value in (
                self._next_outcome_at,
                self._next_live_report_at,
                self._next_replay_at,
            )
            if value is not None
        ]
        if not candidates:
            return 60.0
        return max(1.0, min(60.0, min(candidates) - time.time()))

    def _next_replay_fixtures(self) -> list[str]:
        if not self.replay_fixtures:
            return []
        if self.replay_max_fixtures_per_run >= len(self.replay_fixtures):
            return list(self.replay_fixtures)
        selected = []
        for _ in range(self.replay_max_fixtures_per_run):
            selected.append(self.replay_fixtures[self._fixture_cursor % len(self.replay_fixtures)])
            self._fixture_cursor += 1
        return selected

    def _record_failure(self, task: str, started: datetime, exc: Exception) -> dict:
        payload = {
            "status": "failed",
            "task": task,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": _public_error(exc),
        }
        with self._lock:
            self._failures.append(payload)
            self._failures = self._failures[-20:]
        logger.warning("[EvaluationScheduler] %s failed: %s", task, exc, exc_info=True)
        return payload


def _normalize_horizons(values: Iterable[str]) -> tuple[str, ...]:
    rows = [str(value).lower().strip() for value in values if str(value).strip()]
    return tuple(rows or ("1h", "6h", "1d", "7d"))


def _normalize_fixture_names(values: Iterable[str]) -> tuple[str, ...]:
    raw = [str(value).strip() for value in values if str(value).strip()]
    if not raw or any(value.lower() == "all" for value in raw):
        return tuple(path.name for path in sorted(REPLAY_EVENTS_DIR.glob("sample_*.json")))
    return tuple(raw)


def _normalize_provider_sets(values: Iterable[str]) -> tuple[tuple[str, ...], ...]:
    provider_sets = []
    allowed = set(DEFAULT_PROVIDERS)
    for value in values:
        selected = selected_values(str(value).split(","), allowed, "provider")
        provider_sets.append(tuple(selected))
    return tuple(provider_sets or (tuple(DEFAULT_PROVIDERS),))


def _normalize_bots(values: Iterable[str]) -> tuple[str, ...]:
    selected = selected_values([str(value) for value in values], set(DEFAULT_BOTS), "bot")
    return tuple(selected)


def _iso_from_ts(value: float | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _public_error(exc: Exception) -> str:
    message = str(exc or "").strip().replace("\n", " ")
    if "://" in message or "secret" in message.lower() or "key" in message.lower():
        message = type(exc).__name__
    return message[:240] if message else type(exc).__name__
