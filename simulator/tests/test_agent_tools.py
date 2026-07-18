import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_mcp import AgentMcpAdapter
from agent_tools import MarketAgentToolServer
from bots.analyst_bot import AnalystBot
from portfolio import Portfolio
from rag.repository import RagRepository


class PriceFeed:
    def get_price(self, ticker):
        return 100.0

    def get_active_tickers(self):
        return ["AAPL", "MSFT"]


class NewsFeed:
    def get_trending(self):
        return [{"title": "Revenue growth accelerates", "source": "Test", "age_label": "now"}]

    def get_recent(self):
        return []

    def get_latest(self, ticker, n=3):
        return []


def _bot():
    bot = SimpleNamespace()
    bot.bot_id = "bot-1"
    bot.name = "Bot One"
    bot.portfolio = Portfolio(10_000.0)
    return bot


def test_agent_tools_expose_market_portfolio_evidence_and_risk():
    repo = RagRepository("sqlite:///:memory:")
    repo.create_tables()
    repo.add_document_with_chunks(
        ticker="AAPL",
        title="Apple filing",
        source_url="http://example.com/aapl",
        content="Revenue increased and cash flow improved.",
        chunks=[{"content": "Revenue increased and cash flow improved.", "start_pos": 0, "end_pos": 41}],
    )
    bot = _bot()
    server = MarketAgentToolServer(
        price_feed=PriceFeed(),
        rag_repository=repo,
        bots=[bot],
    )

    market = server.call_tool("market_snapshot", {"ticker": "AAPL"})
    portfolio = server.call_tool("portfolio_snapshot", {"bot_id": "bot-1"})
    evidence = server.call_tool(
        "retrieve_evidence",
        {"ticker": "AAPL", "query_text": "Revenue", "top_k": 1},
    )
    risk = server.call_tool(
        "risk_check_order",
        {"bot_id": "bot-1", "action": "BUY", "ticker": "AAPL", "quantity": 10, "limit_price": 100.0},
    )

    assert market["price"] == 100.0
    assert portfolio["portfolio"]["cash"] == 10_000.0
    assert evidence["evidence"][0]["chunk_id"] == 1
    assert risk["risk_check"]["approved"] is True


def test_agent_mcp_adapter_lists_and_calls_tools():
    server = MarketAgentToolServer(price_feed=PriceFeed(), bots=[_bot()])
    adapter = AgentMcpAdapter(server)

    listed = adapter.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    called = adapter.handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "risk_limits", "arguments": {}},
        }
    )

    assert listed["result"]["tools"][0]["name"] == "market_snapshot"
    assert "max_order_quantity" in called["result"]["content"][0]["text"]
    assert called["result"]["structuredContent"]["risk_limits"]["max_order_quantity"] == 250


def test_agent_mcp_adapter_enforces_auth_and_approval():
    server = MarketAgentToolServer(price_feed=PriceFeed(), bots=[_bot()])
    adapter = AgentMcpAdapter(
        server,
        auth_token="secret",
        approval_required={"risk_check_order"},
    )

    denied = adapter.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    listed = adapter.handle({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "_meta": {"authorization": "Bearer secret"},
    })
    approval_denied = adapter.handle({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "_meta": {"authorization": "Bearer secret"},
        "params": {
            "name": "risk_check_order",
            "arguments": {"bot_id": "bot-1", "action": "BUY", "ticker": "AAPL", "quantity": 1},
        },
    })
    approved = adapter.handle({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "_meta": {"authorization": "Bearer secret"},
        "params": {
            "name": "risk_check_order",
            "arguments": {"bot_id": "bot-1", "action": "BUY", "ticker": "AAPL", "quantity": 1},
            "_meta": {"approved": True},
        },
    })

    assert denied["error"]["code"] == -32001
    assert listed["result"]["tools"]
    assert approval_denied["error"]["code"] == -32001
    assert approved["result"]["structuredContent"]["risk_check"]["approved"] is True
    assert adapter.traces[-1]["tool"] == "risk_check_order"


def test_agent_mcp_adapter_filters_tools_and_keeps_safe_trace_metadata():
    server = MarketAgentToolServer(price_feed=PriceFeed(), bots=[_bot()])
    adapter = AgentMcpAdapter(
        server,
        allowed_tools={"risk_limits"},
    )

    listed = adapter.handle({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "_meta": {
            "client_name": "smoke-client",
            "run_id": "run-1",
            "arguments": "must-not-appear",
        },
    })
    blocked = adapter.handle({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "market_snapshot", "arguments": {"ticker": "AAPL"}},
    })

    assert [tool["name"] for tool in listed["result"]["tools"]] == ["risk_limits"]
    assert blocked["error"]["code"] == -32001
    assert adapter.traces[0]["metadata"]["client_name"] == "smoke-client"
    assert adapter.traces[0]["metadata"]["run_id"] == "run-1"
    assert "arguments" not in adapter.traces[0]["metadata"]


def test_analyst_tool_path_injects_context_and_preflights_risk(monkeypatch):
    server = MarketAgentToolServer(price_feed=PriceFeed())
    bot = AnalystBot(
        PriceFeed(),
        NewsFeed(),
        "claude",
        agent_tool_server=server,
        use_agent_tools=True,
    )
    server.set_bots([bot])

    seen_prompts = []

    def fake_call_llm(prompt):
        seen_prompts.append(prompt)
        return {
            "action": "BUY",
            "ticker": "AAPL",
            "quantity": 50,
            "limit_price": 1000.0,
            "reasoning": "large conviction trade",
            "headline_used": "Revenue growth accelerates",
            "confidence": 0.9,
            "evidence_ids": [],
            "speculative": True,
        }

    monkeypatch.setattr(bot, "_call_llm", fake_call_llm)

    decision = bot.decide()

    assert "AGENT TOOL CONTEXT" in seen_prompts[0]
    assert decision.action == "HOLD"
    assert "Agent risk preflight rejected" in decision.reasoning
