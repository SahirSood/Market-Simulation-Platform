# RAG And Ops

## What RAG Does

The RAG layer gives bots evidence from SEC filings. It does not trade, schedule bots, or own portfolio state. It stores external documents, chunks them, optionally embeds them, retrieves relevant evidence, and injects snippets into bot prompts.

## Storage Model

Code:

- `simulator/rag/models.py`
- `simulator/rag/repository.py`

Tables:

- `rag_documents`: one source document, usually one SEC filing.
- `rag_chunks`: retrieval-sized chunks linked to a document.
- `rag_job_status`: local ingestion/embedding job attempts, status, retry count, and compact metadata.

Important document fields:

- `ticker`
- `source_url`
- `source_type`
- `source_name`
- `form_type`
- `cik`
- `accession_no`
- `published_at`
- `content`
- `raw_content`
- `content_hash`

Important chunk fields:

- `document_id`
- `content`
- `start_pos`
- `end_pos`
- `embedding`

Deduplication is by `content_hash`, computed from cleaned document text.

## SEC Ingestion

Code:

- `simulator/rag/sec_ingestion.py`
- `simulator/rag/run_sec_ingestion.py`
- `scripts/ingest_poller.py`

Flow:

1. Map ticker to CIK.
2. Fetch SEC submissions JSON from `https://data.sec.gov/submissions/CIK{cik}.json`.
3. Select recent forms such as `10-K`, `10-Q`, `8-K`.
4. Build SEC archive filing URL.
5. Fetch filing HTML.
6. Store raw HTML in `raw_content`.
7. Clean HTML into plain text.
8. Chunk text with overlap.
9. Insert document and chunks through `RagRepository`.

Hardened behavior:

- SEC `User-Agent` support via `SEC_USER_AGENT`.
- Retry/backoff for rate limits and transient HTTP failures.
- Metrics for processed, inserted, skipped duplicate, failed fetch, retry count, and last successful accession by CIK.
- Optional `--max-retries` on the poller, with job status persisted in `rag_job_status`.

## Monitoring For New Filings

Code:

- `simulator/rag/monitor.py`

`detect_new_filings_for_ciks()` compares remote SEC submissions against the latest local accession returned by `RagRepository.get_latest_accession_for_cik()`.

CIKs are normalized to canonical 10-digit strings, so `320193` and `0000320193` resolve the same way.

## Embeddings

Code:

- `simulator/rag/embeddings.py`
- `scripts/embed_worker.py`

Embedding model:

- `OpenAIEmbeddingService` uses OpenAI embeddings when `OPENAI_API_KEY` exists.
- `DeterministicFakeEmbeddingService` exists for deterministic tests/local fallback.

Worker model:

- Chunks with empty `embedding` are pending jobs.
- `scripts/embed_worker.py` batches missing chunks and writes embeddings back.
- Optional `--max-retries` records local job attempts in `rag_job_status`.
- This uses the database as a simple queue/status store. Redis/RQ or Celery can replace it later.

## Local Job Ops

Code:

- `RagRepository.summarize_job_status()`
- `RagRepository.requeue_jobs()`
- `scripts/rag_jobs.py`
- `GET /ops/rag/status`
- `GET /ops/ingestion/status`

Operators can inspect grouped ingestion/embedding status and recent rows through
the read-only ops endpoints. Requeue and one-shot worker triggers are now
available through authenticated Phase G write APIs when `ARENA_API_KEY` is set.

```powershell
python scripts/rag_jobs.py --db sqlite:///rag.db summary
python scripts/rag_jobs.py --db sqlite:///rag.db list --job-type embedding --status failed
python scripts/rag_jobs.py --db sqlite:///rag.db requeue --job-type embedding --limit 20
```

Protected API equivalents:

```powershell
$headers = @{"X-API-Key"=$env:ARENA_API_KEY; "X-Actor"="local-operator"}
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ops/ingestion/run -Headers $headers -ContentType "application/json" -Body '{"tickers":["AAPL"],"max_filings":1,"forms":["10-Q"]}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ops/embedding/run -Headers $headers -ContentType "application/json" -Body '{"limit":100,"batch_size":32}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/ops/rag/requeue -Headers $headers -ContentType "application/json" -Body '{"job_type":"embedding","statuses":["failed"],"limit":20}'
Invoke-RestMethod -Method Get -Uri http://localhost:8000/audit/events -Headers $headers
```

## Retrieval

Code:

- `RagRepository.retrieve_evidence()`

Paths:

1. Vector ranking with FAISS when `faiss` and `numpy` are installed.
2. Exact cosine ranking if FAISS is unavailable.
3. Keyword fallback if embeddings are unavailable.

Replay/no-lookahead path:

- `retrieve_evidence(..., as_of_date=...)` filters out documents whose `published_at` is after the simulated decision time.
- `simulator.replay.AsOfRagRepository` injects the current replay event time for bots.
- `BaseBot._retrieve_evidence()` passes `context["as_of_date"]` when available.

Returned evidence rows include:

- `chunk_id`
- `document_id`
- `ticker`
- `source_url`
- `published_at`
- `content`
- `start_pos`
- `end_pos`
- `score`

Evidence drilldown:

- `RagRepository.get_chunks_by_ids(chunk_ids)` returns cited chunks with document metadata.
- `GET /evaluation/evidence?chunk_ids=1,2,3` exposes that lookup to the dashboard.
- Returned rows include chunk id, document id, ticker, form type, accession number, published date, source URL, content, and start/end positions.
- The frontend evidence drawer uses this endpoint from replay decision rows and the bot behavior timeline.

## Bot Integration

Code:

- `simulator/base_bot.py`

Bot prompt flow:

1. `_evidence_query_text()` builds a query from headlines.
2. `_evidence_ticker()` selects a likely ticker.
3. `_retrieve_evidence()` asks the repository for rows.
4. `_format_evidence_for_prompt()` adds snippets to the prompt.
5. LLM returns `evidence_ids`, `confidence`, and `speculative`.
6. `_apply_evidence_guardrail()` may force `HOLD` if evidence is weak and the trade is not speculative.

Evidence fields are persisted by `ReasoningLog` and exposed by the API.

## Retrieval Evaluation

Code:

- `simulator/evaluation.py`

`evaluate_retrieval_cases()` runs labeled retrieval checks against expected chunk ids, document ids, accession numbers, source URLs, or expected snippet text. It reports recall@k and mean reciprocal rank, and it honors per-case `as_of_date` values.

Starter cases live in:

- `data/retrieval_cases/sec_basic_cases.json`
- `data/retrieval_cases/sec_operating_metrics_cases.json`
- `data/retrieval_cases/sec_risk_liquidity_cases.json`

Run:

```powershell
python scripts/eval_retrieval.py --cases data/retrieval_cases/sec_basic_cases.json --db sqlite:///rag.db
python scripts/eval_retrieval.py --cases data/retrieval_cases/sec_operating_metrics_cases.json --db sqlite:///rag.db --record
python scripts/run_retrieval_suite.py --db sqlite:///rag.db --allow-misses
```

Recorded retrieval runs append compact JSONL rows to `data/retrieval_runs/history.jsonl`, which powers `GET /evaluation/retrieval-history`.

## Common Commands

```powershell
python simulator/rag/monitor.py --ciks 0000320193 --max 5
python scripts/ingest_poller.py --once --tickers AAPL MSFT --db sqlite:///rag.db --max-retries 1
python scripts/embed_worker.py --once --db sqlite:///rag.db --batch-size 64 --max-retries 1
python scripts/rag_jobs.py --db sqlite:///rag.db summary
python scripts/eval_retrieval.py --cases data/retrieval_cases/sec_basic_cases.json --db sqlite:///rag.db
python scripts/run_retrieval_suite.py --db sqlite:///rag.db --allow-misses
python -m simulator.rag.run_sec_ingestion --db sqlite:///rag.db --tickers AAPL MSFT
pytest -q simulator/tests/test_evaluation.py simulator/tests/test_replay.py
```

## Testing Notes

RAG tests live in `simulator/rag/tests/`. They mock SEC/network behavior and should remain deterministic. Do not add tests that require live SEC, NewsAPI, yfinance, OpenAI, or Anthropic calls.
