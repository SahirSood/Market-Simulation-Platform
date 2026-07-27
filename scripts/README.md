# Utility Scripts

Scripts in this directory support repeatable local development, release checks,
retrieval evaluation, replay runs, and operator smoke tests.

## Common Groups

- Deployment checks: `check_deploy_env.py`, `smoke_deployment.py`,
  `container_smoke.py`.
- Safety checks: `scan_tracked_secrets.py`.
- Replay and evaluation: `run_replay.py`, `run_replay_matrix.py`,
  `eval_retrieval.py`, `run_retrieval_suite.py`.
- RAG operations: `ingest_poller.py`, `embed_worker.py`, `dedupe_rag.py`,
  `rag_jobs.py`.
- Agent tooling examples: `agent_mcp_server.py`,
  `mcp_http_client_example.py`.

Run scripts from the repository root so relative fixture paths and imports line
up with the documented commands.
