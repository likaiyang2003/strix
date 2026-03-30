---
name: report-to-repro-checklist
description: 将纯文本漏洞报告和 analyzer 结论转换为适用于 /src 模式的细粒度结构化复现计划，供下游 reproducer 严格按计划执行。
---

# 报告转详细复现计划

## 目标

把输入的漏洞报告整理成一份“可执行、可交接、可审阅”的详细复现计划。
你只负责把报告和 analyzer 结论整理成计划，不重新判断能否复现，也不真正执行漏洞。

## 硬性约束

- 必须尊重父 agent 提供的 analyzer 结论。
- 不得重新判断 `can_reproduce`。
- 不得虚构报告中不存在的凭据、Token、payload、绕过方式、请求头或利用链。
- 不得 broad recon、泛化浏览、计划外探索或相邻功能点扩展。
- 敏感值不得扩散；密码、Token、Cookie、JWT、签名值只按“报告中的字段名”引用。
- 如果只是普通登录态场景，应写成类似 `需要测试者自备普通有效登录态` 的通用前提，而不是复用历史 JWT/Cookie。
- 输出必须足够细，避免这类空泛步骤名：
  - `准备请求`
  - `发送请求`
  - `验证响应`
  - `进入系统后测试`

## 两阶段思路

### Stage 1：静默提取事实

先在内部提取并整理以下事实，不单独输出这一步：

- 目标系统、目标域名/IP、入口 URL / Endpoint
- 菜单路径、页面位置、接口位置、关键字段
- 账号信息、角色信息、敏感字段说明
- 成功标志、停止条件
- 认证依赖、时效性依赖、JWT / Cookie / nonce / checksum / 短信码等 blocker
- 缺失信息
- `historical_packet_evidence`

### Stage 2：输出详细计划

基于上述事实，输出一个让执行器“拿到就能开始做”的详细复现计划。

## Suggested Tool 约束

`Suggested Tool` 只能使用以下精确工具名：

- `browser_action`
- `send_request`
- `repeat_request`
- `list_requests`
- `view_request`
- `python`
- `terminal`

优先给一个主工具；只有明确需要两个工具协同时，才补第二个。

## 必须输出的结构

按以下固定顺序输出：

## Extracted Facts

- `Target System`
- `Target Host/IP`
- `Entry URL / Endpoint`
- `Account / Credential References`
- `Critical Path`
- `Vulnerability Type / Category`
- `Expected Impact`
- `Original Conclusion`
- `Analyzer Summary`

## Preconditions

- `Environment`
- `Account / Credential References`
- `Access Requirements`
- `Sensitive Field Handling`

## Detailed Reproduction Steps

每一步都必须使用以下结构：

1. `Step Name`
   - `Objective`:
   - `Preconditions`:
   - `Required Inputs`:
   - `Exact Operation`:
   - `Suggested Tool`:
   - `Suggested Action / Invocation`:
   - `Expected Evidence`:
   - `Evidence Type`:
   - `Success Check`:
   - `Failure Troubleshooting`:
   - `Evidence Retention`:
   - `Stop / Failure Rule`:

## Success Criteria

- `Success Marker`
- `Stop Conditions`

## Blockers

- 列出当前直接阻断复现的条件；没有则写 `None`

## Missing Information

- 列出当前缺失但执行需要的信息；没有则写 `None`

## 规划规则

- 每一步必须是原子步骤，不能把多个本质不同的动作揉在一起。
- 不得写成类似 “发送消息并验证请求与响应” 的单一步骤。
- 如果浏览器动作会产生目标请求，必须拆成：
  - 先做 UI 动作
  - 再定位请求
  - 再查看请求/响应
  - 只在必要时才重放
- 如果报告已经给出明确 API endpoint、HTTP 方法、请求体和响应特征，应优先规划 API-first 路径。
- 如果报告已经限定了页面、菜单、标签页、按钮或字段，计划也必须保持这个边界。
- 如果报告中的认证材料明显带时效性，必须单独写到 `## Blockers`，不能埋进普通步骤。
- 每一步尽量把执行所需的关键字段直接保留在步骤里，不要把执行器设计成频繁回看原始报告。
- planner 应尽量把执行当前步骤真正需要的关键字段直接保留在计划中。
- 不得把执行器设计成依赖二次回看原始报告。
- 不得指导执行器使用 `report-provided jwt-token`、`report-provided Cookie` 这类历史凭据作为默认输入。
- 不得把 `browser_action(action="execute_js")` 作为默认规划动作。
- 最后一步必须是明确的最终证据采集步骤。

## 收尾要求

如果你是子 agent，必须把完整复现计划写入 `agent_finish.result_summary`。
