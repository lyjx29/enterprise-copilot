"""SQL 工具集（Text-to-SQL + 纵深防御安全，见 PROJECT_PLAN §11）。

- get_database_schema  取表结构（供 LLM 生成 SQL）
- generate_sql_query   NL → SQL（内嵌 LLM）
- validate_sql_query   sqlglot AST 校验 + 表白名单（L2/L3）
- execute_sql_query    只读连接执行（L4，物理只读）+ 行数限制
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import sqlglot
from langchain_core.tools import tool
from sqlalchemy import create_engine, inspect, text

from app.core.config import Settings, get_settings
from app.core.llm import get_llm

# ---- 数据库连接（纵深防御 L4：物理只读）----

def _readonly_db_uri(settings: Settings) -> str:
    """构造只读 SQLite URI。SQLite 以 mode=ro 打开时物理无法写入。

    - SQLite file: URI 的相对路径解析有歧义，统一转绝对路径
    - SQLAlchemy 要求 uri=true 放在 URL query 中
    """
    uri = settings.employees_db_uri
    db_path = uri[len("sqlite:///") :] if uri.startswith("sqlite:///") else uri
    abs_path = str(Path(db_path).resolve())
    return f"sqlite:///file:{abs_path}?mode=ro&uri=true"


def _readonly_engine(settings: Settings):
    return create_engine(_readonly_db_uri(settings))


def _get_schema(settings: Settings) -> str:
    """返回员工库全量 DDL（供 LLM 生成 SQL 时参考）。"""
    engine = _readonly_engine(settings)
    insp = inspect(engine)
    lines = []
    for table in insp.get_table_names():
        cols = insp.get_columns(table)
        col_str = ", ".join(f"{c['name']} {c['type']}" for c in cols)
        lines.append(f"CREATE TABLE {table} ({col_str});")
    engine.dispose()
    return "\n".join(lines)


# ---- 纵深防御校验（L2 语法解析 + L3 白名单）----

def validate_sql(sql: str, allowed_tables: list[str]) -> str:
    """sqlglot AST 校验：顶层 SELECT、单语句、无危险 token、表名白名单。

    返回清洗后的 SQL（去代码块标记、去尾分号）。
    校验失败抛 ValueError。
    """
    # 基础清洗：去 markdown 代码块标记
    clean = re.sub(r"```(?:sql)?", "", sql).strip()
    clean = clean.strip().rstrip(";")

    # L2a：危险 token 兜底（注释/分号拼接/SQLite 特有面）
    upper = clean.upper()
    for bad in ("--", "/*", "*/", "PRAGMA", "ATTACH", "VACUUM", "REINDEX", "LOAD_EXTENSION"):
        if bad in upper:
            raise ValueError(f"禁止的 token: {bad}")

    # L2b：解析为 AST，必须恰好一条且是 SELECT
    statements = sqlglot.parse(clean)
    if len(statements) != 1:
        raise ValueError("仅允许单条 SQL 语句")
    stmt = statements[0]
    if not isinstance(stmt, sqlglot.exp.Select):
        raise ValueError(f"仅允许 SELECT 查询，实际为 {type(stmt).__name__}")

    # L3：表名白名单
    for table in stmt.find_all(sqlglot.exp.Table):
        if table.name.lower() not in [t.lower() for t in allowed_tables]:
            raise ValueError(f"表 {table.name} 不在白名单中")

    return clean


# ---- 工具定义 ----

@tool
def get_database_schema() -> str:
    """获取员工数据库的表结构（DDL）。生成 SQL 前先调用此工具了解结构。"""
    settings = get_settings()
    return _get_schema(settings)


@tool
def generate_sql_query(question: str) -> str:
    """根据自然语言问题生成一条 SQL SELECT 查询。

    需先调用 get_database_schema 了解表结构。返回纯 SQL 字符串。
    """
    settings = get_settings()
    schema = _get_schema(settings)
    prompt = (
        "基于以下数据库 schema：\n"
        f"{schema}\n\n"
        f"为问题生成一条 SQL 查询：{question}\n\n"
        "规则：\n"
        "- 只使用 SELECT 语句\n"
        "- 只访问 schema 中存在的表\n"
        "- 返回纯 SQL，不要代码块标记\n"
    )
    llm = get_llm(settings)
    resp = llm.invoke(prompt)
    return str(resp.content)


@tool
def validate_sql_query(query: str) -> str:
    """校验 SQL 安全性（纵深防御 L2/L3）。

    仅允许：单条 SELECT + 白名单表。校验通过返回 'Valid: <sql>'，否则返回 'Error: ...'。
    """
    settings = get_settings()
    try:
        clean = validate_sql(query, settings.sql_allowed_tables)
    except ValueError as exc:
        return f"Error: {exc}"
    return f"Valid: {clean}"


@tool
def execute_sql_query(sql_query: str) -> str:
    """执行已校验的 SQL 查询并返回结果。

    内部先做纵深防御校验，再以只读连接执行；强制 LIMIT 限制返回行数。
    校验失败返回 'Error: ...'。
    """
    settings = get_settings()
    try:
        clean = validate_sql(sql_query, settings.sql_allowed_tables)
    except ValueError as exc:
        return f"校验失败: {exc}"

    engine = _readonly_engine(settings)
    try:
        with engine.connect() as conn:
            if "limit" not in clean.lower():
                clean = f"{clean} LIMIT {settings.sql_max_rows}"
            start = time.monotonic()
            result = conn.execute(text(clean))
            rows = result.fetchmany(settings.sql_max_rows + 1)
            elapsed = time.monotonic() - start
            cols = list(result.keys())
    except Exception as exc:  # 只读连接下任何写操作都会在此失败（L4 兜底）
        return f"执行失败: {exc}"
    finally:
        engine.dispose()

    limited = len(rows) > settings.sql_max_rows
    rows = rows[: settings.sql_max_rows]
    return f"Columns: {cols}\nRows: {rows}\n(耗时 {elapsed:.2f}s, 截断={limited})"
