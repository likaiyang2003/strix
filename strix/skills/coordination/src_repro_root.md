---
name: src-repro-root
description: 串行执行基于漏洞报告的 /src 编排流程，按 analyzer -> reproducer 推进，禁止泛化 recon 或扫描扩展
---

# /src 根级编排

仅当当前任务包含 `<src_repro_task>` 且 `<mode>src_reproduction</mode>` 时，本 skill 生效。
一旦生效，本 skill 覆盖通用 root agent 的默认扫描思路。

## 任务目标

协调一个严格的“报告驱动复现”流程：

1. analyzer 判断报告是否具备可复现条件
2. 若通过，则 reproducer 直接阅读原始报告，自行创建简短步骤合同并执行
3. root agent 汇总 analyzer 结论、reproducer 执行结果与最终 verdict

把 `<report_text>` 视为当前 `/src` 任务的主事实来源。

## 硬性约束

- 不得执行 broad recon、泛化爬取、泛化漏洞扫描或与当前报告无关的验证
- 不得创建与修复建议、报告改写或无关探索相关的子 agent
- 除 `/src run` 外，不得跳过 analyzer
- 不得并行运行 analyzer 与 reproducer
- 任意时刻只允许一个活跃的 `/src` 子阶段 agent
- 不得虚构当前项目中并不存在的工具、持久化能力或外部工作流

## 阶段 1：Analyzer

创建一个子 agent：

- 名称：`SRC Repro Analyzer`
- Skills：`report_repro_analyzer`
- 职责：只判断 `can_reproduce`、`reason`、`missing_info`

委派给 analyzer 的任务必须明确要求：

- 只分析“是否具备复现前提”
- 不执行漏洞、不做规划、不做 recon
- 只返回严格 JSON
- 必须把 JSON 原文写入 `agent_finish.result_summary`

创建 analyzer 后：

- 调用 `wait_for_message`
- 解析 `<agent_completion_report>`
- 从 `<summary>` 中读取 analyzer JSON

如果 analyzer 返回 `can_reproduce=false`：

- 立即结束 `/src` 流程
- 不再创建 reproducer
- root 直接收口，并保留 `reason` 与 `missing_info`

## 阶段 2：Reproducer

仅当：

- analyzer 返回 `can_reproduce=true`
- 或用户显式使用 `/src run` 跳过 analyzer

时才启动 reproducer。

创建一个子 agent：

- 名称：`SRC Reproducer`
- Skills：`repro_plan_executor`
- 职责：直接阅读原始报告，先产出 `/src` 专用步骤合同，再执行，再输出 verdict

委派给 reproducer 的任务必须明确要求：

- 使用 `analysis_json` 作为前提参考，但不得重判 `can_reproduce`
- 使用 `report_text` 作为执行输入，而不是依赖独立 planner 产物
- 先调用 `create_src_repro_plan` 创建 `/src` 专用步骤合同，再输出 `Execution Todo`
- 再按步骤合同执行，使用当前 Strix 已有 browser / proxy / terminal / python / agents graph 能力
- 在 `create_src_repro_plan` 完成前，不得先调用执行型工具
- 执行中应使用 `get_src_repro_plan` / `update_src_repro_plan_step` 维护步骤状态
- 在 `/src` reproducer 中不得使用通用 `todo` 工具
- 必须把完整执行报告写入 `agent_finish.result_summary`

创建 reproducer 后：

- 调用 `wait_for_message`
- 解析 `<agent_completion_report>`
- 从 `<summary>` 中读取完整执行报告

## Root 收尾

当所有必要阶段完成后：

- 汇总 analyzer 判定
- 汇总 reproducer 自行生成的步骤合同摘要
- 汇总 reproducer verdict
- 使用 `finish_scan` 完成 root 收尾

在 `/src` 模式下，`finish_scan` 四个字段建议这样组织：

- `executive_summary`：最终 `/src` verdict 与结果摘要
- `methodology`：串行 `analyzer -> reproducer` 工作流；若为 `/src run`，则注明 `analysis skipped`
- `technical_analysis`：analyzer JSON、reproducer 步骤合同摘要、执行摘要
- `recommendations`：缺失信息、阻塞点、后续建议

## 兼容说明

`report_to_repro_checklist` 仍可作为独立 skill 保留，但它不再属于 `/src` 主执行链路。
