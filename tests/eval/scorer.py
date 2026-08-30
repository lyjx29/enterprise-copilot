"""自写 LLM 评分器（ADR-13）：faithfulness / answer_relevancy（0-5）。

不引入 RAGAS，用本地 LLM 对 (question, answer, expected_points) 判分。
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm

SYSTEM_PROMPT = (
    "你是严谨的评估员。根据参考要点评估回答质量，输出 0-5 分。\n"
    "- faithfulness（忠实性）：回答中的关键数字/事实是否准确反映参考要点；编造或明显错误给低分。\n"
    "- answer_relevancy（相关性）：回答是否直接回答了问题；答非所问给低分。\n"
    '只输出 JSON：{"faithfulness": 0-5, "answer_relevancy": 0-5, "note": "一句话理由"}'
)


def score(question: str, answer: str, expected_points: list[str]) -> dict:
    """对单个回答判分，返回 {faithfulness, answer_relevancy, note}。"""
    points = "、".join(expected_points) if expected_points else "（无参考要点，按常识判断）"
    prompt = f"问题: {question}\n参考要点: {points}\n回答: {answer[:1500]}"
    llm = get_llm()
    resp = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])
    text = str(resp.content).strip()
    try:
        parsed = json.loads(text)
        return {
            "faithfulness": int(parsed.get("faithfulness", 0)),
            "answer_relevancy": int(parsed.get("answer_relevancy", 0)),
            "note": str(parsed.get("note", ""))[:120],
        }
    except (json.JSONDecodeError, ValueError):
        # LLM 未输出纯 JSON 时降级为文本推断
        return {"faithfulness": 0, "answer_relevancy": 0, "note": f"评分解析失败: {text[:80]}"}
