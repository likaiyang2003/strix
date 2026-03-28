# AGENTS.md

本文件定义当前仓库的协作开发规范，适用于后续所有在 `F:\Study\strix` 内进行的功能开发、修复、重构与测试工作。

## 1. 项目概况

- 项目名称：`strix-agent`
- 技术栈：Python 3.12+，Textual TUI，LiteLLM，Docker runtime，多 agent 工具编排
- 当前仓库主线职责：AI 驱动的安全验证与漏洞复现/扫描
- 当前新增业务方向：`/src` 纯文本漏洞报告驱动复现模式

## 2. 环境与工具规范

### 2.1 Python 与环境管理

- 当前系统可用 `uv`
- 统一优先使用 `uv` 管理虚拟环境与运行命令
- 默认虚拟环境目录：`.venv`

推荐初始化方式：

```powershell
uv venv
```

### 2.2 依赖安装规范

当前仓库依赖元数据仍主要维护在 `pyproject.toml` 的 Poetry 结构中，`uv sync --group dev` 目前不能直接识别 `tool.poetry.group.dev`。

因此当前约定如下：

- 运行命令优先使用 `uv run ...`
- 依赖声明的事实来源仍是 `pyproject.toml`
- 不在没有必要的情况下擅自把整个项目从 Poetry 结构迁移到 PEP 621/uv 原生结构

如果只是本地开发或执行测试，优先使用以下方式之一：

```powershell
uv pip install -e .
uv pip install mypy ruff pyright pylint bandit pytest pytest-asyncio pytest-cov pytest-mock pre-commit black isort
```

如果本地已经装有 Poetry，也允许：

```powershell
uv run poetry install --with dev
```

### 2.3 命令执行规范

- 优先使用 `uv run <command>` 执行项目相关命令
- 不直接假设用户本机已激活虚拟环境
- 不在规范中使用当前仓库无法直接成立的命令

推荐命令：

```powershell
uv run pytest -q
uv run ruff check strix tests
uv run mypy strix
uv run pyright strix
uv run python -m compileall strix
```

## 3. 开发总原则

- 先理解现有架构，再动代码
- 优先局部修改，不做与任务无关的大重构
- 保持现有 Strix 主扫描链路稳定
- 新功能优先以“新增模块 + 小范围接入”的方式实现
- 不重复造已有执行能力，优先复用 Strix 现有 browser / proxy / terminal / python / agent graph 能力

## 4. 目录职责约定

### 4.1 核心目录

- `strix/agents/`
  - agent loop、agent state、StrixAgent 入口
- `strix/interface/`
  - CLI/TUI、交互入口、渲染层
- `strix/tools/`
  - tool 注册、schema、执行器、各类工具实现
- `strix/runtime/`
  - Docker sandbox、tool server
- `strix/skills/`
  - agent skill 规则与知识注入
- `strix/telemetry/`
  - run 目录、事件、结果持久化
- `tests/`
  - 回归与单元/集成测试
- `plan/`
  - 实施计划、方案文档

### 4.2 `/src` 二开目录约定

与 `/src` 相关的新能力，优先放在以下位置：

- `strix/interface/`
  - slash command 入口
- `strix/src_repro/`
  - `/src` 模式下的业务契约、结果解析、输出封装
- `strix/tools/src_repro/`
  - `/src` 专用宿主工具
- `strix/skills/src_report/`
  - analyzer / planner / reproducer 业务 skill
- `strix/skills/coordination/`
  - `/src` 模式 root orchestration skill

## 5. `/src` 功能的专门约束

### 5.1 当前范围

当前 `/src` 只处理：

- 纯文本漏洞报告
- 文本内联输入
- `@file` 文件引用输入

当前 `/src` 不处理：

- DOCX 原始文档
- HTML 报告解析
- 图片提取
- OCR
- 占位符回填

### 5.2 `/src` 的流程约束

`/src` 必须遵循固定流程：

1. 宿主层接收 `/src`
2. 解析并生成 `report_text`
3. 路由到 root agent
4. root agent 调 analyzer
5. analyzer 输出 `can_reproduce/reason/missing_info`
6. 若不可复现，直接收尾
7. 若可复现，调 planner
8. planner 输出结构化复现步骤
9. 调 reproducer 执行
10. root 汇总并落盘

禁止行为：

- `/src` 模式下自动做 broad recon
- `/src` 模式下自动进入默认扫描逻辑
- reproducer 擅自扩展攻击范围
- planner 重新判断可复现性
- analyzer 直接生成执行计划

### 5.3 `/src` 的实现原则

- `/src` 是 Strix 的专用模式，不是独立项目
- 只迁移旧项目的后置复现业务规则，不迁移旧的 OpenCode client 和 LangGraph
- 业务规则通过 skill 和宿主 orchestration 实现

## 6. 代码规范

### 6.1 类型与接口

- 公共函数必须尽量补齐类型标注
- 新增跨模块数据结构，优先使用 `dataclass`、`TypedDict`
- 避免无边界 `dict[str, Any]` 滥用
- 新增模块优先写清输入输出契约

### 6.2 错误处理

- 禁止裸 `except:`
- 对外部调用使用明确异常类型或统一封装
- 错误信息必须可定位上下文
- 失败时优先保留结构化错误信息

### 6.3 文件与路径

- 优先使用 `pathlib.Path`
- 新增文件写出逻辑必须限制在允许目录内
- 不允许未校验的绝对路径覆盖项目外文件

### 6.4 工具扩展

新增 tool 时必须同时具备：

- Python 实现
- XML schema
- 注册导入

如该 tool 会频繁在 TUI 中展示，建议补 renderer，但不是第一阶段硬要求。

### 6.5 Skill 规范

- skill 内容必须聚焦单一职责
- `/src` analyzer / planner / reproducer skill 必须分离
- 规则要可执行、避免泛泛建议
- 对输出格式有硬约束的 skill，必须明确写死输出合同

## 7. 测试规范

### 7.1 基本要求

- 所有新增逻辑至少补单元测试
- 关键交互链路补最小集成测试
- 修 bug 必须附回归测试

### 7.2 推荐测试命令

```powershell
uv run pytest -q
uv run pytest tests/interface -q
uv run pytest tests/tools -q
uv run pytest tests/src_repro -q
```

### 7.3 `/src` 相关测试最低覆盖

至少包括：

- slash command 解析
- `@file` 读取
- root agent 路由
- analyzer 结果解析
- 落盘工具
- 最小 `/src` 流程集成测试

## 8. 质量门槛

提交或交付前，推荐至少运行：

```powershell
uv run python -m compileall strix
uv run ruff check strix tests
uv run pytest -q
```

如果改动涉及类型或核心链路，增加：

```powershell
uv run mypy strix
uv run pyright strix
```

## 9. 文档维护规范

- 新增功能前，如范围较大，先在 `plan/` 下写实施计划
- 当前 `/src` 二开计划以以下文件为准：
  - `plan/2026-03-26-strix-src-repro-plan.md`
- 如果实施过程中范围变化，优先同步更新计划文档
- 如果某个 Phase 没有完整实现完成，不要默认直接进入下一个 Phase
- 若中途停止、切换方向、缩小范围、或只完成了部分代码实现，必须先更新 `plan/2026-03-26-strix-src-repro-plan.md`
- 计划更新至少要写清楚：
  - 当前完成到哪个 Phase / Step
  - 哪些子任务已完成
  - 哪些子任务未完成
  - 当前阻塞点或风险
  - 下一步建议动作
- 重要目录或开发约束变化时，同步更新本 `AGENTS.md`

## 10. 禁止事项

- 不在未确认影响范围的情况下重构核心 agent loop
- 不随意改动默认 scan system prompt 的主体安全逻辑
- 不把 `/src` 模式实现成对默认扫描链路的硬覆盖
- 不引入旧项目的整套 workflow runtime
- 不引入无法在当前仓库稳定运行的工具链命令作为规范默认值

## 11. 当前推荐工作流

后续开发默认按以下顺序推进：

1. 先确认任务边界
2. 查阅相关代码与 `plan/` 文档
3. 先改最小入口与契约
4. 再补业务能力
5. 最后补测试与文档
6. 如果当前 Phase 未完整收口，先更新计划文档，再继续编码或切换到下一阶段

对 `/src` 功能，优先顺序是：

1. slash command 入口
2. root agent 路由
3. `/src` root skill
4. analyzer / planner / reproducer skill
5. 结果解析与落盘
6. 测试收口
