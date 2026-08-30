"""V2-M4 报告生成：读 matrix_report.json，输出系统化评测报告（markdown）。

用法：
    python -m tests.eval.analysis
"""
from __future__ import annotations

import json
from pathlib import Path

REPORT_PATH = Path("data/matrix_report.json")
OUT_PATH = Path("docs/EVAL_REPORT.md")


def _fmt(f: float) -> str:
    return f"{f:.2f}"


def generate() -> str:
    data = json.loads(REPORT_PATH.read_text())
    reports = data["reports"]
    configs = {c["name"]: c["desc"] for c in data["configs"]}

    lines: list[str] = []
    lines.append("# FinCopilot v2 · 评测矩阵报告\n")
    lines.append(f"> 生成时间：{Path(REPORT_PATH).stat().st_mtime_ns}\n")
    lines.append("本报告对比不同检索参数组合在金标集上的表现（faithfulness / answer_relevancy，0-5）。\n")

    # 总体对比表
    lines.append("## 总体对比\n")
    lines.append("| 组合 | 说明 | 金标数 | Faithfulness | Answer Relevancy |")
    lines.append("|---|---|---|---|---|")
    for name, r in reports.items():
        o = r["overall"]
        lines.append(
            f"| {name} | {configs.get(name, '')} | {o['count']} | {_fmt(o['faithfulness'])} | {_fmt(o['answer_relevancy'])} |"
        )
    lines.append("")

    # 按类别对比
    lines.append("## 按类别对比\n")
    all_types = sorted({t for r in reports.values() for t in r["by_type"]})
    lines.append("| 类别 | " + " | ".join(f"{r['name']} F/R" for r in reports.values()) + " |")
    lines.append("|" + "---|" * (len(reports) + 1))
    for t in all_types:
        cells = []
        for r in reports.values():
            f_, r_ = r["by_type"].get(t, (0.0, 0.0))
            cells.append(f"{_fmt(f_)}/{_fmt(r_)}")
        lines.append(f"| {t} | " + " | ".join(cells) + " |")
    lines.append("")

    # 每组合最佳/最差
    lines.append("## 亮点与问题\n")
    for name, r in reports.items():
        o = r["overall"]
        best = max(r["items"], key=lambda i: i["scores"]["faithfulness"], default=None)
        worst = min(r["items"], key=lambda i: i["scores"]["faithfulness"], default=None)
        if best:
            lines.append(f"- **{name}** 最佳：`{best['id']}` (f={best['scores']['faithfulness']})")
        if worst:
            lines.append(f"- **{name}** 待改进：`{worst['id']}` (f={worst['scores']['faithfulness']}) 回答：{worst['answer'][:80]}")
    lines.append("")

    # 明细
    lines.append("## 明细\n")
    for name, r in reports.items():
        lines.append(f"### {name}（{configs.get(name, '')}）\n")
        lines.append("| ID | 类型 | F | R |")
        lines.append("|---|---|---|---|")
        for i in r["items"]:
            lines.append(f"| {i['id']} | {i['type']} | {i['scores']['faithfulness']} | {i['scores']['answer_relevancy']} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    if not REPORT_PATH.exists():
        raise SystemExit(f"找不到 {REPORT_PATH}（请先运行评测矩阵）")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(generate())
    print(f"报告已写入 {OUT_PATH}")


if __name__ == "__main__":
    main()
