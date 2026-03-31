from strix.skills import get_available_skills, load_skills


def test_src_report_skills_are_listed_in_available_skills() -> None:
    available = get_available_skills()

    assert "src_report" in available
    assert "report_repro_analyzer" in available["src_report"]
    assert "report_to_repro_checklist" in available["src_report"]
    assert "repro_plan_executor" in available["src_report"]


def test_load_skills_can_load_src_repro_root_and_src_report_skills() -> None:
    loaded = load_skills(
        [
            "src_repro_root",
            "report_repro_analyzer",
            "report_to_repro_checklist",
            "repro_plan_executor",
        ]
    )

    assert "src_repro_root" in loaded
    assert "report_repro_analyzer" in loaded
    assert "report_to_repro_checklist" in loaded
    assert "repro_plan_executor" in loaded

    root_skill = loaded["src_repro_root"]
    assert "analyzer -> reproducer" in root_skill
    assert "使用 `report_text` 作为执行输入" in root_skill
    assert "`report_to_repro_checklist` 仍可作为独立 skill 保留" in root_skill

    analyzer_skill = loaded["report_repro_analyzer"]
    assert '"can_reproduce"' in analyzer_skill
    assert "historical_packet_evidence" in analyzer_skill
    assert "post_exploitation_result" in analyzer_skill
    assert "Authorization: bearer null" in analyzer_skill
    assert "ordinary_authenticated_session_required" in analyzer_skill
    assert "special_role_or_special_account_required" in analyzer_skill
    assert "specific_report_secret_required_now" in analyzer_skill
    assert "你判断的是“这份报告是否足以进入 reproducer 开始尝试”" in analyzer_skill
    assert "只要报告已经足够让 reproducer 发起第一次有意义的受控复现尝试，就应优先判 `can_reproduce=true`" in analyzer_skill
    assert "普通登录态功能中的存储型 XSS" in analyzer_skill
    assert "如果报告展示了依赖会话的 UI 操作，不要自动把“当前缺少可用会话”视为阻塞" in analyzer_skill

    planner_skill = loaded["report_to_repro_checklist"]
    assert "需要测试者自备普通有效登录态" in planner_skill
    assert "Detailed Reproduction Steps" in planner_skill
    assert "Suggested Action / Invocation" in planner_skill
    assert "Required Inputs" in planner_skill
    assert "Evidence Type" in planner_skill
    assert "Stop / Failure Rule" in planner_skill
    assert "historical_packet_evidence" in planner_skill
    assert "不得指导执行器使用 `report-provided jwt-token`" in planner_skill
    assert "不得写成类似 “发送消息并验证请求与响应” 的单一步骤" in planner_skill
    assert "不得把 `browser_action(action=\"execute_js\")` 作为默认规划动作" in planner_skill
    assert "planner 应尽量把执行当前步骤真正需要的关键字段直接保留在计划中" in planner_skill
    assert "不得把执行器设计成依赖二次回看原始报告" in planner_skill

    executor_skill = loaded["repro_plan_executor"]
    assert "你不是 analyzer，也不是 planner" in executor_skill
    assert "## 1) Execution Todo" in executor_skill
    assert "先创建一份简短、原子化、可执行的 `/src` 专用步骤合同" in executor_skill
    assert "你必须先调用 `create_src_repro_plan`" in executor_skill
    assert "`create_src_repro_plan` 成功返回后" in executor_skill
    assert "`send_request`" in executor_skill
    assert "`update_src_repro_plan_step`" in executor_skill
    assert "`get_src_repro_plan`" in executor_skill
    assert "不得在 `/src` reproducer 中使用通用 `todo` 工具" in executor_skill
    assert "`browser_action(action=\"execute_js\")` 边界" in executor_skill
    assert "不得在执行过程中二次回看文件版原始报告" in executor_skill
    assert "不得创建任何“缺口解析”子 agent" in executor_skill
    assert "如果决定性验证步骤从未真正完成，不能判 `not reproducible`，只能判 `blocked`" in executor_skill
    assert "对 `ui_navigation + packet_replay` 联合场景，默认至少拆成 3 步" in executor_skill
    assert "严禁把“发送请求 + 验证响应 + 验证页面执行”合并成一个步骤" in executor_skill
    assert "## 三层规则" in executor_skill
    assert "### 第一层：验证节点骨架" in executor_skill
    assert "`entry_or_reachability`" in executor_skill
    assert "`transport_request`" in executor_skill
    assert "`render_or_trigger`" in executor_skill
    assert "### 第二层：漏洞族覆盖规则" in executor_skill
    assert "#### stored_xss_or_stored_injection" in executor_skill
    assert "#### authz_or_idor_or_logic_bypass" in executor_skill
    assert "#### ssrf_or_blind_oob" in executor_skill
    assert "### 第三层：统一 verdict 闸门" in executor_skill
    assert "`success_judgment`" in executor_skill
    assert "`negative_judgment`" in executor_skill
    assert "`blocked_judgment`" in executor_skill
    assert "对所有决定性验证步骤" in executor_skill
    assert "## 步骤 judgment 语义" in executor_skill
    assert "一个决定性验证节点只对应一个步骤" in executor_skill
    assert "judgment 只能评价当前步骤对应的那个节点，不得跨步评价后续节点" in executor_skill
    assert "不得在“请求发送”步骤里写“服务器响应异常”这类属于响应节点的 judgment" in executor_skill
    assert "不得在“响应验证”步骤里写“页面未弹窗”这类属于页面执行节点的 judgment" in executor_skill
    assert "不得在单个步骤的 `stop_rule` 中直接写出最终 verdict" in executor_skill
    assert "不得把“未捕获到请求”和“已捕获请求但 payload 被过滤/改写”写进同一个 judgment" in executor_skill
    assert "本地信号不等于目标侧证据" in executor_skill
    assert "payload 只是出现在输入框、textarea、contenteditable 或本地 DOM 中" in executor_skill
    assert "如果你只有“本地信号”，而没有任何目标侧证据，则最终 verdict 不得为 `reproducible`" in executor_skill
    assert "不得机械地把 `send_request` / `repeat_request` 作为所有联合场景的第一步" in executor_skill
    assert "则默认优先走“UI 进入 -> 生成当前会话中的真实请求 -> 再看是否需要重放”的路径" in executor_skill
    assert "则不得先做“裸 `send_request` 放包”作为主路线" in executor_skill
    assert "如果一个分支只是被代理层、中间层或工具层阻断" in executor_skill
    assert "收到代理生成的错误页、Caido 错误页" in executor_skill
    assert "`done` 不等于“工具调用结束了”" in executor_skill
    assert "收到 Caido/proxy error page，尚未确认请求到达目标" in executor_skill
    assert "则应回到报告已给出的 UI 路径继续尝试" in executor_skill
    assert "不得用“虽然没看到弹窗，但应该已经成功”这种推断替代真实 verdict" in executor_skill
