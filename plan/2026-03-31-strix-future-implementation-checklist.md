# Strix 未来实现计划清单

更新时间：2026-03-31

## 1. 目标

本清单用于记录基于 Claude Code 相关参考项目整理出的、适合 Strix 后续逐步落地的实现方向。

这些内容**不是当前 `/src` 第一阶段主链的立即必做项**，而是后续版本迭代时的未来能力清单。

当前默认前提：

- `/src` 第一阶段主链已经基本成型
- 当前重点仍是“漏洞报告驱动的内部复现验证”
- 以下能力用于未来增强，而不是现在强行并入当前主链

## 2. 总体原则

未来实现时，统一遵循以下原则：

- 先做宿主层分流与边界，再做业务能力扩展
- 先做结构化状态与工具边界，再做更多复杂 workflow
- 能在 skill 层收口的，优先在 skill 层收口
- 只有在 skill 层反复失稳时，才补宿主层强约束
- 新能力尽量通过“新增模式/新增子命令/新增状态产物”接入，不直接污染默认扫描链路

## 3. 未来实现项

### 3.1 命令先分流，再进入专用工作流

目标：

- 继续保持“不同任务类型走不同工作流”的架构方向
- 避免所有输入都回落到默认扫描主链

建议落地方向：

- 保持当前 `/src` 为专用入口
- 后续如实现“修复后回归验证”，新增专用子命令而不是硬塞进现有 `/src`
- 对不同模式分别定义：
  - 输入格式
  - skill 组合
  - 工具边界
  - 输出合同

候选实现项：

- `/src verify` 或 `/src regression`
- 更明确的 slash command routing contract
- 模式级 task message schema

优先级：高

### 3.2 工具按阶段下发，而不是全局暴露

目标：

- 让工具暴露范围与 agent 当前阶段绑定
- 降低非目标 agent 误用 `/src` 专用工具的概率

当前痛点：

- `create_src_plan`
- `get_src_plan`
- `update_src_plan_step`

虽然逻辑上只服务于 `/src` reproducer，但当前仍属于全局注册工具。

建议落地方向：

- 只对 `/src` reproducer 下发 `/src` 计划工具
- 非 `/src` agent 默认不暴露这类工具
- 或由宿主层在工具可用性检查阶段直接拒绝非目标阶段调用

候选实现项：

- tool visibility by agent stage
- tool registry filtering by mode
- stricter executor-side tool gating

优先级：高

### 3.3 Skill 元数据正式化

目标：

- 让 skill 不只是长 prompt，而是带明确契约的能力单元

建议增强的 skill 元数据：

- 适用阶段
- 允许工具范围
- 输入合同
- 输出合同
- 禁止行为
- 与其他 skill 的依赖关系

建议落地方向：

- 为 `/src` 相关 skill 形成统一 frontmatter 约束
- 明确 analyzer / reproducer / future regression skill 的职责边界
- 让技能装载更接近“模式组件”而不是单纯文本拼接

候选实现项：

- `src_report` skill metadata schema
- stage-aware skill loading
- skill capability validation

优先级：高

### 3.4 结构化状态与结果产物

目标：

- 让 `/src` 的计划、执行、结论更可审计、可恢复、可对比

当前状态：

- 已有文本落盘：
  - `02_reproduction_plan.txt`
  - `03_execution_trace.md`
  - `04_final_verdict.md`

未来建议：

- 增加结构化 JSON 落盘
- 为后续“修复前 vs 修复后”对比留接口

候选产物：

- `src_repro_plan.json`
- `src_repro_execution.json`
- `src_repro_verdict.json`
- 结构化步骤状态快照

可支持的后续能力：

- 更稳的 UI 重建
- 运行恢复
- 结果比对
- 审计与统计

优先级：中高

### 3.5 第二阶段单独建模：修复后的复现验证

目标：

- 把“修复后回归验证”明确建模成与当前第一阶段不同的能力

当前边界：

- 当前 `/src` 更适合第一阶段：
  - 读取漏洞报告
  - 判断能否复现
  - 生成步骤
  - 执行有界复现
  - 给研发提供修复输入

未来第二阶段目标：

- 在固定前提下重复执行同一漏洞链
- 验证修复后是否仍命中成功标志
- 比较修复前 / 修复后的 verdict 差异

可能涉及：

- 固定测试账号 / 凭据库
- 登录前置流程 / 会话复用
- regression replay 输入
- baseline 对比
- 更严格的 verdict 对齐

候选实现项：

- `/src verify`
- `/src regression`
- 修复前 baseline 保存
- 修复后 verdict diff

优先级：中高

## 4. 建议实施顺序

建议未来按以下顺序推进：

1. 工具按阶段下发
2. Skill 元数据正式化
3. 结构化状态与结果产物
4. 新的命令分流模式
5. 第二阶段“修复后的复现验证”

## 5. 当前结论

这 5 项都值得做，但不应一次性并入当前主链。

当前更合理的策略是：

- 保持 `/src` 第一阶段主链稳定
- 将本文件作为未来增强路线图
- 在真实报告回归中持续验证当前主链是否稳定
- 待第一阶段收口稳定后，再按本清单逐项推进
