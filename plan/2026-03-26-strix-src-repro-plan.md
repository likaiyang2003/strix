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
- 修复后的正式回归验证工作流

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

- 必须先调用 `create_src_plan`
- 在 `create_src_plan` 完成前，不得先调用执行型工具
- 执行中使用 `get_src_plan` / `update_src_plan_step` 维护状态
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

- `create_src_plan`
  - 首次在左侧聊天区全量展示步骤合同
- `get_src_plan`
  - 左侧仅展示简版快照，不再默认铺开完整步骤细节
- `update_src_plan_step`
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

- `create_src_plan`
- `get_src_plan`
- `update_src_plan_step`
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
- `create_src_plan` 首次全量展示已收口
- `update_src_plan_step` 已改为增量返回
- `get_src_plan` 左侧已改为简版快照展示
- 右侧 sidebar 已新增 `SRC 状态` 简版步骤状态区
- analyzer 已收紧为“只拦明显无法开始复现”的报告口径
- reproducer 已补充“联合场景至少拆 3 步”与“Caido/代理错误页应判 blocked”的规则
- reproducer 已补充“联合场景默认优先走 UI 会话链路，不再机械地裸放包优先”的规则
- `/src` 步骤合同已补充 `failure_judgment` 字段，用于显式表达每一步的失败/未命中判断
- reproducer 已补充“本地信号不等于目标侧成功证据”的规则，防止把本地 DOM/JS 操作误判为复现成功
- reproducer 已补充“三层规则”：验证节点骨架 + 漏洞族覆盖规则 + 统一 verdict 闸门
- `/src` 步骤合同进一步细化为 `success_judgment` / `negative_judgment` / `blocked_judgment`
- reproducer 已补充“单节点单步骤 + judgment 不跨步”规则，防止在一个步骤内混合请求、响应、页面执行判断
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
python -m pytest -o addopts='' tests/skills/test_src_repro_skills.py -q
```

## 6. 当前未收口项

### 6.1 Analyzer 仍可能过严

当前 analyzer 虽已放宽到“只拦明显无法开始复现”的口径，但在以下场景中仍需继续用真实报告回归确认稳定性：

- 普通用户会话下的存储型 XSS
- 普通登录态业务功能中的逻辑漏洞
- 报告提供了完整 endpoint / payload / success marker，但历史 JWT/Cookie 只是证据而不是当前必需输入
- UI + API 联合场景中，analyzer 是否会仍然过早把未来可能的执行阻塞当成 analyzer 阶段的否决理由

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

### 6.3 Reproducer 的 plan 质量与 blocked 标记仍需继续观察

当前 reproducer 已新增规则：

- 联合 `ui_navigation + packet_replay` 场景默认至少拆成 3 步
- 禁止把“发送请求 + 验证响应 + 验证页面执行”合并成一步
- Caido / 代理错误页 / 中间层错误页应优先标记为 `blocked`
- 不能把“工具调用结束”当作 `done`
- 对带 UI 路径与页面端成功标志的联合场景，默认优先先走 UI 分支，再决定是否查看或重放当前真实请求
- 单个 API 分支被代理或中间层阻断时，如果报告内仍有尚未尝试的有界 UI 分支，不应立刻结束整个任务
- 本地输入框填充、自己注入的 JS 日志、alert 监控钩子命中等“本地信号”不能单独支持 `reproducible`
- 最终未命中成功标志时，必须明确落到 `not reproducible` 或 `blocked`
- 计划生成前需先抽取固定验证节点，再按漏洞族补齐必须保留的验证链，最后统一通过 verdict 闸门收口
- 步骤级失败语义已细分为：命中成功证据、已完成验证但未命中成功标志、无法完成决定性验证

但这些目前仍主要依赖 skill 约束，而不是宿主层硬校验。

因此仍需继续观察：

- 真实报告下是否还会出现单步 `/src` plan
- 是否还会把代理错误页、中间层错误页错标为 `done`

### 6.4 `/src` 步骤合同仍主要是“工具级 + prompt 级”组合约束

虽然当前已经落地：

- 先 `create_src_plan`
- 再执行
- 执行中维护步骤状态
- 宿主层阻止 `/src` reproducer 在建 plan 之前直接调用执行型工具
- 宿主层阻止 `/src` reproducer 使用通用 `todo`

但当前仍未做到的部分是：

- 宿主层还没有校验 `agent_finish` 之前是否一定已经创建了 plan
- 宿主层还没有校验最终 `## 1) Execution Todo` 是否与实际 plan 完全一致
- 宿主层还没有从工具结果反推“步骤覆盖率”并自动校对最终 verdict

### 6.5 `/src` 计划工具当前仍是全局注册

当前 `create_src_plan` / `get_src_plan` / `update_src_plan_step`：

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

### 6.6 落盘仍以文本摘要为主

当前 `02_reproduction_plan.txt` 已经可以保存 `/src` 步骤合同摘要，但仍是文本兼容形态。

这意味着：

- 当前 run 目录里还没有结构化的 `src_repro_plan.json`
- 后续若要做更强的审计、重放或 UI 二次展示，仍需要结构化落盘

### 6.7 修复后的复现验证尚未纳入当前 `/src`

当前 `/src` 更适合作为企业 SRC 的**第一阶段能力**：

- 外部白帽提交漏洞报告后
- 内部安全团队或运营人员读取报告
- 判断是否可尝试复现
- 跑通有界复现链并给研发提供修复输入

但它**尚未**覆盖企业 SRC 的第二阶段：

- 研发修复后的正式回归验证
- 在固定前提下重复执行同一漏洞链
- 比对“修复前 / 修复后”是否仍命中成功标志
- 在更稳定的登录态、测试账号、测试环境下做回归确认

这部分与当前第一阶段 `/src` 的工程目标不同，后续应作为单独能力规划，而不是继续塞入当前 `/src` 主链。

如果后续进入“修复后的复现验证”阶段，预计会涉及：

- 固定测试账号或凭据库
- 登录前置流程或会话复用
- 更稳定的 regression replay 输入
- 修复前后 verdict 对比
- 更适合回归的结构化落盘与对比输出

因此当前结论是：

- 第一阶段 `/src`：已基本成型，继续做真实报告回归验证
- 第二阶段“修复后的复现验证”：单独规划，不在当前主链中强行并入

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
7. 单独规划第二阶段“修复后的复现验证”能力，先明确：
   - 是否复用当前 `/src` 命令族还是新增子命令
   - 是否引入固定测试账号 / 凭据库 / 登录前置流程
   - 是否需要结构化保存“修复前基线”与“修复后结果”
   - 是否在 regression 模式下对 verdict 做更严格的对比收口

## 8. 当前结论

当前 `/src` 已经完成第一版主链路收口，并更适合承担**第一阶段：漏洞报告驱动的内部复现验证**：

- 主流程已简化
- 多余支线已移除
- 产物已可落盘
- 回归已可跑通

但它还不是最终形态。

当前最重要的后续工作不是继续把更多能力硬塞进第一阶段 `/src`，而是：

- 让 analyzer 判定更稳
- 让左侧与右侧的 `/src` 展示职责进一步分离
- 把已经落地的 `/src` 专用步骤合同继续往“可审计、可落盘、可校验”方向收口
- 单独规划第二阶段“修复后的复现验证”，避免与当前第一阶段主链耦合过早
