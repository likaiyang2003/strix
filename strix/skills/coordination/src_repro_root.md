---
name: src-repro-root
description: 串行执行基于报告的 /src 编排流程，按 analyzer -> planner -> reproducer 顺序推进，禁止泛化 recon 或扫描扩展
---

# /src 根级编排

仅当当前任务同时包含 `<src_repro_task>` 与 `<mode>src_reproduction</mode>` 时，本 skill 才生效。

一旦生效，本 skill 会覆盖通用 root agent 工作流。

## 任务目标

协调一个严格的“报告驱动复现”流程：

1. analyzer 判断报告是否具备可复现性
2. planner 将报告转换为结构化复现步骤
3. reproducer 使用 Strix 工具严格执行已批准的计划

将 `<report_text>` 视为漏洞细节的唯一事实来源。

## 硬性约束

- 不得执行 broad recon、泛化爬取、泛化漏洞扫描或与当前报告无关的验证
- 在 `/src` 模式下不得创建报告编写 agent 或修复 agent
- 不得跳过 analyzer 或 planner
- 不得并行运行 analyzer、planner 和 reproducer
- 任意时刻只允许一个活跃的子阶段
- 不得虚构当前项目中并不存在的持久化工具

## 阶段 1：Analyzer

创建一个子 agent：

- 名称：`SRC 复现分析器`
- Skills：`report_repro_analyzer`
- 职责：只判断 `can_reproduce`、`reason`、`missing_info`

委派给 analyzer 的任务必须明确要求：

- 只分析“是否具备复现准备条件”
- 除非为了阅读上下文绝对必要，否则不得执行漏洞、制定计划、做 recon 或广泛使用工具
- 仅返回严格 JSON
- 必须将最终 JSON 原文写入 `agent_finish.result_summary`

创建 analyzer 后：

- 调用 `wait_for_message`
- 解析收到的 `<agent_completion_report>`
- 从 `<summary>` 字段读取 analyzer JSON

如果 analyzer 返回 `can_reproduce=false`：

- 立即停止 `/src` 流程
- 不再创建 planner 或 reproducer
- 用简洁的 root 总结收口，并保留 analyzer 的 `reason` 与 `missing_info`

## 阶段 2：Planner

仅当 analyzer 返回 `can_reproduce=true` 时才启动。

创建一个子 agent：

- 名称：`SRC 复现规划器`
- Skills：`report_to_repro_checklist`
- 职责：把报告和 analyzer 结论转换为结构化复现步骤

委派给 planner 的任务必须明确要求：

- 尽量保留报告原始顺序
- 不得重新判断可复现性
- 不得虚构凭据、payload、绕过方式或报告中不存在的利用链
- 必须将完整复现清单写入 `agent_finish.result_summary`

创建 planner 后：

- 调用 `wait_for_message`
- 解析收到的 `<agent_completion_report>`
- 从 `<summary>` 字段读取完整计划

## 阶段 3：Reproducer

创建一个子 agent：

- 名称：`SRC 复现执行器`
- Skills：`repro_plan_executor`
- 职责：严格按计划执行

委派给 reproducer 的任务必须明确要求：

- 同时使用原始报告与 planner 输出
- 按顺序执行计划，使用现有 browser、proxy、terminal、python 工具
- 不得重设计或重写计划
- 必须将最终执行报告写入 `agent_finish.result_summary`

创建 reproducer 后：

- 调用 `wait_for_message`
- 解析收到的 `<agent_completion_report>`
- 从 `<summary>` 字段读取最终执行报告

## Root 收尾

当所有必要阶段完成后：

- 汇总 analyzer 判定
- 汇总 planner 产出
- 汇总 reproducer verdict，或提前停止时的 analyzer 原因
- 使用 `finish_scan` 完成 root 收尾

在 `/src` 模式下，`finish_scan` 四个字段按以下方式使用：

- `executive_summary`：最终 `/src` verdict 与一段结果摘要
- `methodology`：串行 `analyzer -> planner -> reproducer` 工作流
- `technical_analysis`：analyzer JSON、planner 清单摘要、reproducer 执行摘要
- `recommendations`：缺失信息、阻塞点或下一步建议
