# Strix `/src` 二开实施计划

## 1. 目标

在当前 Strix 项目中新增一个 `/src` 交互命令，用于对公司内部的纯文本 SRC 漏洞报告执行定向复现。

本次二开只集成“后置复现链路”，不集成旧项目中的文档解析、图片提取、OCR、占位符回填、DOCX 重建等前置流程。

最终目标流程：

1. 用户在 TUI 中输入 `/src <纯文本报告>` 或 `/src @<file>`
2. 宿主层解析命令，得到 `report_text`
3. 宿主层将任务路由给 root agent
4. root agent 自动加载 `/src` 专用编排 skill
5. root agent 串行创建 analyzer 子 agent
6. analyzer 输出 `can_reproduce`、`reason`、`missing_info`
7. 若不可复现，root agent 结束并落盘结果
8. 若可复现，root agent 创建 planner 子 agent
9. planner 输出结构化复现步骤
10. root agent 创建 reproducer 子 agent
11. reproducer 使用 Strix 现有 browser/proxy/terminal/python 能力执行复现
12. root agent 汇总计划、执行日志、最终 verdict，并保存产物

## 2. 范围边界

### 2.1 本次要做

- TUI 新增 `/src` 命令入口
- 支持直接传文本和 `@file` 文件引用
- 为 `/src` 模式增加宿主侧命令分流
- 为 `/src` 模式增加 root orchestration skill
- 增加 analyzer / planner / reproducer 三类业务 skill
- 增加最小化的 `/src` 结果落盘能力
- 增加必要的单元测试与集成测试

### 2.2 本次不做

- 不支持 DOCX / HTML 原始报告直接输入
- 不集成旧项目的 parser / OCR / rebuild 逻辑
- 不引入 LangGraph
- 不引入旧项目的 OpenCode client
- 不优先生成 DOCX 报告
- 不改动 Strix 默认扫描主流程

## 3. 总体设计

### 3.1 设计原则

- `/src` 是 Strix 的一种“专用交互模式”，不是新的独立 CLI 程序
- Strix 保持执行引擎角色，旧项目只迁移“复现业务规则”
- 业务规则通过 skill 和宿主侧 orchestration 表达，不新增第二套 agent runtime
- root agent 负责编排，子 agent 负责单职责执行
- `/src` 模式严格禁止默认 recon / scan 行为，必须是“报告驱动复现”

### 3.2 核心架构

- 宿主层：
  - 解析 `/src`
  - 读取文件内容
  - 定位 root agent
  - 给 root agent 注入 `/src` 编排上下文
- Root agent：
  - 按固定顺序调度 analyzer -> planner -> reproducer
  - 不自己做大段执行
  - 负责最终汇总和调用落盘工具
- Analyzer：
  - 只判断“是否可复现”
- Planner：
  - 只输出结构化复现步骤
- Reproducer：
  - 只按步骤执行，不重新设计计划
- 宿主落盘：
  - 保存源报告、分析结果、复现计划、最终结论、执行痕迹摘要

## 4. 与旧项目的映射关系

### 4.1 保留逻辑

来自 `Src_verify_Dev` 的可迁移核心：

- `analysis_service.py`
  - 解析 analyzer 返回的 JSON
  - fallback 推断逻辑
- `reproduce_service.py`
  - prompt 结构
  - 计划生成与执行阶段的职责分离
- `prompt_budget.py`
  - 长文本裁剪逻辑
- `opencode-skills/*`
  - analyzer / planner / reproducer 三类业务规则
- `verdict-rules.md`
  - reproducer 的最终结论规则

### 4.2 不迁逻辑

- `parser_service.py`
- `node_parse.py`
- `node_ocr.py`
- `rebuild_service.py`
- `OpenCodeClient`
- `LangGraph graph.py`

## 5. 文件改动清单

### 5.1 需要修改的现有文件

#### `strix/interface/tui.py`

新增职责：

- 在 `_send_user_message()` 中识别 `/src`
- 将 `/src` 转给专门的 slash command handler
- `/src` 强制路由到 root agent，而非当前选中 agent
- 在 Help 文案中增加 `/src` 的说明

建议改动点：

- `HelpScreen.compose()`
- `StrixTUIApp._send_user_message()`
- 视情况补一个 `_handle_slash_command()` 私有方法

#### `strix/tools/agents_graph/agents_graph_actions.py`

新增职责：

- 提供宿主侧辅助函数定位 root agent
- 提供宿主侧安全访问 agent instance 的方法

建议新增非 tool 函数：

- `get_root_agent_id() -> str | None`
- `get_agent_instance(agent_id: str) -> Any | None`

#### `strix/tools/__init__.py`

新增职责：

- 导入新的 `src_repro` 工具模块

### 5.2 需要新增的文件

#### `strix/interface/slash_commands.py`

职责：

- 解析 slash command
- 目前先只实现 `/src`
- 读取 `@file`
- 构造标准化 `report_text`
- 检查输入合法性
- 定位 root agent
- 将 `/src` 任务注入 root agent

建议函数：

- `is_slash_command(message: str) -> bool`
- `parse_src_command(message: str, cwd: Path) -> SrcReproRequest`
- `dispatch_src_command(app: Any, message: str) -> dict[str, Any]`
- `_resolve_report_text(argument: str, cwd: Path) -> str`
- `_build_src_instruction(report_text: str, source_label: str | None) -> str`

#### `strix/src_repro/contracts.py`

职责：

- 定义 `/src` 域的轻量数据契约

建议数据结构：

- `SrcReproRequest`
  - `report_text`
  - `source_label`
  - `created_at`
- `SrcReproAnalysis`
  - `can_reproduce`
  - `reason`
  - `missing_info`
- `SrcReproBundle`
  - `source_report`
  - `analysis`
  - `reproduction_plan`
  - `execution_trace`
  - `final_verdict`
  - `artifacts`

#### `strix/src_repro/prompt_budget.py`

职责：

- 从旧项目迁移长文本裁剪逻辑
- 只保留纯文本报告相关函数

建议函数：

- `trim_for_analysis()`
- `trim_for_plan()`
- `trim_for_reproduction()`
- `build_budgeted_prompt()`

#### `strix/src_repro/result_parser.py`

职责：

- 解析 analyzer 返回内容
- 支持 JSON 优先、文本 fallback

建议函数：

- `parse_analysis(raw_text: str) -> SrcReproAnalysis`
- `_infer_can_reproduce()`
- `_infer_reason()`
- `_infer_missing_info()`

#### `strix/src_repro/output.py`

职责：

- 负责 `/src` 结果落盘
- 产物统一落到当前 run 目录下

建议输出目录：

- `strix_runs/<run_name>/src_repro/<bundle_id>/`

建议文件：

- `00_source_report.txt`
- `01_analysis.json`
- `02_reproduction_plan.txt`
- `03_execution_trace.md`
- `04_final_verdict.md`
- `manifest.json`

建议函数：

- `save_src_repro_bundle(tracer: Any, bundle: SrcReproBundle) -> dict[str, str]`
- `_get_src_repro_dir(tracer: Any, bundle_id: str) -> Path`

#### `strix/tools/src_repro/__init__.py`

职责：

- 工具模块初始化导出

#### `strix/tools/src_repro/src_repro_actions.py`

职责：

- 提供 root agent 在流程结束时调用的持久化工具

建议工具：

- `save_src_repro_bundle(...)`

入参建议：

- `source_report`
- `analysis_json`
- `reproduction_plan`
- `execution_trace`
- `final_verdict`
- `source_label`

#### `strix/tools/src_repro/src_repro_actions_schema.xml`

职责：

- 给上面工具定义 XML schema

#### `strix/skills/coordination/src_repro_root.md`

职责：

- `/src` 模式的 root 编排规则

必须约束：

- 不做 recon
- 不做默认 scan
- 仅围绕输入报告执行复现
- 必须串行创建 analyzer / planner / reproducer
- 必须在结束前调用 `save_src_repro_bundle`

#### `strix/skills/src_report/report_repro_analyzer.md`

职责：

- 纯文本报告的可复现性分析

必须约束：

- 输出严格 JSON
- 仅输出 `can_reproduce`、`reason`、`missing_info`

#### `strix/skills/src_report/report_to_repro_checklist.md`

职责：

- 从报告中提取复现步骤

必须约束：

- 不重新判断可复现性
- 只做“报告 -> 结构化步骤”

#### `strix/skills/src_report/repro_plan_executor.md`

职责：

- 严格按计划执行

必须约束：

- 不重写计划
- 每步都要记录执行状态
- 最终 verdict 只能是
  - `reproducible`
  - `not reproducible`
  - `blocked`

### 5.3 可选新增文件

#### `strix/interface/tool_components/src_repro_renderer.py`

职责：

- 优化 `save_src_repro_bundle` 工具在 TUI 中的显示效果

不是第一阶段必须项。

## 6. 运行时调用链设计

### 6.1 宿主层调用链

1. 用户在 TUI 输入 `/src ...`
2. `tui.py` 识别 slash command
3. `slash_commands.py` 解析命令
4. 读取文件或内联文本，得到 `report_text`
5. 宿主层找到 root agent
6. 宿主层取消 root agent 当前执行
7. 宿主层向 root agent 发送一个结构化用户消息

建议注入消息模板：

```text
<src_repro_task>
  <mode>src_reproduction</mode>
  <source_label>...</source_label>
  <instructions>
    Treat the following vulnerability report as the only source of truth.
    Do not perform broad reconnaissance.
    First analyze reproducibility, then plan, then execute.
  </instructions>
  <report_text>
  ...
  </report_text>
</src_repro_task>
```

### 6.2 Root agent 调度链

1. root agent 识别到 `src_reproduction` 任务
2. root agent 加载 `src_repro_root`
3. root agent 创建 analyzer agent
4. analyzer 完成后，root agent 接收 JSON 结果
5. 若 `can_reproduce=false`
  - root agent 直接汇总并调用 `save_src_repro_bundle`
6. 若 `can_reproduce=true`
  - root agent 创建 planner agent
  - planner 完成后回传复现计划
  - root agent 创建 reproducer agent
  - reproducer 按计划执行
  - root agent 收集执行结果与 verdict
7. root agent 调用 `save_src_repro_bundle`
8. root agent 进入 waiting 状态

## 7. 各 agent 的职责合同

### 7.1 Root agent

只负责：

- 分阶段调度
- 决策分支
- 结果汇总
- 最终落盘

禁止：

- 自己长时间进行浏览器和代理执行
- 跳过 analyzer 或 planner 直接进入执行

### 7.2 Analyzer agent

输入：

- 纯文本漏洞报告

输出：

- 严格 JSON

禁止：

- 输出泛泛安全建议
- 擅自生成复现步骤

### 7.3 Planner agent

输入：

- 纯文本漏洞报告
- analyzer 结论

输出：

- 结构化复现步骤

禁止：

- 重新判断可复现性
- 直接执行

### 7.4 Reproducer agent

输入：

- 原始报告
- 复现计划

输出：

- 执行笔记
- 工具轨迹
- final verdict

禁止：

- 自己扩展攻击范围
- 不按计划擅自增加新的利用链

## 8. 数据与产物约定

### 8.1 analysis 结果格式

要求 analyzer 最终输出可被 `result_parser.py` 稳定解析：

```json
{
  "can_reproduce": true,
  "reason": "报告已包含关键复现信息",
  "missing_info": []
}
```

### 8.2 final verdict 结果格式

reproducer 最终结果必须至少包含：

- `Plan Coverage`
- `Reproduction Execution Notes`
- `Skills/MCP Execution Trace`
- `Final Verdict`

其中 `Final Verdict` 只能是：

- `reproducible`
- `not reproducible`
- `blocked`

## 9. 详细实施阶段

### Phase 1：命令入口与最小骨架

目标：

- `/src` 命令能在 TUI 中被识别和路由

任务：

- 新增 `slash_commands.py`
- 改 `tui.py` 的 `_send_user_message()`
- 增加 help 文案
- 增加 root agent 定位 helper

验收：

- 输入 `/src hello`
- 宿主不会把消息发给当前子 agent
- 而是正确发给 root agent

### Phase 2：skill 与 agent 编排

目标：

- root agent 能按 analyzer -> planner -> reproducer 顺序工作

任务：

- 新增 `src_repro_root.md`
- 新增 analyzer / planner / reproducer 三个 skill
- 验证 root agent 能创建三个子 agent

验收：

- analyzer 的 JSON 能被稳定收回
- planner 的步骤能被稳定收回
- reproducer 能被正确创建

### Phase 3：结果解析与 prompt budget

目标：

- 长报告可稳定处理
- analyzer 结果可容错解析

任务：

- 迁 `prompt_budget.py`
- 迁 `result_parser.py`
- 在 `/src` 命令里对报告文本做裁剪

验收：

- 超长报告输入时不至于直接压爆上下文
- analyzer 返回非标准文本时仍能 fallback

### Phase 4：结果落盘

目标：

- `/src` 有稳定产物输出

任务：

- 新增 `src_repro/output.py`
- 新增 `save_src_repro_bundle` 工具
- root agent 在成功/失败/不可复现时都能落盘

验收：

- run 目录下出现 `src_repro/<bundle_id>/`
- 包含 source report、analysis、plan、verdict 等文件

### Phase 5：测试与收口

目标：

- `/src` 最小闭环可回归

任务：

- 增加 interface tests
- 增加 output tests
- 增加 src_repro tool tests
- 增加一条最小集成测试

验收：

- 测试通过
- 手工验证一条 `/src @file` 路径

## 10. 测试计划

### 10.1 单元测试

- `tests/interface/test_slash_commands.py`
  - 解析 `/src text`
  - 解析 `/src @file`
  - 文件不存在报错
- `tests/src_repro/test_result_parser.py`
  - 标准 JSON
  - code block JSON
  - fallback 文本推断
- `tests/src_repro/test_prompt_budget.py`
  - 长文本裁剪
  - 高优先级字段保留
- `tests/src_repro/test_output.py`
  - 输出目录创建
  - manifest 写入
- `tests/tools/test_src_repro_actions.py`
  - 工具参数校验
  - 文件成功写出

### 10.2 集成测试

- `tests/interface/test_tui_src_dispatch.py`
  - `/src` 是否路由到 root
- `tests/integration/test_src_repro_minimal_flow.py`
  - mock analyzer/planner/reproducer
  - 走完整闭环

## 11. 风险与规避

### 风险 1：root agent 仍按默认 scan 思维运行

规避：

- `src_repro_root.md` 必须明确禁止 recon / broad scan
- 宿主层消息模板必须明确 mode

### 风险 2：analyzer 输出不稳定

规避：

- 迁移旧项目 `AnalysisService.parse_analysis()` 的 fallback 逻辑

### 风险 3：reproducer 擅自扩展计划

规避：

- skill 中严格约束
- root agent 在 prompt 中强调“只执行计划”

### 风险 4：结果落盘与 tracer 目录冲突

规避：

- `/src` 统一使用 `strix_runs/<run_name>/src_repro/<bundle_id>/`
- 不覆盖现有 vulnerability report 目录

### 风险 5：当前 root agent 正在运行普通扫描

规避：

- `/src` 派发前先 cancel root 当前执行
- 明确 `/src` 是高优先级新任务

## 12. 交付验收标准

以下全部满足，视为本次 `/src` 第一阶段二开完成：

- TUI 中支持 `/src <text>` 与 `/src @file`
- `/src` 任务被正确路由到 root agent
- root agent 自动加载 `/src` 专用编排 skill
- analyzer / planner / reproducer 三阶段按顺序执行
- analyzer 能输出并解析 `can_reproduce/reason/missing_info`
- planner 能输出结构化复现步骤
- reproducer 能调用 Strix 现有工具执行
- root agent 最终能保存 source report、analysis、plan、trace、verdict
- 关键测试通过

## 13. 建议实施顺序

建议按以下顺序推进，避免一次改动过大：

1. 先做 `/src` 命令入口和 root 路由
2. 再加 `src_repro_root.md`
3. 再加 analyzer / planner / reproducer skill
4. 再加 `result_parser.py` 和 `prompt_budget.py`
5. 再加 `save_src_repro_bundle`
6. 最后补测试和 UI 优化

## 14. 备注

本计划面向第一阶段可用版本，目标是把“纯文本报告驱动复现”落到 Strix 现有架构中。

后续如需继续演进，可在第二阶段考虑：

- 支持 Markdown / JSON 报告格式规范化输入
- 增加 `/src-review`、`/src-rerun` 等命令
- 增加 DOCX 输出
- 增加 replay / resume
- 为 `/src` 结果增加专用 renderer
