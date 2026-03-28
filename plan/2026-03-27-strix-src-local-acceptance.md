# Strix `/src` 本地源码手工验收说明

## 1. 结论先说

当前 `/src` 二开能力不在远端 sandbox 镜像里，主要位于当前仓库的宿主 Python 代码中，包括：

- `/src` slash command 解析
- root agent 对 `<src_repro_task>` 的确定性编排
- `src_repro_root` / analyzer / planner / reproducer skill 加载
- `result_parser.py` / `prompt_budget.py`
- `save_src_repro_bundle` 与结果落盘

远端 Docker 镜像当前只负责 sandbox / tool server，也就是 browser / proxy / terminal / python 等执行能力。

因此：

- 如果运行的是“当前仓库源码宿主 + 远端 sandbox 镜像”，`/src` 能力应该存在
- 如果运行的是“旧版已安装 CLI / 打包版宿主 / 其他来源宿主”，即使 Docker 拉起成功，也不会看到本次 `/src` 二开能力

## 2. 推荐验收启动方式

在仓库根目录 `F:\Study\strix` 下执行，优先使用当前源码直接启动宿主：

```powershell
uv run python -m strix.interface.main --target <你的验收目标>
```

如果本地已经做过 editable 安装，也可以使用：

```powershell
uv run strix --target <你的验收目标>
```

不建议把“Docker 启动了 sandbox”误认为“宿主就是当前源码”。手工验收时，优先以上面两条命令为准。

## 3. 启动前检查

至少确认：

- Docker Desktop 已启动
- 已配置 `STRIX_LLM`
- 如所选模型需要 API Key，已配置 `LLM_API_KEY`

也可以直接在仓库根目录放置 `.env`，当前 CLI 启动时会自动加载。例如：

```dotenv
STRIX_LLM=openai/gpt-5.4
LLM_API_KEY=your-api-key
STRIX_REASONING_EFFORT=high
```

可以先用下面命令确认当前源码入口可用：

```powershell
uv run python -m strix.interface.main --help
```

也可以确认当前加载的是仓库源码里的 `/src` 模块：

```powershell
uv run python -c "import strix.interface.slash_commands as m; print(m.__file__)"
```

预期输出路径应落在当前仓库下，例如：

```text
F:\Study\strix\strix\interface\slash_commands.py
```

## 4. 推荐验收流程

### 4.1 准备纯文本报告

示例：

```powershell
New-Item -ItemType Directory -Force tmp | Out-Null
@'
Target: http://host.docker.internal:8080
Vulnerability: Reflected XSS
Endpoint: /search?q=
Steps:
1. Open /search?q=%3Cscript%3Ealert(1)%3C/script%3E
2. Observe the payload reflected into HTML without sanitization
Expected:
- JavaScript executes in browser context
'@ | Set-Content tmp\src-report.txt -Encoding utf8
```

### 4.2 启动当前源码宿主

```powershell
uv run python -m strix.interface.main --target http://127.0.0.1:8080
```

说明：

- 首次运行如果拉取 `ghcr.io/usestrix/strix-sandbox:0.1.13`，这是正常现象
- 这个镜像只提供 sandbox，不代表 `/src` 宿主逻辑来自镜像
- 如果目标服务在宿主机本地，Strix 现有链路会把容器侧访问改写到 `host.docker.internal`

### 4.3 在 TUI 中输入 `/src`

```text
/src @tmp/src-report.txt
```

也可以直接内联：

```text
/src Target: http://host.docker.internal:8080 ...
```

## 5. 预期行为

输入 `/src` 后，预期链路如下：

1. 宿主层解析 `/src`，读取 `report_text`
2. 宿主层强制把任务发给 root agent
3. root agent 自动进入 `/src` 专用编排
4. 顺序创建 analyzer 子 agent
5. 若可复现，再创建 planner 子 agent
6. 再创建 reproducer 子 agent，使用 Strix 现有 browser / proxy / terminal / python 能力执行
7. 宿主层保存分析、计划、执行结果和最终 verdict

## 6. 验收产物检查

完成后检查：

```powershell
Get-ChildItem strix_runs -Recurse -Directory | Where-Object { $_.FullName -match 'src_repro' }
```

预期目录结构：

```text
strix_runs/<run_name>/src_repro/<bundle_id>/
```

预期至少包含：

- `00_source_report.txt`
- `01_analysis.json`
- `02_reproduction_plan.txt`
- `03_execution_trace.md`
- `04_final_verdict.md`
- `manifest.json`

## 7. 如果你看到“docker 拉了远端镜像，所以 `/src` 没有”

优先按下面顺序排查：

1. 先确认你是不是用当前仓库源码启动的宿主
2. 运行 `uv run python -m strix.interface.main --help`
3. 运行 `uv run python -c "import strix.interface.slash_commands as m; print(m.__file__)"`
4. 如果输出路径不在 `F:\Study\strix` 下，说明你跑的不是当前源码宿主

## 8. 当前边界

本说明覆盖的是：

- 当前仓库源码宿主
- 远端官方 sandbox 镜像
- `/src <纯文本报告>` 与 `/src @file`

本说明不覆盖：

- 宿主也一起打进自定义 Docker 镜像的验收方案
- DOCX / HTML / OCR / 图片提取前置流程
- `/src` 的专用 TUI renderer
