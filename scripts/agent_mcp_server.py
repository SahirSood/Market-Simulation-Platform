"""Run the local agent tool server over newline-delimited JSON-RPC.

This standalone entry point exposes market snapshot, evidence retrieval, risk
limits, and risk checks where bot state is registered by the host process. The
API/simulator use the same MarketAgentToolServer in-process with live bots.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM_DIR = ROOT / "simulator"
if str(SIM_DIR) not in sys.path:
    sys.path.insert(0, str(SIM_DIR))

from agent_mcp import AgentMcpAdapter
from agent_tools import MarketAgentToolServer
from engine_adapter import EngineAdapter
from price_feed import PriceFeed
from rag.embeddings import get_openai_embedding_service_from_env
from rag.repository import RagRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Local MCP-style market agent tool server")
    parser.add_argument("--db", default=os.getenv("DATABASE_URL"), help="SQLAlchemy DB URL for RAG")
    parser.add_argument(
        "--token",
        default=os.getenv("AGENT_MCP_TOKEN"),
        help="Optional bearer token required for tools/list and tools/call",
    )
    parser.add_argument(
        "--approval-required",
        default=os.getenv("AGENT_MCP_APPROVAL_REQUIRED", ""),
        help="Comma-separated tool names that require _meta.approved=true",
    )
    args = parser.parse_args()

    rag_repository = None
    embedding_service = None
    if args.db:
        rag_repository = RagRepository(args.db)
        rag_repository.create_tables()
        embedding_service = get_openai_embedding_service_from_env()

    tool_server = MarketAgentToolServer(
        price_feed=PriceFeed(),
        engine_adapter=EngineAdapter(),
        rag_repository=rag_repository,
        embedding_service=embedding_service,
    )
    approval_required = {
        item.strip()
        for item in args.approval_required.split(",")
        if item.strip()
    }
    AgentMcpAdapter(
        tool_server,
        auth_token=args.token,
        approval_required=approval_required,
    ).serve_stdio(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
