"""
AppState singleton — holds all live simulator objects.
server.py calls init() once at startup; routers read via get().
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AppState:
    bots:               list                              # list[BaseBot]
    engine_adapter:     object                            # EngineAdapter
    reasoning_log:      object                            # ReasoningLog
    price_feed:         object                            # PriceFeed
    news_feed:          object                            # NewsFeed
    scheduler:          object                            # BotScheduler
    noise_pool:         object                            # NoiseTraderPool
    event_loop:         asyncio.AbstractEventLoop
    replay_store:       object = None                     # ReplayStore for Phase D runs
    rag_repository:     object = None                     # RagRepository for evidence drilldown
    embedding_service:  object = None                     # Optional embedding service for evals
    risk_limits:        object = None                     # Shared scheduler/tool risk limits
    agent_tool_server:  object = None                     # Shared local MCP/tool registry
    mcp_http_adapter:   object = None                     # Optional HTTP MCP adapter
    sandbox_active:     bool   = False
    sandbox_scheduler:  object = None                     # BotScheduler for sandbox


_state: Optional[AppState] = None


def get() -> AppState:
    if _state is None:
        raise RuntimeError("AppState not initialised — call init() first")
    return _state


def init(state: AppState) -> None:
    global _state
    _state = state
