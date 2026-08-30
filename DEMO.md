# FinCopilot 演示脚本

> 面向面试官/招聘者的 5 分钟演示。核心卖点：**多源自适应路由 + 企业级工程化**。

## 环境准备（已就绪）
- Docker Desktop 运行中（api :8000 + qdrant :6333 healthy）
- 财报已摄入 Qdrant（amazon/apple/google，982 块）
- 员工库只读连接（300,024 员工）

## 演示步骤

### 1. 开场（30s）
> "这是 FinCopilot，一个多源自适应财务分析师 Copilot。它能判断问题该查哪条路——财报文档、员工数据库、还是实时网络——自动路由并带来源回答。"

### 2. 三路演示（各 1 问，共 ~2min）
| 路径 | 问题 | 预期回答 | 演示要点 |
|---|---|---|---|
| **RAG** | "What was Amazon's revenue in 2023?" | **$574.785 billion** + 来源 `amazon 10-k 2023 p.38` | 混合检索命中财报原文，带页码引用 |
| **SQL** | "How many employees are there?" | **300,024** | Text-to-SQL 只读执行，回答结构化 |
| **Web** | "What is the latest AI news?" | 摘要 + 链接 | 兜底实时路径（墙内网络可能降级，如实说明）|

> 可用 `curl -N -X POST http://localhost:8000/v1/chat -H "Content-Type: application/json" -d '{"question":"..."}'` 或 Streamlit 前端演示。

### 3. 记忆演示（30s）
- 问 "What was Amazon's revenue in 2023?" → 再问 "How about 2022?" → 应回答 **$513.983 billion**（记忆上下文）。

### 4. 工程亮点（1-2min，可追问）
- **架构**：分层多 Agent——Supervisor Router 可评估，三个 Sub-agent 自主执行（含跨模式 fallback）
- **检索**：双路召回（Qdrant dense + BM25 稀疏）→ RRF 融合
- **安全**：SQL 纵深防御 5 层（sqlglot 校验 + 只读连接），演示 `curl -X POST /v1/chat -d '{"question":"Delete all data"}'` 看如何拒绝
- **可观测**：structlog JSON 日志、Langfuse tracing（可选）
- **测试**：26 个 pytest（离线可跑）+ 金标评估集

### 5. 收尾（30s）
> "从课程 notebook 到可部署产品：Docker 一键起、SSE 流式、多线程记忆、企业级安全。三步 clone 即跑。"

## 备选问题
- "What was Apple's total net sales in 2023?"（RAG，~383B）
- "Which department has the highest average salary?"（SQL，Finance）
- "What was Amazon's operating income in 2023?"（RAG，~$36.9B）
