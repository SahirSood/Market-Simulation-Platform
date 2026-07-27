# Simulator Core

The simulator coordinates model decisions, market data, risk controls, the
native matching engine, portfolios, replay, and RAG-backed evidence retrieval.
It is the domain layer shared by the API, tests, and local scripts.

## Key Areas

- `bots/`: fixed trading personalities used for same-input Claude/OpenAI runs.
- `scheduler.py`: decision loop, order submission flow, and event publishing.
- `risk.py`: deterministic pre-trade limits that gate every non-`HOLD` order.
- `engine_adapter.py`: native C++ engine bridge with a controlled stub fallback.
- `rag/`: SEC ingestion, chunk storage, embeddings, retrieval, and monitoring.
- `replay.py` and `replay_workflow.py`: deterministic scenario playback.
- `evaluation.py`: citation, replay, and model-comparison metrics.

## Local Commands

```powershell
pytest simulator/tests -q
python scripts/run_replay.py --events data/replay_events/sample_earnings_beat.json --db sqlite:///rag.db --no-orders
python scripts/run_retrieval_suite.py --db sqlite:///rag.db --allow-misses
```

The scheduler repeats deterministic risk checks before orders reach the engine,
so model and MCP-style tool suggestions cannot bypass the final execution gate.
