"""Local agent tools for Phase C.

This module is deliberately transport-agnostic: the API server, simulator, tests,
or a small MCP/stdio wrapper can all call the same tool registry. Tools return
plain dictionaries so they are easy to expose through MCP later without changing
bot code.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from risk import RiskLimits, risk_check_order


class MarketAgentToolServer:
    """In-process tool server used by experimental agent-backed decisions."""

    def __init__(
        self,
        price_feed,
        engine_adapter=None,
        rag_repository=None,
        embedding_service=None,
        bots: Optional[list] = None,
        risk_limits: Optional[RiskLimits] = None,
    ):
        self.price_feed = price_feed
        self.engine_adapter = engine_adapter
        self.rag_repository = rag_repository
        self.embedding_service = embedding_service
        self.risk_limits = risk_limits or RiskLimits()
        self._bots_by_id = {}
        self.set_bots(bots or [])

    def set_bots(self, bots: list) -> None:
        self._bots_by_id = {
            getattr(bot, "bot_id", ""): bot
            for bot in bots
            if getattr(bot, "bot_id", None)
        }

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": "market_snapshot",
                "description": "Return active tickers, last price, and order book snapshot for a ticker.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"ticker": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
            {
                "name": "portfolio_snapshot",
                "description": "Return a bot portfolio snapshot by bot_id.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"bot_id": {"type": "string"}},
                    "required": ["bot_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "retrieve_evidence",
                "description": "Retrieve RAG evidence for ticker and query text.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "query_text": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                    "required": ["query_text"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "risk_limits",
                "description": "Return deterministic simulator risk limits.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "name": "risk_check_order",
                "description": "Run deterministic risk checks for a proposed bot order.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "bot_id": {"type": "string"},
                        "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                        "ticker": {"type": "string"},
                        "quantity": {"type": "integer"},
                        "limit_price": {"type": ["number", "null"]},
                    },
                    "required": ["bot_id", "action", "ticker", "quantity"],
                    "additionalProperties": False,
                },
            },
        ]

    def call_tool(self, name: str, arguments: Optional[dict] = None) -> dict:
        arguments = arguments or {}
        if name == "market_snapshot":
            return self.market_snapshot(arguments.get("ticker"))
        if name == "portfolio_snapshot":
            return self.portfolio_snapshot(arguments["bot_id"])
        if name == "retrieve_evidence":
            return self.retrieve_evidence(
                ticker=arguments.get("ticker"),
                query_text=arguments.get("query_text", ""),
                top_k=int(arguments.get("top_k", 5)),
            )
        if name == "risk_limits":
            return self.risk_limits_tool()
        if name == "risk_check_order":
            return self.risk_check_order_tool(
                bot_id=arguments["bot_id"],
                action=arguments.get("action"),
                ticker=arguments.get("ticker"),
                quantity=arguments.get("quantity"),
                limit_price=arguments.get("limit_price"),
            )
        raise ValueError(f"Unknown agent tool: {name}")

    def market_snapshot(self, ticker: Optional[str] = None) -> dict:
        active_tickers = []
        get_active_tickers = getattr(self.price_feed, "get_active_tickers", None)
        if callable(get_active_tickers):
            active_tickers = list(get_active_tickers())

        symbol = (ticker or (active_tickers[0] if active_tickers else "")).upper().strip()
        price = None
        if symbol:
            price = float(self.price_feed.get_price(symbol))

        order_book = None
        if symbol and self.engine_adapter is not None:
            snapshot = self.engine_adapter.get_snapshot(symbol)
            trade_count = self.engine_adapter.get_trade_count(symbol)
            order_book = self._snapshot_to_dict(snapshot, trade_count)

        return {
            "ticker": symbol or None,
            "price": price,
            "active_tickers": active_tickers,
            "order_book": order_book,
        }

    def portfolio_snapshot(self, bot_id: str) -> dict:
        bot = self._get_bot(bot_id)
        snapshot = bot.portfolio.snapshot()
        try:
            snapshot["total_value"] = round(float(bot.portfolio.mark_to_market(self.price_feed)), 2)
        except Exception:
            snapshot["total_value"] = None
        return {
            "bot_id": bot_id,
            "bot_name": getattr(bot, "name", bot_id),
            "portfolio": snapshot,
        }

    def retrieve_evidence(self, ticker: Optional[str], query_text: str, top_k: int = 5) -> dict:
        if self.rag_repository is None or not query_text:
            return {"evidence": []}
        rows = self.rag_repository.retrieve_evidence(
            ticker=ticker,
            query_text=query_text,
            top_k=top_k,
            embedding_service=self.embedding_service,
        )
        if not rows and ticker:
            rows = self.rag_repository.retrieve_evidence(
                ticker=None,
                query_text=query_text,
                top_k=top_k,
                embedding_service=self.embedding_service,
            )
        return {"evidence": rows}

    def risk_limits_tool(self) -> dict:
        return {"risk_limits": self.risk_limits.to_dict()}

    def risk_check_order_tool(
        self,
        bot_id: str,
        action: str,
        ticker: Optional[str],
        quantity,
        limit_price=None,
    ) -> dict:
        bot = self._get_bot(bot_id)
        decision = SimpleNamespace(
            action=action,
            ticker=ticker,
            quantity=quantity,
            limit_price=limit_price,
        )
        return {
            "risk_check": risk_check_order(
                bot=bot,
                decision=decision,
                price_feed=self.price_feed,
                limits=self.risk_limits,
            ).to_dict()
        }

    def _get_bot(self, bot_id: str):
        bot = self._bots_by_id.get(bot_id)
        if bot is None:
            raise KeyError(f"Unknown bot_id: {bot_id}")
        return bot

    @staticmethod
    def _snapshot_to_dict(snapshot, trade_count: int) -> dict:
        if snapshot is None:
            return {
                "bids": [],
                "asks": [],
                "spread": None,
                "mid_price": None,
                "trade_count": trade_count,
            }
        return {
            "bids": [
                {"price": level.price, "quantity": int(level.total_quantity)}
                for level in getattr(snapshot, "bids", [])
            ],
            "asks": [
                {"price": level.price, "quantity": int(level.total_quantity)}
                for level in getattr(snapshot, "asks", [])
            ],
            "spread": getattr(snapshot, "spread", None),
            "mid_price": getattr(snapshot, "mid_price", None),
            "trade_count": trade_count,
        }
