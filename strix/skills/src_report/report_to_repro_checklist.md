---
name: report-to-repro-checklist
description: 将纯文本漏洞报告和 analyzer 结论转换为适用于 /src 模式的结构化复现清单
---

# 报告转复现清单

## 目标

把输入的漏洞报告转换成一份可以直接执行的复现清单。

本 skill 只负责把报告文本转换为步骤。
本 skill 不重新评估报告是否可复现。

## 硬性约束

- 必须遵守父 agent 已提供的 analyzer 结论
- 不得重新判断 `can_reproduce`
- 不得虚构报告中不存在的凭据、token、payload、绕过方式、请求头或利用链
- 当报告本身存在顺序时，尽量保留原始顺序
- 每一步都必须原子化、可执行
- 推荐使用当前 Strix 内置工具，如 browser、proxy、terminal、python
- 不得输出旧项目中的外部工具名，例如 `/playwright-cli`、`/http-replay`、`/traffic-capture`、`/evidence-capture`、`/web-login`
- 不得输出当前项目中不存在的浏览器动作，例如 `browser_action (screenshot)`
- 不得在计划中扩散原始密码、token、cookie、API key 或验证码；如需引用，只能按报告中的字段名描述

## 允许使用的 Suggested Tool

`Suggested Tool` 只能使用以下精确名称：

- `browser_action`
- `send_request`
- `repeat_request`
- `list_requests`
- `view_request`
- `python`
- `terminal`

优先只给出一个主工具。只有当报告明确要求两个工具协同时，才允许补充第二工具。

### 工具路由规则

- UI 导航、打开页面、点击、输入、等待、查看源码、收集浏览器控制台状态：`browser_action`
- 直接发送 API 请求、执行重放、验证响应：`send_request`
- 复用已捕获请求并做修改：`repeat_request`
- 查找或查看已捕获请求：`list_requests` 或 `view_request`
- 结构化解析响应、token 解码、字段比对或少量辅助逻辑：`python`
- 只有 shell 才能完成，且没有更合适项目内置工具时：`terminal`

## 必须输出的结构

返回的清单必须严格包含以下部分，并按顺序输出：

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
   - `Exact Operation`:
   - `Suggested Tool`:
   - `Suggested Action / Invocation`:
   - `Required Inputs`:
   - `Expected Evidence`:
   - `Evidence Type`:
   - `Stop / Failure Rule`:

根据需要重复若干步。

## Success Criteria

- `Success Marker`
- `Stop Conditions`

## Evidence Checklist

- 列出应该收集的具体截图、响应、字段或观察结论

## 规划规则

- 如果报告同时混合了 UI 导航与请求重放，则应尽量保留原顺序；但若报告已经给出了明确的 API endpoint、方法、请求体和成功响应，也可以优先规划 API 验证路径
- 报告中已经明确给出的值，应如实带入
- planner 应尽量把执行当前步骤真正需要的关键字段直接保留在计划中，减少 reproducer 执行时回看原始报告的频率
- 如果某一步依赖报告中的明确事实，例如 URL、endpoint、HTTP 方法、参数名、payload、按钮文本、菜单路径、成功标志描述或关键响应特征，应优先把这些事实写进该步骤的 `Exact Operation`、`Suggested Action / Invocation`、`Required Inputs` 或 `Expected Evidence`
- 不得把本应写进步骤的关键执行信息故意留成“见原始报告”或“按报告原文执行”这类模糊表述
- 只有当原始报告中的某些细节过长、过敏感或不适合完整内嵌到计划里时，才允许保留为“必要时回看原始报告”的补充信息；但即便如此，当前步骤仍必须保留足以开始执行的最小关键字段
- 如果报告里出现高风险 secret，应当按“凭据字段引用”来表达，而不是扩散原值
- 如果某一步依赖的是“隐含上下文”，应把它写成该步骤内的明确假设，不得藉此发明新的攻击逻辑
- 主复现路径应保持简洁清晰，但每个步骤必须足够原子化，避免执行器自行猜测下一动作
- 不得把多个本质不同的动作合并成一步
- 不得在同一步中混合 UI 证据与代理/请求证据，只要这两类证据可以分开检查，就应拆步
- 如果报告已经给出明确 API endpoint、HTTP 方法、请求体和验证响应，应优先规划 API-first 路径：
  - 只建立最小必要会话上下文
  - 发送或重放请求
  - 验证响应
  - 仅在最终触发或可视确认时补充 UI 步骤
- 如果某个浏览器动作本应生成流量，应在适当情况下拆成独立步骤：
  - 先执行 UI 动作
  - 再检查是否出现目标请求
  - 再查看请求或响应
  - 最后才决定是否需要有界重放
- 不得创建开放式页面探索步骤
- 不得创建 DOM 猎取步骤
- 不得把“找到页面”写成宽泛浏览任务；只能使用报告明确给出的入口、菜单或路由链
- 敏感值必须脱敏：
  - 非 secret 的用户名、URL、endpoint、字段名、菜单路径可以保留
  - 原始密码、token、cookie、API key 不得原样输出
  - 如需引用，应写成 `report-provided Authorization header`、`report-provided Cookie`、`report-provided jwt-token` 这类字段名引用
- 最后一步必须是一个明确的证据采集步骤，例如 `Collect Final Verification Evidence`
- `Stop Conditions` 必须绑定最终验证/证据步骤：
  - 一旦最终验证步骤执行完且未出现成功标志，必须立即结束当前复现流程
  - 不得再扩展到相邻页面、菜单、tab 或其他功能

## 基于角色的规划规则

- 必须保留 analyzer 对“当前前提 / 历史抓包证据 / 成功标志 / 成功后结果”的角色区分
- 只有当前 `execution_prerequisite` 才能写入 `## Preconditions`
- `historical_packet_evidence` 不得写入 `## Preconditions`
- `post_exploitation_result` 不得写入 `## Preconditions`
- `success_marker` 不得写入 `## Preconditions`
- 报告中的历史抓包、headers、cookies、tokens、checksums 可以出现在 `## Extracted Facts`，或作为有界重放步骤中的“报告证据”出现，但不能被暗示成当前可用凭据
- 如果报告只展示了历史抓包，应写成 `report-described historical request shape`、`report-described historical headers` 或等价表达，除非报告明确证明现在仍可复用
- 如果报告说成功触发后会泄露 token、cookie、session ID、账号数据或其他敏感值，这些内容只能放在 `Expected Impact`、`Success Criteria`、最终验证步骤或 `Evidence Checklist`
- 除非报告明确说明这些值当前仍可用且应复用，否则不得指导执行器使用 `report-provided jwt-token`、`report-provided Cookie` 等
- 如果报告显示“原报告者当时处于已登录状态”，但没有说明新测试者现在如何获得该状态，应把它保留为有界前提或显式假设，不能静默抹掉
- `Authorization: bearer null`、空 token、占位 header 等可作为请求形态证据引用，但不能被 planner 当作“无需认证”的独立证据
- 如果 analyzer 已经判定“无需复用认证材料也可进入复现”，则 planner 应保持最小前提，不得把历史或泄露 secret 重新塞回执行输入
- 当成功条件是“数据泄露”时，应描述泄露数据的类别，而不是把报告里出现过的具体 secret 当成输入要求
- 如果报告只隐含普通登录用户上下文，且不要求复用报告中的特定 secret，应写成类似 `需要测试者自备普通有效登录态` 的通用前提
- 在这种情况下，不得把历史 JWT/Cookie/Authorization 变成必需执行输入
- 如果流程需要特殊角色或特殊账号，而不仅是普通登录用户，应在 `Access Requirements` 中明确写出
- 如果报告没有说明如何获得该特殊角色/账号，应把它保留为有界前提说明，而不是发明绕过方法或复用历史 secret

## 步骤构造指南

- 每一步都只能有一个主工具和一个主观察目标
- planner 必须明确告诉执行器“要做什么动作”，而不能只说“用哪一类工具”
- `Suggested Action / Invocation` 必须足够具体，能约束执行器；但仍然只能使用当前项目中真实存在的动作
- `Required Inputs` 只列出这一步真正需要的输入，例如 `target_url`、`payload`、`request_id`、`field_name`、`credential field name`
- `Evidence Type` 必须使用简短而具体的标签，例如 `ui`、`request`、`response`、`state_change`、`error`
- `Stop / Failure Rule` 必须明确：这一步失败后是立即停止、允许一次有界 fallback，还是必须等证据收齐后才能进入下一步
- 不得让执行器自己猜测该步骤是导航、提交、抓流量、重放还是最终验证
- 如果原始报告已经给出了足以执行的关键字段，planner 应优先把这些字段写进步骤，而不是把 reproducer 设计成默认需要再次回看原始报告
- 计划应默认做到“拿到步骤就能直接开始执行”；回看原始报告只能是补缺口的后备路径，而不是 planner 预设的常态依赖

- 对纯 UI 验证问题：
  - 使用 `browser_action` 处理进入页面、点击、输入、提交、等待、刷新和最终观察
  - `Suggested Action / Invocation` 中必须写出明确动作，例如：
    - `browser_action(action="launch", url="...")`
    - `browser_action(action="click")`
    - `browser_action(action="type")`
    - `browser_action(action="press_key", key="Enter")`
    - `browser_action(action="wait")`
- 对 API-heavy 问题：
  - 把 `send_request` 或 `repeat_request` 作为主执行路径
  - 如果请求发送和响应检查都重要，应拆成独立步骤
  - 仅在建立会话或最终 UI 确认时补充 `browser_action`
- 对 Mixed UI + API 问题：
  - 保持最小 UI 路径，只用于到达已认证状态或目标功能
  - 优先把 API 写入/重放步骤设计为中心验证步骤
  - 如果验证路径依赖抓到浏览器流量，必须明确包含 `list_requests` 和 `view_request`
  - 最终 UI 确认必须保持有界、明确
- 对“浏览器动作会产生流量”的场景：
  - 不得写成类似 “发送消息并验证请求与响应” 的单一步骤
  - 必须拆成原子步骤，例如：
    - 先提交浏览器动作
    - 再列出或定位目标请求
    - 再查看请求或响应
    - 仅在需要时执行有界重放
- 不得把 `browser_action(action="execute_js")` 作为默认规划动作，用于导航、找按钮或宽泛页面探索
- 只有当报告明确依赖某个 DOM 状态验证，且标准浏览器动作无法表达时，才可在计划中使用 `execute_js`
- 如果决定性验证依赖代理流量，则最终验证路径必须明确点名代理工具，而不能继续使用模糊的“浏览器验证”表述
- 如果预期的重放请求可能因会话形态、CSRF、nonce、signature 或中间层拒绝而失败，那么重放步骤必须保持有界，并且在此之前先把“浏览器侧已捕获原始请求”的检查步骤写成决定性前置步骤

## 子 agent 收尾合同

如果你是子 agent，必须将完整清单写入 `agent_finish.result_summary`。
