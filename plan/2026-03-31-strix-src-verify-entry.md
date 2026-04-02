# Strix `/src verify` 入口记录

更新时间：2026-03-31

## 1. 本次落地

- 新增第二阶段命令入口：
  - `/src verify <report_text>`
  - `/src verify @file`
- `verify` 当前使用单子 agent workflow，`/src verify run` 已移除。

## 2. 当前代码行为

- slash command 解析层会识别 `verify` 并写入 `execution_stage="verify"`
- `/src` 结构化任务消息会携带 `<execution_stage>verify</execution_stage>`
- `SrcReproTask` 会接收并保留该阶段字段
- verify executor 子任务消息会继续携带该阶段字段
- 现阶段 `/src verify` 走 verify 专用 root skill 与 orchestration

## 3. 为什么先只做入口

- 第二阶段“修复后的复现验证”和当前第一阶段“报告驱动复现”目标不同
- 先独立命令入口，可以避免继续把第二阶段规则硬塞进当前 `/src` 主链
- 先让宿主层、任务契约、测试都认识 `verify`，后续再安全接入专门 workflow

## 4. 后续建议

- 为 `verify` 单独规划 root skill / orchestration
- 引入修复前 baseline 与修复后 verdict diff
- 明确登录态、固定账号、回归约束与结果落盘格式
