# Strix `/src` 复现计划

更新时间：2026-03-31

## 1. 当前正式架构

当前 `/src` 主流程已经收口为：

- `/src`：`analyzer -> reproducer`
- `/src run`：直接 `reproducer`

其中 reproducer 的职责是：

1. 读取当前下发的原始漏洞报告文本
2. 先创建 `/src` 专用步骤合同
3. 再按步骤合同执行
4. 最后输出 verdict

以下旧方案已不再属于当前实现：

- `planner` 作为 `/src` 主阶段
- “缺口解析子 agent”
- `load_src_report_source` 原始报告回看工具

## 2. 范围边界

### 当前支持

- 纯文本漏洞报告
- TUI 中的 `/src <text>`
- TUI 中的 `/src @file`
- `/src run <text>`
- `/src run @file`
- `@file` 相对路径按“当前工作目录 -> `Vul_report/` 目录”顺序解析
- TUI 中对 `/src @` 与 `/src run @` 提供 `Vul_report/` 文件建议
- 当仅存在唯一匹配时，支持用 Tab 自动补全 `@file`

### 当前不做

- DOCX / HTML 原始报告解析
- OCR / 图片提取
- 原始报告二次回看
- 缺口解析子 agent
- 默认 broad recon / 默认扫描主链路

## 3. 当前实现流程

### 3.1 宿主入口

宿主层负责：

- 解析 `/src` 与 `/src run`
- 读取 `@file`
- 为相对 `@file` 自动补 `Vul_report/` 目录解析
- 在 TUI 中为 `/src @` / `/src run @` 提供文件提示与唯一匹配补全
- 对裸 `/src`、空 `run`、缺失文件等非法输入显式报错
- 组装 `<src_repro_task>`
- 为 root agent 自动加载 `src_repro_root`
- 路由到 root agent

相关文件：

- [slash_commands.py](/F:/Study/strix/strix/interface/slash_commands.py)

### 3.2 Analyzer

Analyzer 只负责输出：

- `can_reproduce`
- `reason`
- `missing_info`

补充说明：

- `/src run` 模式不会真正调用 analyzer
- 但编排层仍会生成一份“跳过分析”的结构化 analysis 结果，供后续执行与落盘统一使用

它不负责：

- 生成复现步骤
- 执行漏洞
- 扩展攻击范围

相关文件：

- [report_repro_analyzer.md](/F:/Study/strix/strix/skills/src_report/report_repro_analyzer.md)
- [orchestration.py](/F:/Study/strix/strix/src_repro/orchestration.py)

### 3.3 Reproducer

Reproducer 直接读取 `report_text` 执行，不再接收 planner 产物。

当前要求它：

- 必须先调用 `create_src_repro_plan`
- 在 `create_src_repro_plan` 完成前，不得先调用执行型工具
- 执行中使用 `get_src_repro_plan` / `update_src_repro_plan_step` 维护状态
- 在 `/src` reproducer 中禁止使用通用 `todo` 工具
- 最终按 4 个部分输出：
  - `## 1) Execution Todo`
  - `## 2) Reproduction Execution Notes`
  - `## 3) Skills/MCP Execution Trace`
  - `## 4) Final Verdict`

相关文件：

- [src_repro_root.md](/F:/Study/strix/strix/skills/coordination/src_repro_root.md)
- [repro_plan_executor.md](/F:/Study/strix/strix/skills/src_report/repro_plan_executor.md)
- [orchestration.py](/F:/Study/strix/strix/src_repro/orchestration.py)

### 3.4 TUI 展示与 `/src` 步骤状态

当前 TUI 已对 `/src` 步骤工具做单独展示收口：

- `create_src_repro_plan`
  - 首次在左侧聊天区全量展示步骤合同
- `get_src_repro_plan`
  - 左侧仅展示简版快照，不再默认铺开完整步骤细节
- `update_src_repro_plan_step`
  - 改为增量返回
  - 左侧仅展示本次更新到的步骤与简短汇总

右侧 sidebar 已新增 `SRC 状态` 面板：

- 优先显示当前选中 agent 的 `/src` 步骤状态
- 如果当前选中的是 root，而真实步骤合同跑在其子级 reproducer 上，则自动回退显示最近的 `/src` reproducer 状态
- 右侧内容来自 tracer 中的 `/src` 计划工具结果重建，而不是解析左侧聊天文本

相关文件：

- [src_repro_plan_actions.py](/F:/Study/strix/strix/tools/src_repro/src_repro_plan_actions.py)
- [src_repro_plan_renderer.py](/F:/Study/strix/strix/interface/tool_components/src_repro_plan_renderer.py)
- [tui.py](/F:/Study/strix/strix/interface/tui.py)
- [tui_styles.tcss](/F:/Study/strix/strix/interface/assets/tui_styles.tcss)

### 3.5 落盘

`/src` 产物统一写入当前 run 目录下的 `src_repro/<bundle_id>/`。

当前产物包括：

- `00_source_report.txt`
- `01_analysis.json`
- `02_reproduction_plan.txt`
- `03_execution_trace.md`
- `04_final_verdict.md`
- `manifest.json`

说明：

- `02_reproduction_plan.txt` 当前保存的是 reproducer 自己生成的 `/src` 步骤合同摘要
- 该命名保留是为了兼容现有落盘结构，并不代表当前仍有 planner 阶段

相关文件：

- [output.py](/F:/Study/strix/strix/src_repro/output.py)
- [src_repro_actions.py](/F:/Study/strix/strix/tools/src_repro/src_repro_actions.py)
- [src_repro_actions_schema.xml](/F:/Study/strix/strix/tools/src_repro/src_repro_actions_schema.xml)

## 4. 当前代码映射

### 主入口与编排

- [slash_commands.py](/F:/Study/strix/strix/interface/slash_commands.py)
- [strix_agent.py](/F:/Study/strix/strix/agents/StrixAgent/strix_agent.py)
- [orchestration.py](/F:/Study/strix/strix/src_repro/orchestration.py)

### Skills

- [src_repro_root.md](/F:/Study/strix/strix/skills/coordination/src_repro_root.md)
- [report_repro_analyzer.md](/F:/Study/strix/strix/skills/src_report/report_repro_analyzer.md)
- [repro_plan_executor.md](/F:/Study/strix/strix/skills/src_report/repro_plan_executor.md)
- [report_to_repro_checklist.md](/F:/Study/strix/strix/skills/src_report/report_to_repro_checklist.md)

说明：

- `report_to_repro_checklist` 仍保留为独立 skill
- 它不再属于 `/src` 主执行链路

### `/src` 专用工具

- [src_repro_actions.py](/F:/Study/strix/strix/tools/src_repro/src_repro_actions.py)
- [src_repro_plan_actions.py](/F:/Study/strix/strix/tools/src_repro/src_repro_plan_actions.py)

当前包含：

- `create_src_repro_plan`
- `get_src_repro_plan`
- `update_src_repro_plan_step`
- `save_src_repro_bundle`

### `/src` 专用 renderer

- [src_repro_plan_renderer.py](/F:/Study/strix/strix/interface/tool_components/src_repro_plan_renderer.py)
- [tui.py](/F:/Study/strix/strix/interface/tui.py)
- [tui_styles.tcss](/F:/Study/strix/strix/interface/assets/tui_styles.tcss)

## 5. 当前已完成项

### 已完成能力

- `/src` 与 `/src run` 命令解析
- `@file` 输入支持
- 相对 `@file` 自动解析 `Vul_report/` 目录
- `/src @` / `/src run @` 文件建议与唯一匹配补全
- `/src` 非法输入显式报错与交互收口
- root agent 路由
- analyzer -> reproducer 两阶段编排
- `/src run` 跳过 analyzer
- `/src` 专用步骤工具已接入
- `/src` 专用 renderer 已接入
- `create_src_repro_plan` 首次全量展示已收口
- `update_src_repro_plan_step` 已改为增量返回
- `get_src_repro_plan` 左侧已改为简版快照展示
- 右侧 sidebar 已新增 `SRC 状态` 简版步骤状态区
- 宿主层已只对 `/src` reproducer 强制 `src_repro_plan`
- `/src` reproducer 已禁止使用通用 `todo`
- `/src` 结果落盘
- `/src` 相关最小回归测试
- 原始报告回看链路移除
- 缺口解析子 agent 链路移除

### 已通过验证

以下回归已通过：

- [test_slash_commands.py](/F:/Study/strix/tests/interface/test_slash_commands.py)
- [test_orchestration.py](/F:/Study/strix/tests/src_repro/test_orchestration.py)
- [test_src_repro_minimal_flow.py](/F:/Study/strix/tests/integration/test_src_repro_minimal_flow.py)
- [test_strix_src_repro_runtime.py](/F:/Study/strix/tests/agents/test_strix_src_repro_runtime.py)
- [test_src_repro_skills.py](/F:/Study/strix/tests/skills/test_src_repro_skills.py)
- [test_src_repro_actions.py](/F:/Study/strix/tests/tools/test_src_repro_actions.py)
- [test_src_repro_plan_actions.py](/F:/Study/strix/tests/tools/test_src_repro_plan_actions.py)
- [test_executor_src_repro_gate.py](/F:/Study/strix/tests/tools/test_executor_src_repro_gate.py)
- [test_src_repro_plan_renderer.py](/F:/Study/strix/tests/interface/test_src_repro_plan_renderer.py)
- [test_output.py](/F:/Study/strix/tests/src_repro/test_output.py)

已执行命令：

```powershell
uv run pytest tests/interface/test_slash_commands.py tests/src_repro/test_orchestration.py tests/integration/test_src_repro_minimal_flow.py tests/agents/test_strix_src_repro_runtime.py tests/skills/test_src_repro_skills.py tests/tools/test_src_repro_actions.py tests/src_repro/test_output.py -q
uv run python -m compileall strix
uv run pytest tests/skills/test_src_repro_skills.py tests/src_repro/test_orchestration.py -q
uv run pytest tests/tools/test_src_repro_plan_actions.py tests/interface/test_src_repro_plan_renderer.py -q
uv run pytest tests/src_repro/test_orchestration.py tests/agents/test_strix_src_repro_runtime.py tests/integration/test_src_repro_minimal_flow.py -q
uv run python -m compileall strix\tools\src_repro\src_repro_plan_actions.py strix\interface\tool_components\src_repro_plan_renderer.py strix\interface\tui.py
```

## 6. 当前未收口项

### 6.1 Analyzer 仍可能过严

当前 analyzer 在“普通登录态即可继续尝试”的场景下，仍可能误判为：

- 缺少可用认证令牌
- 缺少当前登录态获取方式
- `can_reproduce=false`

典型受影响案例：

- 普通用户会话下的存储型 XSS
- 普通登录态业务功能中的逻辑漏洞
- 报告提供了完整 endpoint / payload / success marker，但历史 JWT/Cookie 只是证据而不是当前必需输入

这部分仍需继续收紧 [report_repro_analyzer.md](/F:/Study/strix/strix/skills/src_report/report_repro_analyzer.md)。

### 6.2 左侧聊天区仍有较多过程性文本

虽然当前计划卡片本身已经收口：

- `create` 不再重复刷屏
- `update` 不再整份回显 plan
- 右侧 `SRC 状态` 已承担实时状态职责

但左侧聊天区当前仍可能出现较多过程性自然语言，例如：

- `<think>...</think>` 块
- “我现在准备执行 S2”
- 对同一步骤的口头重复说明

这说明当前左侧空间的主要占用，已经从“计划工具结果过大”转移为“模型自身过程性输出过多”。

后续若继续做 TUI 体验收口，优先级应放在：

- 隐藏或过滤 `<think>` 展示
- 收紧 reproducer 技能文案，减少口头复述
- 视需要在 UI 层进一步压缩过程性 assistant 文本

### 6.3 `/src` 步骤合同仍主要是“工具级 + prompt 级”组合约束

虽然当前已经落地：

- 先 `create_src_repro_plan`
- 再执行
- 执行中维护步骤状态
- 宿主层阻止 `/src` reproducer 在建 plan 之前直接调用执行型工具
- 宿主层阻止 `/src` reproducer 使用通用 `todo`

但当前仍未做到的部分是：

- 宿主层还没有校验 `agent_finish` 之前是否一定已经创建了 plan
- 宿主层还没有校验最终 `## 1) Execution Todo` 是否与实际 plan 完全一致
- 宿主层还没有从工具结果反推“步骤覆盖率”并自动校对最终 verdict

### 6.4 `/src` 计划工具当前仍是全局注册

当前 `create_src_repro_plan` / `get_src_repro_plan` / `update_src_repro_plan_step`：

- 已通过执行流和 skill 约束，逻辑上只服务于 `/src` reproducer
- 宿主层也已对 `/src` reproducer 增加 plan-before-execute 限制

但从工具注册与 system prompt 下发层面看：

- 这 3 个工具当前仍是全局注册
- 会进入全局工具列表
- 并非真正只对 `/src` reproducer 可见

当前还没有做到：

- 非 reproducer agent 不下发这 3 个工具
- 或非 reproducer agent 调用它们时被宿主层统一拒绝

这部分目前只是已知边界，不是本轮已收口项。

### 6.5 落盘仍以文本摘要为主

当前 `02_reproduction_plan.txt` 已经可以保存 `/src` 步骤合同摘要，但仍是文本兼容形态。

这意味着：

- 当前 run 目录里还没有结构化的 `src_repro_plan.json`
- 后续若要做更强的审计、重放或 UI 二次展示，仍需要结构化落盘

## 7. 下一步建议

建议按以下顺序推进：

1. 收紧 analyzer 对普通登录态场景的判定，避免误把普通会话需求判成 `can_reproduce=false`
2. 继续收口左侧聊天区的过程性文本，优先隐藏 `<think>` 并减少步骤口头复述
3. 视需要把 `/src` 步骤合同增加结构化 JSON 落盘，而不只保留文本摘要
4. 视需要把宿主层校验继续收紧到：
   - 未创建 plan 时不允许提前 `agent_finish`
   - 最终 `Execution Todo` 必须与真实 plan 对齐
   - 最终 verdict 与步骤状态、阻塞状态保持一致
5. 视需要继续收紧工具暴露边界：
   - 只对 `/src` reproducer 下发计划工具
   - 或非 reproducer 调用计划工具时宿主层直接拒绝
6. 用真实漏洞报告继续做回归，重点覆盖：
   - 普通登录态 XSS
   - UI + API 混合场景
   - 历史凭据仅作证据、不作当前输入的案例

## 8. 当前结论

当前 `/src` 已经完成第一版主链路收口：

- 主流程已简化
- 多余支线已移除
- 产物已可落盘
- 回归已可跑通

但它还不是最终形态。

当前最重要的后续工作不是再加更多分支，而是继续集中做以下几件事：

- 让 analyzer 判定更稳
- 让左侧与右侧的 `/src` 展示职责进一步分离
- 把已经落地的 `/src` 专用步骤合同继续往“可审计、可落盘、可校验”方向收口
