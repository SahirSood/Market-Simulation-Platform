# Data Fixtures

This directory contains small, publishable fixtures used for deterministic
retrieval and replay checks. It does not contain private market data, real
credentials, or generated local databases.

## Contents

- `retrieval_cases/`: labeled RAG benchmark cases for SEC evidence retrieval.
- `replay_events/`: synthetic replay scenarios for same-input model
  comparisons.

Local SQLite databases such as `rag.db`, `marketsim.db`, and replay outputs are
ignored by git. Keep generated benchmark history under ignored local paths
unless a fixture is intentionally curated for repeatable review.
