# FinCopilot · 多源自适应财务分析师 Copilot

一个能自动判断"用户问题该查哪条路"的财务分析师智能体，三路自动路由：

| 路径 | 数据源 | 技术 |
|---|---|---|
| **RAG 文档** | SEC 财报（10-K/Q）| 企业级混合检索：层级语义分块 → bi-encoder → Qdrant → 双路召回 → RRF 融合 → cross-encoder 精排 → Self-RAG 门控 |
| **SQL 数据库** | 员工库 | Text-to-SQL，纵深防御 5 层（sqlglot 校验 + 白名单 + 只读连接）|
| **Web 实时** | 联网搜索 | DuckDuckGo 兜底 |

## 技术栈

Python 3.12 · FastAPI · LangGraph 1.x（分层多 Agent）· Qdrant · Ollama 本地优先（可切云端）· SSE 流式 · Docker Compose

## 三步运行

> 详细架构见 [PROJECT_PLAN.md](PROJECT_PLAN.md)（项目的唯一事实来源）。

```bash
# 1. 准备环境
cp .env.example .env

# 2. 一键起服务（api + qdrant）
docker compose up --build

# 3. 验证
curl http://localhost:8000/v1/health
# → {"status":"ok","version":"0.1.0"}
```

API 文档：http://localhost:8000/docs

## 项目结构

```
app/
├── main.py          # FastAPI 入口（lifespan 生命周期）
├── api/             # HTTP 路由、SSE、中间件
├── services/        # chat / thread / ingest 业务编排
├── agents/          # LangGraph 分层多 Agent
├── tools/           # 检索 / SQL / Web 工具
├── core/            # 配置 / LLM 工厂 / 安全 / 日志 / tracing
└── schemas/         # Pydantic 模型
```

## 开发

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
ruff format . && ruff check .
pytest
```

## 里程碑状态

| 里程碑 | 状态 |
|---|---|
| M0 项目骨架 | 🔨 进行中 |
| M1 核心多源 Agent 图 | ⬜ 未开始 |
| M2 FastAPI 服务化 | ⬜ 未开始 |
| M3 企业层 | ⬜ 未开始 |
| M4 数据打磨 | ⬜ 未开始 |
| M5 测试与评估 | ⬜ 未开始 |
| M6 发布 | ⬜ 未开始 |
