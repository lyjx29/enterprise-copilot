"""评估脚本：跑金标集 + 自写评分器，输出报告。

用法：
    python -m tests.eval.run                # 全量
    python -m tests.eval.run --filter rag   # 只跑 rag 类
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.agents.graph import build_graph
from tests.eval.scorer import score

GOLDEN_PATH = Path(__file__).parent / "golden_set.json"


def run(filter_type: str | None = None, sample: int | None = None) -> dict:
    golden = json.loads(GOLDEN_PATH.read_text())
    graph = build_graph()
    results = []

    questions = [q for q in golden["questions"] if not filter_type or q["type"] == filter_type]
    if sample:
        questions = questions[:sample]

    for item in questions:
        thread_id = f"eval-{item['id']}"
        # followup 先跑 context 建立记忆
        if item.get("context"):
            graph.invoke(
                {"messages": [HumanMessage(content=item["context"])]},
                config={"configurable": {"thread_id": thread_id}},
            )
        result = graph.invoke(
            {"messages": [HumanMessage(content=item["question"])]},
            config={"configurable": {"thread_id": thread_id}},
        )
        answer = result["messages"][-1].content
        scores = score(item["question"], answer, item["expected_points"])
        results.append(
            {
                "id": item["id"],
                "type": item["type"],
                "question": item["question"],
                "scores": scores,
                "answer_excerpt": answer[:200],
            }
        )
        print(f"[{item['id']}] f={scores['faithfulness']} r={scores['answer_relevancy']}")

    # 汇总报告
    valid = [
        r for r in results if r["scores"]["faithfulness"] > 0 or r["scores"]["answer_relevancy"] > 0
    ]
    report = {
        "total": len(results),
        "scored": len(valid),
        "avg_faithfulness": round(sum(r["scores"]["faithfulness"] for r in valid) / len(valid), 2)
        if valid
        else 0,
        "avg_answer_relevancy": round(
            sum(r["scores"]["answer_relevancy"] for r in valid) / len(valid), 2
        )
        if valid
        else 0,
        "results": results,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="FinCopilot 金标评估")
    parser.add_argument(
        "--filter", choices=["rag", "sql", "web", "followup", "edge", "mixed"], default=None
    )
    parser.add_argument("--sample", type=int, default=None, help="只跑前 N 条（调试用）")
    args = parser.parse_args()

    report = run(args.filter, args.sample)
    out = Path("data/eval_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n报告已写入 {out}")
    print(
        f"总数={report['total']} 有效={report['scored']} "
        f"avg_faithfulness={report['avg_faithfulness']} avg_relevancy={report['avg_answer_relevancy']}"
    )


if __name__ == "__main__":
    sys.exit(main())
