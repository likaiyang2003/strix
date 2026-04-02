# Strix `/src verify` Workflow Split

更新时间：2026-03-31

## 1. 本次收口

- `/src verify` 已从“只是入口字段”升级为独立 workflow
- 当前支持：
  - `/src verify <report_text>`
  - `/src verify @file`
  - 不再支持 `/src verify run`

## 2. 代码边界

- slash command 现在会为 verify 生成：
  - `<mode>src_verification</mode>`
  - `<requested_root_skill>src_verify_root</requested_root_skill>`
- root agent 现在会按 mode 分流：
  - `src_reproduction` -> 第一阶段 `/src`
  - `src_verification` -> 第二阶段 `/src verify`
- 第二阶段宿主编排入口：
  - `strix/src_verify/orchestration.py`
- 第二阶段 coordination skill：
  - `strix/skills/coordination/src_verify_root.md`

## 3. 当前第二阶段实际形态

已经独立的部分：

- 独立命令入口
- 独立 mode
- 独立 root skill
- 独立 orchestrator
- 单子 agent 执行模型：
  - root 不再派发 verify analyzer
  - root 只派发 `SRC Verify Executor`

暂时复用的部分：

- `/src` 现有计划工具与结果落盘
- `/src` 现有 `create_src_plan` / `get_src_plan` / `update_src_plan_step`

## 4. 当前结论

现在已经完成“先裁成独立工作流”这一步。

下一步再做的，不是继续切链，而是细化第二阶段自己的规则，例如：

- fix verification 专用 analyzer 口径
- 修复前 baseline / 修复后结果对比
- 更适合回归验证的 verdict 语义
- 账号、登录态、固定环境等第二阶段前置条件

详细可落地方案见：

- `plan/2026-03-31-strix-src-verify-implementation-plan.md`
