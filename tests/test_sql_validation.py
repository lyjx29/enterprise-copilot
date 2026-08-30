"""SQL 纵深防御校验单测（PROJECT_PLAN §11 L2/L3）。

验证 sqlglot AST 校验能拦截各类绕过手段（大小写/注释/多语句/越权表等）。
"""

from __future__ import annotations

import pytest

from app.tools.sql import validate_sql

ALLOWED = ["employees", "departments", "dept_emp", "salaries", "titles"]


def _ok(sql: str) -> str:
    return validate_sql(sql, ALLOWED)


def _rejected(sql: str) -> str:
    with pytest.raises(ValueError):
        validate_sql(sql, ALLOWED)


# ---- 合法 SELECT（应通过）----


def test_plain_select():
    assert "SELECT COUNT(*)" in _ok("SELECT COUNT(*) FROM employees")


def test_select_with_where_join():
    _ok(
        "SELECT d.dept_name, AVG(s.salary) FROM salaries s "
        "JOIN dept_emp de ON s.emp_no = de.emp_no "
        "JOIN departments d ON de.dept_no = d.dept_no GROUP BY d.dept_name"
    )


def test_code_block_stripped():
    out = _ok("```sql\nSELECT COUNT(*) FROM employees;\n```")
    assert "```" not in out and out.endswith("FROM employees")


def test_keywords_normalized():
    _ok("select count(*) from employees where emp_no = 10001")


# ---- 危险/越权 SQL（应被拒绝）----


def test_ddl_insert_rejected():
    _rejected("INSERT INTO employees VALUES (1, 'a')")


def test_ddl_drop_rejected():
    _rejected("DROP TABLE employees")


def test_ddl_update_rejected():
    _rejected("UPDATE employees SET salary = 0")


def test_multi_statement_semicolon_rejected():
    _rejected("SELECT COUNT(*) FROM employees; DROP TABLE employees")


def test_comment_injection_rejected():
    _rejected("SELECT COUNT(*) FROM employees-- DROP TABLE employees")


def test_sqlite_pragma_rejected():
    _rejected("PRAGMA writable_schema=ON")


def test_sqlite_attach_rejected():
    _rejected("ATTACH DATABASE 'x.db' AS evil")


def test_case_insensitive_dml_rejected():
    _rejected("sElEcT COUNT(*) FROM employees; dRoP tAbLe employees")


def test_unknown_table_rejected():
    _rejected("SELECT * FROM sqlite_master")


def test_table_outside_whitelist_rejected():
    _rejected("SELECT * FROM users")
