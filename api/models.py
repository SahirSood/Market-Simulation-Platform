"""Pydantic response models for all API endpoints."""
from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ── Bot models ────────────────────────────────────────────────────────────────

class BotSummary(BaseModel):
    bot_id:           str
    name:             str
    personality_tag:  str           # e.g. "Pessimistic Bear", derived from bot.name
    llm_provider:     str
    starting_cash:    float
    cash:             float
    total_value:      float         # mark_to_market()
    unrealized_pnl:   float
    realized_pnl:     float
    position_count:   int
    last_action:      Optional[str]
    last_ticker:      Optional[str]
    last_decision_at: Optional[datetime]


class PositionItem(BaseModel):
    ticker:         str
    quantity:       int
    avg_cost:       float
    current_price:  float
    unrealized_pnl: float


class DecisionSummary(BaseModel):
    id:              int
    timestamp:       datetime
    action:          str
    ticker:          Optional[str]
    quantity:        Optional[int]
    limit_price:     Optional[float]
    fill_count:      int
    fill_qty_total:  int
    fill_avg_price:  Optional[float]
    reasoning:       str            # truncated to 200 chars
    confidence:      Optional[float] = None
    evidence_ids:    list[int] = Field(default_factory=list)
    evidence_urls:   list[str] = Field(default_factory=list)
    speculative:     bool = False
    hold_cause:      Optional[str] = None


class BotDetail(BaseModel):
    bot_id:           str
    name:             str
    personality_tag:  str
    llm_provider:     str
    cash:             float
    total_value:      float
    unrealized_pnl:   float
    realized_pnl:     float
    positions:        list[PositionItem]
    recent_decisions: list[DecisionSummary]


# ── Market models ─────────────────────────────────────────────────────────────

class OrderLevel(BaseModel):
    price:    float
    quantity: int
    order_count: int = 0


class OrderBookSnapshot(BaseModel):
    ticker:      str
    bids:        list[OrderLevel]
    asks:        list[OrderLevel]
    spread:      Optional[float]
    mid_price:   Optional[float]
    trade_count: int


class TradeRecord(BaseModel):
    id:              int
    timestamp:       datetime
    bot_id:          str
    bot_name:        str
    action:          str
    ticker:          Optional[str]
    quantity:        Optional[int]
    fill_avg_price:  Optional[float]
    fill_qty_total:  int
    reasoning:       str            # truncated to 200 chars
    hold_cause:      Optional[str] = None


# ── Leaderboard models ────────────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    rank:              int
    bot_id:            str
    name:              str
    personality_tag:   str
    today_pnl:         float
    alltime_pnl:       float        # total_value - STARTING_CASH
    total_value:       float
    trade_count_today: int


class ReasoningEntry(BaseModel):
    id:                 int
    timestamp:          datetime
    action:             str
    ticker:             Optional[str]
    quantity:           Optional[int]
    limit_price:        Optional[float]
    reasoning:          str         # full text, not truncated
    headline_used:      Optional[str]
    confidence:         Optional[float] = None
    evidence_ids:       list[int] = Field(default_factory=list)
    evidence_urls:      list[str] = Field(default_factory=list)
    speculative:        bool = False
    hold_cause:         Optional[str] = None
    fill_count:         int
    fill_qty_total:     int
    fill_avg_price:     Optional[float]
    portfolio_snapshot: dict


# ── Sandbox models ────────────────────────────────────────────────────────────

class SandboxStatus(BaseModel):
    active:  bool
    message: str
