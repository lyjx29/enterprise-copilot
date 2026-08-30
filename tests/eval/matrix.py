"""评测矩阵（V2-M3）：参数组合 × 金标 自动化对比。

每次评测 = 1 次 graph 调用（回答）+ 1 次 LLM 判分。多组合 × 多金标 = 大量 LLM 调用。

用法：
    python -m tests.eval.matrix --sample 3        # 每组合跑前 3 条（验证）
    python -m tests.eval.matrix --filter rag      # 只跑 rag 类
    python -m tests.eval.matrix                    # 全量（耗时长，消耗大量 token）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.agents.graph import build_graph
from app.core.config import get_settings
from tests.eval.scorer import score

GOLDEN_PATH = Path(__file__).parent / "golden_set.json"

CONFIGS = [
    {"name": "rerank-on", "env": {"RERANK_ENABLED": "true"}, "desc": "双路+RRF+LLM精排"},
    {"name": "rerank-off", "env": {"RERANK_ENABLED": "false"}, "desc": "仅双路+RRF（无精排）"},
]


def _set_env(env: dict) -> None:
    """切换参数组合（env + 刷新 settings 缓存）。"""
    os.environ.update(env)
    get_settings.cache_clear()


def _avg(items: list[dict]) -> tuple[float, float]:
    if not items:
        return 0.0, 0.0
    return (
        round(sum(i["faithfulness"] for i in items) / len(items), 2),
        round(sum(i["answer_relevancy"] for i in items) / len(items), 2),
    )


def run_config(cfg: dict, filter_type: str | None, sample: int | None) -> dict:
    """跑一个参数组合的金标子集，返回汇总报告。"""
    _set_env(cfg["env"])
    graph = build_graph()
    golden = json.loads(GOLDEN_PATH.read_text())
    allowed = set(filter_type.split(",")) if filter_type else None
    questions = [
        q for q in golden["questions"] if not allowed or q["type"] in allowed
    ]
    if sample:
        questions = questions[:sample]

    by_type: dict[str, list] = defaultdict(list)
    items = []
    for item in questions:
        thread_id = f"m-{cfg['name']}-{item['id']}"
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
        s = score(item["question"], answer, item["expected_points"])
        by_type[item["type"]].append(s)
        items.append({"id": item["id"], "type": item["type"], "scores": s, "answer": answer[:120]})
        print(f"  [{cfg['name']}] {item['id']} f={s['faithfulness']} r={s['answer_relevancy']}")

    type_summary = {t: _avg(v) for t, v in sorted(by_type.items())}
    all_items = [i for v in by_type.values() for i in v]
    overall = _avg(all_items)
    return {
        "name": cfg["name"],
        "desc": cfg["desc"],
        "overall": {"faithfulness": overall[0], "answer_relevancy": overall[1], "count": len(all_items)},
        "by_type": type_summary,
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="FinCopilot 评测矩阵（参数×金标）")
    parser.add_argument(
        "--filter",
        default=None,
        help="逗号分隔的类别过滤，如 rag,sql（留空=全部）",
    )
    parser.add_argument("--sample", type=int, default=None, help="每组合只跑前 N 条（验证用）")
    args = parser.parse_args()
    args.filter = args.filter.replace(",", ",") if args.filter else None

    reports = {}
    for cfg in CONFIGS:
        print(f"\n=== 组合: {cfg['name']} ({cfg['desc']}) ===")
        reports[cfg["name"]] = run_config(cfg, args.filter, args.sample)

    print("\n" + "=" * 64)
    print("评测矩阵汇总（faithfulness / answer_relevancy）")
    for name, r in reports.items():
        o = r["overall"]
        print(f"{name:12} 总体 {o['faithfulness']} / {o['answer_relevancy']}  (n={o['count']})")
        for t, (f_, r_) in r["by_type"].items():
            print(f"  {t:10} {f_} / {r_}")

    out = Path("data/matrix_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"configs": CONFIGS, "reports": reports}, ensure_ascii=False, indent=2))
    print(f"\n报告已写入 {out}")


if __name__ == "__main__":
    sys.exit(main())
