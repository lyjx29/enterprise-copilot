"""CLI 入口：python -m app.agents.run --query "..."

用于 M1 本地验证分层多 Agent 图（无需 API 服务）。
"""
from __future__ import annotations

import argparse

from langchain_core.messages import HumanMessage

from app.agents.graph import build_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="FinCopilot Agent CLI")
    parser.add_argument("--query", required=True, help="要回答的问题")
    args = parser.parse_args()

    graph = build_graph()
    result = graph.invoke(
        {"messages": [HumanMessage(content=args.query)]},
        config={"configurable": {"thread_id": "cli"}},
    )
    print(f"\n[datasource] {result.get('datasource', '?')}")
    print("=" * 60)
    print(result["messages"][-1].content)


if __name__ == "__main__":
    main()
