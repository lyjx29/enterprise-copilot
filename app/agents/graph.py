"""LangGraph 分层多 Agent 图（PROJECT_PLAN §8.3 / ADR-10）。

架构：Supervisor Router（结构化输出，可评估）→ 三个 Sub-agent（create_react_agent）。
- RAG: retrieve_docs → 判分 → rewrite → retry，可 web_search 跨路兜底
- SQL: get_schema → generate_sql → validate → execute（纵深防御）
- Web: web_search → 综合

记忆：M1 用 MemorySaver（内存）；M2 换 SqliteSaver（thread_id 持久化）。
"""

from __future__ import annotations

import re
from functools import lru_cache

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from app.agents.state import AgentState
from app.core.config import get_settings
from app.core.llm import get_llm
from app.schemas.agent import RouterQuery
from app.tools.retrieval import retrieve_docs, rewrite_query
from app.tools.sql import (
    execute_sql_query,
    generate_sql_query,
    get_database_schema,
    validate_sql_query,
)
from app.tools.web import web_search

# ---- 系统提示词 ----

ROUTER_PROMPT = """你是 FinCopilot 的路由器。判断用户问题应走哪条数据源路径，并提取查询理解信息：

- rag: 财报文档（SEC 10-K/Q）问题，如公司营收、利润、现金流等财务指标
- sql: 员工数据库结构化问题，如平均工资、员工数量、部门统计
- web: 实时/外部信息，或前两者无法覆盖的

同时提取：
- company / doc_type / fiscal_year / fiscal_quarter（供文档库 metadata 过滤）
- keywords（3-5 个检索关键词）
- rewritten_query（改写查询，澄清+去噪）
"""

RAG_PROMPT = """你是 FinCopilot 的财务文档分析师。基于检索到的财报文档回答用户问题。

工作流程：
1. 调用 retrieve_docs 检索相关文档，检索时传入 company/fiscal_year 过滤参数（若问题含公司/年份）
2. 若检索结果充分，直接给出带来源引用的回答（注明公司/年份/页码）
3. 若结果不足，调用 rewrite_query 改写查询后再次 retrieve_docs
4. 仍不足则调用 web_search 兜底，并说明"文档库未找到，以下来自网络"

规则：
- 检索 query 使用精确的财报术语（如 "total net sales"、"operating income"、
  "consolidated statements of operations"），避免口语化，以命中财务数据段落
- 只基于检索到的文档作答，绝不编造数字
- 回答保持简洁，先给结论再给依据
"""

SQL_PROMPT = """你是 FinCopilot 的 SQL 分析师。基于员工数据库回答结构化数据问题。

工作流程：
1. 调用 get_database_schema 了解表结构
2. 调用 generate_sql_query 生成 SQL（仅 SELECT）
3. 调用 validate_sql_query 校验安全性
4. 调用 execute_sql_query 执行并获取结果
5. 基于查询结果回答用户问题

规则：只用 SELECT；若校验或执行失败，修正后重试；回答给出结论与关键数字。
"""

WEB_PROMPT = """你是 FinCopilot 的实时信息分析师。搜索并综合实时信息回答用户问题。

工作流程：
1. 调用 web_search 搜索
2. 综合多个结果，给出带来源链接的回答

规则：引用来源链接；信息过时/不确定时如实说明。
"""


# ---- 工具 ----


def _last_human_text(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


def _format_history(messages: list, max_turns: int = 3) -> str:
    """取最近几轮对话历史（Human/AI），供 router 与分支 agent 理解上下文。"""
    turns = []
    for msg in messages[-max_turns * 2 :]:
        role = "用户" if isinstance(msg, HumanMessage) else "助手"
        text = str(msg.content).strip()
        if text:
            turns.append(f"{role}: {text[:300]}")
    return "\n".join(turns)


def _contextual_question(state: AgentState, question: str) -> str:
    """当前问题 + 历史上下文（不含当前问题本身）。"""
    history = _format_history(state["messages"][:-1]) if state.get("messages") else ""
    if not history:
        return question
    return f"历史对话:\n{history}\n\n当前问题: {question}"


# ---- Sub-agent 构建（模块级缓存，避免重复构建）----


@lru_cache(maxsize=1)
def _build_rag_agent():
    return create_react_agent(
        model=get_llm(),
        tools=[retrieve_docs, rewrite_query, web_search],
        prompt=RAG_PROMPT,
    )


@lru_cache(maxsize=1)
def _build_sql_agent():
    return create_react_agent(
        model=get_llm(),
        tools=[
            get_database_schema,
            generate_sql_query,
            validate_sql_query,
            execute_sql_query,
        ],
        prompt=SQL_PROMPT,
    )


@lru_cache(maxsize=1)
def _build_web_agent():
    return create_react_agent(
        model=get_llm(),
        tools=[web_search],
        prompt=WEB_PROMPT,
    )


def _final_answer(result: dict) -> str:
    """从 create_react_agent 结果中取最终 AI 回答文本。"""
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return str(msg.content)
        if isinstance(msg, ToolMessage):
            continue
    # 兜底：取最后一条消息
    if messages:
        return str(messages[-1].content)
    return "(未生成回答)"


def _extract_sources(text: str) -> list[dict]:
    """M1 简版来源提取：从回答文本中找 [company year p.N] 形如的引用。"""
    pattern = r"\[(score=[^|\]]*\|[^\]]*)\]"
    sources = []
    for m in re.finditer(pattern, text):
        parts = m.group(1).split("|")
        src: dict = {}
        for p in parts:
            k, _, v = p.strip().partition("=")
            if k in {"company", "doc_type", "year", "quarter", "page", "score"}:
                src[k] = v
        if src:
            sources.append(src)
    return sources


# ---- 节点 ----


def supervisor_router_node(state: AgentState) -> dict:
    """Supervisor Router：结构化输出 datasource + 查询理解（含历史上下文）。"""
    settings = get_settings()
    llm = get_llm(settings)
    structured = llm.with_structured_output(RouterQuery)
    question = _contextual_question(state, _last_human_text(state["messages"]))
    rq = structured.invoke([SystemMessage(content=ROUTER_PROMPT), HumanMessage(content=question)])
    return {"datasource": rq.datasource, "query_analysis": rq.model_dump()}


def rag_node(state: AgentState) -> dict:
    """RAG 分支：Sub-agent 自主检索/改写/兜底。"""
    agent = _build_rag_agent()
    question = _contextual_question(state, _last_human_text(state["messages"]))
    qa = RouterQuery(**state["query_analysis"])
    hint = ""
    if qa.company or qa.fiscal_year:
        hint = f"\n(上下文: 公司={qa.company or '?'}, 年份={qa.fiscal_year or '?'}, 文档={qa.doc_type or '?'})"
    result = agent.invoke({"messages": [HumanMessage(content=f"{question}{hint}")]})
    answer = _final_answer(result)
    return {
        "messages": [AIMessage(content=answer)],
        "retrieved_docs": answer,
        "sources": _extract_sources(answer),
    }


def sql_node(state: AgentState) -> dict:
    """SQL 分支：Sub-agent 生成/校验/执行。"""
    agent = _build_sql_agent()
    question = _contextual_question(state, _last_human_text(state["messages"]))
    result = agent.invoke({"messages": [HumanMessage(content=question)]})
    answer = _final_answer(result)
    return {"messages": [AIMessage(content=answer)], "sql_result": answer}


def web_node(state: AgentState) -> dict:
    """Web 分支：Sub-agent 搜索/综合。"""
    agent = _build_web_agent()
    question = _contextual_question(state, _last_human_text(state["messages"]))
    result = agent.invoke({"messages": [HumanMessage(content=question)]})
    answer = _final_answer(result)
    return {"messages": [AIMessage(content=answer)], "web_results": answer}


# ---- 图组装 ----


def build_graph(checkpointer=None):
    """组装并编译分层多 Agent 图。

    checkpointer：M1 默认 MemorySaver（内存）；M2 起由调用方注入 SqliteSaver（thread_id 持久化）。
    """
    builder = StateGraph(AgentState)
    builder.add_node("supervisor", supervisor_router_node)
    builder.add_node("rag", rag_node)
    builder.add_node("sql", sql_node)
    builder.add_node("web", web_node)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        lambda state: state.get("datasource", "rag"),
        {"rag": "rag", "sql": "sql", "web": "web"},
    )
    builder.add_edge("rag", END)
    builder.add_edge("sql", END)
    builder.add_edge("web", END)

    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)
