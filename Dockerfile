# syntax=docker/dockerfile:1
# 多阶段构建 + 非 root 运行（PROJECT_PLAN §14.3）

# ---- 阶段一：构建依赖 ----
FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /build
RUN pip install --no-cache-dir uv
# 先拷 pyproject，利用 Docker 层缓存
COPY pyproject.toml README.md ./
COPY app ./app
RUN uv pip install --system --no-cache-dir .

# ---- 阶段二：运行（非 root）----
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app ./app

# 非 root 用户
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data /app/debug_logs \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
