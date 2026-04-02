# Strix `/src verify` 判定与 Skill 合同实施方案

更新时间：2026-03-31

## 1. 目标

为 `/src verify` 补齐一版可直接开发的实现方案，使其具备：

- 与 `/src` reproducer 相同的“先生成详细 plan，再执行”的工作模式
- 独立于 `/src` reproducer 的最终判定语义
- 独立的 verify skill 合同
- 不扩大当前第一阶段 `/src` 主链范围的最小实现路径

本方案的重点不是新增更多 agent，而是把“修复后验证”正式建模成与“漏洞复现”不同的执行目标。

## 2. 当前状态

当前 `/src verify` 已经完成：

- 独立命令入口
- 独立 mode：`src_verification`
- 独立 root skill：`src_verify_root`
- 独立 orchestrator：`strix/src_verify/orchestration.py`
- 单子 agent 执行模型：root 只派发一个 `SRC Verify Executor`

但当前仍复用：

- `/src` 计划工具与结果落盘
- `/src` plan schema 的基础字段
- `/src` plan 工具的宿主接线

这意味着：

- workflow 已独立
- skill 语义尚未独立
- 当前 `/src verify` 仍更像“换了入口的 reproducer”，而不是“真正的修复后验证器”

## 3. 核心定位

`/src verify` 的目标不是再次证明漏洞“能不能打出来”，而是：

1. 在与原报告可比较的条件下，重新执行原漏洞链
2. 判断原成功标志是否仍然命中
3. 判断修复后的安全行为是否成立
4. 给出 fix verification 视角下的最终 verdict

因此，`/src verify` 不是：

- broad recon
- 修复后绕过挖掘
- 对默认扫描主链的替代
- “把 repro verdict 反过来”的简单包装

## 4. 与 `/src` reproducer 的关键差异

### 4.1 目标不同

`/src` reproducer` 的目标：

- 证明原漏洞链仍可成立

`/src verify` 的目标：

- 证明原漏洞链在修复后不再成立，并且修复后的安全行为真实成立

### 4.2 最终判定不同

`/src` reproducer 当前使用：

- `reproducible`
- `not reproducible`
- `blocked`

`/src verify` 建议改为：

- `still reproducible`
- `fixed`
- `blocked`

其中最关键的区别是：

- `not reproducible` 不等于 `fixed`
- `fixed` 的门槛必须高于“这次没打出来”

### 4.3 verify 必须有“可比性闸门”

`/src verify` 比 `/src` reproducer 多一个强约束：

- 当前验证必须与原报告中的漏洞链可比较

如果以下任何一项无法确认，则不能直接判 `fixed`：

- 是否进入了原报告要求的目标页面或目标功能区域
- 是否具备原报告要求的登录态/普通账号/角色前提
- 是否真正发出了对应请求，或真正完成了对应 UI 操作链
- 是否检查了原报告定义的成功标志或等价成功标志

一旦“可比性”不成立，最终只能判 `blocked`，而不是 `fixed`。

### 4.4 verify 需要正向的“修复后安全行为证据”

`/src` reproducer 里，决定性验证链走完且未命中成功标志，可以收口到 `not reproducible`。

`/src verify` 里，想判 `fixed`，除了“旧成功标志未出现”以外，还应尽可能命中修复后的安全行为证据，例如：

- XSS payload 被转义、过滤或仅以纯文本展示
- 越权请求被 403、404、业务拒绝或权限校验错误拦截
- 危险副作用未发生，且服务端返回明确拒绝/校验失败结果
- 原本危险写入点变成安全写入、拒绝写入或隔离写入

如果只观察到“没打出来”，但没有足够证据说明修复后的正确行为成立，优先判 `blocked`，而不是贸然判 `fixed`。

## 5. `/src verify` 的最终 verdict 定义

### 5.1 `still reproducible`

定义：

- 在与原报告可比较的条件下，旧漏洞成功标志再次命中

命中示例：

- 修复后仍能触发原报告定义的 XSS 执行
- 修复后仍能拿到原本不应访问的数据
- 修复后仍能完成原报告定义的危险状态变更
- 修复后仍能触发原报告定义的服务端副作用

判定原则：

- 只要旧成功标志命中，立即收口到 `still reproducible`
- 优先级最高

### 5.2 `fixed`

定义：

- 在与原报告可比较的条件下，决定性验证链已真正完成
- 旧成功标志未再出现
- 且观察到了足以支持“修复后安全行为成立”的证据

必须同时满足：

- 关键前提成立
- 关键验证链走完
- 旧成功标志缺失
- 修复后安全行为成立

不满足以上全部条件时，不应直接判 `fixed`。

### 5.3 `blocked`

定义：

- 决定性验证链未完成
- 或当前验证与原报告不可比较
- 或缺少判断是否 fixed 的必要证据

典型场景：

- 登录态/测试账号不可用
- 目标页面未进入
- 关键请求未真正发出或未能确认
- 代理、中间层、环境阻断
- 报告未提供足够 baseline，导致无法确认修复是否生效
- 仅观察到“旧成功标志没出现”，但没有足够证据支持“已 fixed”

## 6. `/src verify` 的 plan 合同

### 6.1 工作模式

`/src verify` 第一版继续保持单子 agent 模型：

1. verify executor 读取 `report_text`
2. 先生成详细 verification plan
3. 再按 verification plan 执行
4. 最后输出 verify verdict

### 6.2 详细 verification plan 至少应包含的内容

每一步尽量保留以下字段：

- `title`
- `objective`
- `suggested_action`
- `required_inputs`
- `expected_evidence`
- `evidence_type`
- `success_judgment`
- `negative_judgment`
- `blocked_judgment`
- `stop_rule`

### 6.3 第一版对现有 plan 工具的最小兼容策略

为了避免第一版就重写 `/src` 计划工具，建议第一版 `verify` 仍复用现有：

- `create_src_plan`
- `get_src_plan`
- `update_src_plan_step`

但在 verify skill 中强制约定字段语义：

- `success_judgment`
  - 表示命中“旧漏洞成功标志”
  - 一旦命中，贡献给最终 `still reproducible`

- `negative_judgment`
  - 表示该决定性验证节点已完成验证，旧成功标志未命中
  - 且观察到足以支持“修复后安全行为成立”的证据
  - 贡献给最终 `fixed`

- `blocked_judgment`
  - 表示该节点无法完成决定性验证
  - 贡献给最终 `blocked`

也就是说，第一版 verify 不新增新 tool 字段，而是：

- 复用当前 schema
- 但重新解释现有 judgment 语义

### 6.4 第二版再考虑的 schema 优化

如果第一版验证稳定，后续可再考虑把 plan schema 扩成 verify 专用字段，例如：

- `original_success_marker`
- `expected_secure_behavior`
- `comparability_requirements`
- `still_reproducible_judgment`
- `fixed_judgment`

这不是第一版必须项。

## 7. `/src verify` skill 合同

建议新增 skill：

- `strix/skills/src_report/verify_plan_executor.md`

### 7.1 职责

verify executor 只负责：

- 从 `report_text` 中提取原漏洞链
- 先创建详细 verification plan
- 按 plan 执行验证
- 根据 verify 专用 verdict 语义收口

### 7.2 硬约束

- 不得重新退回第一阶段 `/src` reproducer 语义
- 不得 broad recon
- 不得扩展攻击面
- 不得把修复后验证变成“修复后绕过挖掘”
- 不得把“这次没打出来”等价为 `fixed`
- 不得在关键验证链未完成时给出 `fixed`

### 7.3 执行前必须完成的动作

在调用任何执行型工具前，必须：

- 先生成 detailed verification plan
- 明确原报告中的旧成功标志
- 明确当前验证所需的 comparability 条件
- 明确修复后应出现的安全行为

### 7.4 最终输出合同

建议第一版仍沿用当前四段式结构，以减少 parser 改动：

1. `## 1) Execution Todo`
2. `## 2) Verification Execution Notes`
3. `## 3) Skills/MCP Execution Trace`
4. `## 4) Final Verdict`

其中 `## 4) Final Verdict` 至少输出：

- `verdict: still reproducible|fixed|blocked`
- `reason: ...`
- `comparability: established|partial|missing`
- `old_success_marker: hit|not_hit|unknown`
- `secure_behavior: observed|not_observed|unknown`

## 8. `/src verify` orchestration 方案

第一版建议保持单子 agent 模型，不新增 verify analyzer。

本轮已完成切换：

- `strix/src_verify/orchestration.py`

- `SRC Verify Executor`
- `verify_plan_executor`

### 8.1 第一版不新增 verify analyzer 的原因

本轮立项时，verify 的主要缺口不在“前置分析不足”，而在：

- skill 语义未独立
- verdict 模型未独立
- fixed 判定门槛未单独建模

因此第一版优先拆 executor，比先加 analyzer 更有价值。

### 8.2 orchestrator 需要同步修改的点

- `_infer_final_verdict` 识别：
  - `still reproducible`
  - `fixed`
  - `blocked`
- 最终摘要文案改成 verify 语义
- 输出 message 不再复用 reproducer 口径

## 9. 与 `/src` reproducer 的判定对照

### 9.1 `/src` reproducer

- 命中旧成功标志：`reproducible`
- 决定性验证链完成，但未命中成功标志：`not reproducible`
- 决定性验证链未完成：`blocked`

### 9.2 `/src verify`

- 命中旧成功标志：`still reproducible`
- 决定性验证链完成，旧成功标志未命中，且观察到修复后安全行为：`fixed`
- 其余不能得出可靠 fix 结论的情况：`blocked`

### 9.3 关键分析结论

verify 比 repro 多出的核心门槛有两个：

- comparability gate
- secure-behavior gate

这是 verify 与 repro 最本质的不同点。

## 10. 第一版落地范围

### 10.1 本轮建议落地

- 新增 `verify_plan_executor` skill
- `/src verify` 改用 verify 专用 skill
- verify verdict 从 `not reproducible` 迁移为 `fixed`
- verify parser/orchestrator 支持 `still reproducible|fixed|blocked`
- 补对应单元与最小集成测试

### 10.2 本轮不做

- verify 专用 analyzer
- baseline 文件独立落盘
- fix 前后自动 diff
- 固定凭据库
- 登录前置自动化体系
- verify 专用 plan tool/schema/renderer 全量重构

## 11. 测试建议

至少补以下测试：

- `tests/src_verify/test_orchestration.py`
  - verdict 识别 `still reproducible`
  - verdict 识别 `fixed`
  - verdict 识别 `blocked`

- verify skill 合同测试
  - 命中旧成功标志 -> `still reproducible`
  - 未命中旧成功标志但也无安全行为证据 -> `blocked`
  - 未命中旧成功标志且命中修复后安全行为 -> `fixed`

- 最小集成测试
  - `/src verify` fixed
  - `/src verify` still reproducible
  - `/src verify` blocked

## 12. 推荐实施顺序

1. 新增 `verify_plan_executor` skill 文档
2. 修改 `src_verify/orchestration.py` 切换 skill 名称与 verdict 解析
3. 补 verify skill 合同测试
4. 补 verify orchestration 与 integration 测试
5. 跑通最小真实案例后，再决定是否进入第二版 schema/落盘优化

## 13. 当前结论

`/src verify` 的正确方向不是继续复用 reproducer skill，而是：

- 保持“先 plan，再执行”的流程相似性
- 但把最终判定升级成 verify 专用语义：
  - `still reproducible`
  - `fixed`
  - `blocked`

其中 `fixed` 的门槛必须显著高于 `/src` reproducer 中的 `not reproducible`。

这就是 `/src verify` 第一版 skill 独立化时最重要的建模边界。

## 14. 当前落地进度（2026-03-31）

当前完成到：

- verify workflow 第一版 skill 独立化收口

已完成：

- 新增 `verify_plan_executor` skill
- `strix/src_verify/orchestration.py` 已切到 `SRC Verify Executor` + `verify_plan_executor`
- verify verdict 已切为 `still reproducible|fixed|blocked`
- verify verdict 已支持持久化解析
- verify root skill 已恢复并对齐单子 agent workflow
- verify 相关单元测试与最小集成测试已补齐

未完成：

- verify 专用 analyzer
- baseline / 修复前后自动对比
- verify 专用 plan schema 与 renderer

当前风险：

- 仍复用 `/src` 第一版 plan 工具与基础 schema，需要继续观察 verify judgment 语义是否足够稳定

下一步建议：

- 在真实修复案例上继续验证 comparability / secure-behavior gate
- 再决定是否进入第二版 baseline/diff 或 verify schema 优化
