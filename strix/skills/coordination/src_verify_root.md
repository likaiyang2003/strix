---
name: src-verify-root
description: 串行执行基于漏洞报告的 /src verify 编排流程，直接派发 verify executor，禁止扩展成扫描或修复后绕过挖掘
---

# /src verify 根级编排

仅当当前任务包含 `<src_repro_task>` 且 `<mode>src_verification</mode>` 时，本 skill 生效。
一旦生效，本 skill 覆盖通用 root agent 的默认扫描思路。

## 任务目标

协调一个严格的“修复后验证”流程：

1. root 直接派发一个 verify executor 子 agent
2. verify executor 必须先创建详细 verification plan，再按 plan 执行
3. root 汇总 verify executor 的执行结果与最终 verdict

把 `<report_text>` 视为当前 `/src verify` 任务的主事实来源。

## 硬性约束

- 不得执行 broad recon、泛化爬取、泛化漏洞扫描或与当前报告无关的验证
- 不得创建 verify analyzer；第一版只允许一个 verify executor 子 agent
- 不得并行运行多个 `/src verify` 子 agent
- 不得把修复后验证改造成“修复后绕过挖掘”
- 不得把 verify verdict 退回 `/src` reproducer 的旧语义
- 不得虚构当前项目中并不存在的工具、持久化能力或外部工作流
- 任意时刻只允许一个活跃的 `/src verify` 子阶段 agent

## 阶段 1：Verify Executor

创建一个子 agent：

- 名称：`SRC Verify Executor`
- Skills：`verify_plan_executor`
- 职责：直接阅读原始报告，先创建 verification plan，再执行验证，并输出 `still reproducible|fixed|blocked`

委派给 verify executor 的任务必须明确要求：

- 直接使用 `report_text` 作为主输入，不新增 verify analyzer
- 在调用任何执行型工具前，必须先调用 `create_src_plan`
- 执行中应使用 `get_src_plan` / `update_src_plan_step` 维护步骤状态
- 在 `/src verify` executor 中不得使用通用 `todo` 工具
- 必须把完整执行报告写入 `agent_finish.result_summary`

创建 verify executor 后：

- 调用 `wait_for_message`
- 解析 `<agent_completion_report>`
- 从 `<summary>` 中读取完整执行报告

## Root 收尾

当 verify executor 完成后：

- 汇总 verification plan 摘要
- 汇总 verify executor 的最终 verdict
- 汇总 comparability、旧成功标志与修复后安全行为
- 使用 `finish_scan` 完成 root 收尾

在 `/src verify` 模式下，`finish_scan` 四个字段建议这样组织：

- `executive_summary`：最终 verify verdict 与结果摘要
- `methodology`：单子 agent verification workflow，注明“先 plan，再执行”
- `technical_analysis`：verification plan 摘要、执行摘要、comparability / secure behavior 判定
- `recommendations`：阻塞点、后续验证建议、补充信息建议
