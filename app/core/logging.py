"""structlog 结构化日志配置（JSON 输出，PROJECT_PLAN §12）。"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "INFO") -> None:
    """配置 structlog：JSON 行输出 + request_id contextvars。"""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            int(logging.getLevelName(level.upper()))
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
    )
