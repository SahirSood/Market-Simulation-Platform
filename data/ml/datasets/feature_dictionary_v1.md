# Replay ML Feature Dictionary v1

Rows represent one replay decision. Feature columns are available at the
decision timestamp. Label columns use future prices and must not be used as
training features.

| Column | Type | Source | Description | Leakage Risk |
| --- | --- | --- | --- | --- |
| `decision_id` | integer | replay decision row | Stable replay decision row id. | none |
| `run_id` | string | replay run | Replay run id. | none |
| `run_name` | string | replay run | Human-readable replay run name. | none |
| `run_status` | string | replay run | Run status at export time. | none |
| `input_fingerprint` | string | replay run | Hash of replay input events for same-input comparison. | none |
| `event_index` | integer | replay decision | Zero-based replay event index. | none |
| `as_of_time` | timestamp | replay decision | Decision timestamp used as the no-lookahead cutoff. | none |
| `mode` | string | constant | Dataset mode; currently replay. | none |
| `bot_id` | string | replay decision | Provider-specific bot id. | none |
| `bot_name` | string | replay decision | Display bot name. | none |
| `base_personality` | string | derived | Bot name without provider suffix. | none |
| `llm_provider` | string | replay decision | LLM provider used for the decision. | none |
| `model` | string | model metadata | Model name recorded with the replay decision. | none |
| `prompt_version` | string | model metadata | Prompt version recorded with the replay decision. | none |
| `prompt_hash` | string | model metadata | Prompt hash recorded with the replay decision. | none |
| `action` | string | replay decision | BUY, SELL, HOLD, or sanitized action. | none |
| `ticker` | string | replay decision | Decision ticker if a trade was proposed. | none |
| `quantity` | integer | replay decision | Proposed order quantity. | none |
| `limit_price` | float | replay decision | Proposed limit price when present. | none |
| `confidence` | float | replay decision | Model confidence score after parsing. | none |
| `speculative` | boolean | replay decision | Whether the model marked the idea speculative. | none |
| `reasoning_length` | integer | derived | Character length of stored public reasoning. | none |
| `headline_used` | string | replay decision | Headline cited by the model, if any. | none |
| `evidence_count` | integer | replay decision | Number of cited evidence ids. | none |
| `evidence_url_count` | integer | replay decision | Number of cited evidence URLs. | none |
| `risk_checked` | boolean | replay decision | Whether deterministic risk ran for this row. | none |
| `risk_approved` | boolean | replay decision | Risk approval result when checked. | none |
| `risk_blocked` | boolean | derived | True when risk checked and rejected the proposal. | none |
| `risk_reason` | string | replay decision | Risk approval or rejection reason. | none |
| `fill_count` | integer | replay decision | Recorded fill count. | none |
| `fill_qty_total` | integer | replay decision | Total filled quantity. | none |
| `fill_avg_price` | float | replay decision | Average fill price when filled. | none |
| `current_price` | float | event payload | Ticker price at decision time. | feature |
| `next_event_price` | float | future event payload | Ticker price at the next replay event. | label |
| `return_next_event` | float | future event payload | Raw ticker return from current to next replay event. | label |
| `signed_return_next_event` | float | future event payload | Return aligned to BUY or SELL direction. | label |
| `directional_correct_next_event` | boolean | derived label | True when signed next-event return is positive. | label |
| `intent_mark_pnl_next_event` | float | derived label | Intent PnL using proposed quantity and next-event mark. | label |
| `benchmark_symbol` | string | export argument | Benchmark used for relative labels. | none |
| `benchmark_price` | float | event payload | Benchmark price at decision time. | feature |
| `benchmark_next_event_price` | float | future event payload | Benchmark price at next replay event. | label |
| `benchmark_return_next_event` | float | future event payload | Benchmark return to next replay event. | label |
| `excess_return_vs_benchmark_next_event` | float | derived label | Signed return minus benchmark return. | label |
| `beat_benchmark_next_event` | boolean | derived label | True when signed return beats benchmark return. | label |
| `headline_count` | integer | event payload | Headline/context count visible at decision time. | feature |
| `real_headline_count` | integer | event payload | Non-synthetic headline/context count. | feature |
| `synthetic_headline_count` | integer | event payload | Synthetic headline/context count. | feature |
| `ticker_headline_count` | integer | event payload | Visible headline count for the selected ticker. | feature |
| `macro_headline_count` | integer | derived | Visible context rows classified as macro. | feature |
| `filing_headline_count` | integer | derived | Visible context rows classified as SEC/filing context. | feature |
| `earnings_headline_count` | integer | derived | Visible context rows classified as earnings context. | feature |
| `headline_source_count` | integer | derived | Number of distinct visible headline sources. | feature |
| `headline_sources` | string | derived | Semicolon-separated visible headline sources. | feature |
| `headline_age_minutes_min` | float | event payload | Minimum visible headline age in minutes. | feature |
| `headline_age_minutes_avg` | float | event payload | Average visible headline age in minutes. | feature |
| `has_real_news` | boolean | event payload | Whether real context was visible. | feature |
| `has_synthetic_market_summary` | boolean | event payload | Whether synthetic market summary text was visible. | feature |
| `news_context_quality` | string | derived | no_context, synthetic_only, mixed, or news_enriched. | feature |
| `event_spy_return_1d` | float | market regime | SPY one-day return known at event time. | feature |
| `event_qqq_return_1d` | float | market regime | QQQ one-day return known at event time. | feature |
| `event_tlt_return_1d` | float | market regime | TLT one-day return known at event time. | feature |
| `event_gld_return_1d` | float | market regime | GLD one-day return known at event time. | feature |
| `event_risk_regime` | string | market regime | Risk-on/risk-off classification. | feature |
| `event_trend_regime` | string | market regime | Broad trend classification. | feature |
| `event_volatility_regime` | string | market regime | Broad volatility classification. | feature |
| `event_breadth_proxy` | float | market regime | Breadth proxy known at event time. | feature |
| `ticker_return_1d` | float | generated features | Ticker one-day return known at event time. | feature |
| `ticker_return_5d` | float | generated features | Ticker five-day return known at event time. | feature |
| `ticker_return_20d` | float | generated features | Ticker twenty-day return known at event time. | feature |
| `ticker_rolling_volatility_20d` | float | generated features | Ticker rolling volatility known at event time. | feature |
| `ticker_volume_ratio_20d` | float | generated features | Ticker volume ratio known at event time. | feature |
| `ticker_gap_from_previous_close` | float | generated features | Ticker gap from previous close known at event time. | feature |
| `ticker_distance_from_20d_ma` | float | generated features | Ticker distance from 20-day MA known at event time. | feature |
