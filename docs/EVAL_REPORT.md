# FinCopilot v2 · 评测矩阵报告

> 生成时间：1788112252920855848

本报告对比不同检索参数组合在金标集上的表现（faithfulness / answer_relevancy，0-5）。

## 总体对比

| 组合 | 说明 | 金标数 | Faithfulness | Answer Relevancy |
|---|---|---|---|---|
| rerank-on | 双路+RRF+LLM精排 | 12 | 4.67 | 4.92 |
| rerank-off | 仅双路+RRF（无精排） | 12 | 4.00 | 5.00 |

## 按类别对比

| 类别 | rerank-on F/R | rerank-off F/R |
|---|---|---|
| rag | 4.67/4.92 | 4.00/5.00 |

## 亮点与问题

- **rerank-on** 最佳：`rag-01` (f=5)
- **rerank-on** 待改进：`rag-11` (f=1) 回答：文档库未找到，以下来自网络：  
根据 Companies Market Cap 数据，亚马逊 2022 年收入为 **5,139.8 亿美元**（来源：htt
- **rerank-off** 最佳：`rag-01` (f=5)
- **rerank-off** 待改进：`rag-03` (f=2) 回答：Amazon's net income in 2023 was **$30,425 million** (or $304.25 billion).

**Sou

## 明细

### rerank-on（双路+RRF+LLM精排）

| ID | 类型 | F | R |
|---|---|---|---|
| rag-01 | rag | 5 | 5 |
| rag-02 | rag | 5 | 5 |
| rag-03 | rag | 5 | 5 |
| rag-04 | rag | 5 | 5 |
| rag-05 | rag | 5 | 5 |
| rag-06 | rag | 5 | 5 |
| rag-07 | rag | 5 | 5 |
| rag-08 | rag | 5 | 5 |
| rag-09 | rag | 5 | 5 |
| rag-10 | rag | 5 | 5 |
| rag-11 | rag | 1 | 4 |
| rag-12 | rag | 5 | 5 |

### rerank-off（仅双路+RRF（无精排））

| ID | 类型 | F | R |
|---|---|---|---|
| rag-01 | rag | 5 | 5 |
| rag-02 | rag | 5 | 5 |
| rag-03 | rag | 2 | 5 |
| rag-04 | rag | 5 | 5 |
| rag-05 | rag | 5 | 5 |
| rag-06 | rag | 2 | 5 |
| rag-07 | rag | 5 | 5 |
| rag-08 | rag | 5 | 5 |
| rag-09 | rag | 2 | 5 |
| rag-10 | rag | 2 | 5 |
| rag-11 | rag | 5 | 5 |
| rag-12 | rag | 5 | 5 |
