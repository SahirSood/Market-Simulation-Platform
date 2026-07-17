# Retrieval Benchmark Cases

These JSON files define labeled RAG retrieval checks for SEC evidence quality.
They are meant to run locally against whatever `rag.db` or `DATABASE_URL` you
have populated through SEC ingestion.

Run the default case file:

```powershell
python scripts/eval_retrieval.py --cases data/retrieval_cases/sec_basic_cases.json --db sqlite:///rag.db
```

Case fields:

- `name`: human-readable case label.
- `ticker`: optional ticker filter.
- `query_text`: retrieval query.
- `as_of_date`: optional no-lookahead timestamp.
- `top_k`: number of evidence chunks to inspect.
- `expected_chunk_ids`: optional local chunk ids.
- `expected_document_ids`: optional local document ids.
- `expected_accession_nos`: stable SEC accession labels when known.
- `expected_source_urls`: stable source URLs when known.
- `expected_text_contains`: portable fallback labels that should appear in a
  relevant returned chunk.

At least one expected field should be present. Cases with `expected_text_contains`
are easiest to use across different local databases.
