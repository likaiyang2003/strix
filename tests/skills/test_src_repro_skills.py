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
    assert "报告驱动复现" in loaded["src_repro_root"]
    assert '"can_reproduce"' in loaded["report_repro_analyzer"]
    assert "historical_packet_evidence" in loaded["report_repro_analyzer"]
    assert "post_exploitation_result" in loaded["report_repro_analyzer"]
    assert "Authorization: bearer null" in loaded["report_repro_analyzer"]
    assert "所有自然语言输出都必须使用中文" in loaded["report_repro_analyzer"]
    assert "缺少可用的认证令牌或会话 cookie" in loaded["report_repro_analyzer"]
    assert "缺少当前可用登录态获取方式" in loaded["report_repro_analyzer"]
    assert "ordinary_authenticated_session_required" in loaded["report_repro_analyzer"]
    assert "special_role_or_special_account_required" in loaded["report_repro_analyzer"]
    assert "specific_report_secret_required_now" in loaded["report_repro_analyzer"]
    assert "缺少一步一步的登录教程，本身不应直接视为阻塞" in loaded["report_repro_analyzer"]
    assert "Replay-First 充分性" in loaded["report_repro_analyzer"]
    assert "需要测试者自备普通有效登录态" in loaded["report_to_repro_checklist"]
    assert "Detailed Reproduction Steps" in loaded["report_to_repro_checklist"]
    assert "Suggested Action / Invocation" in loaded["report_to_repro_checklist"]
    assert "Required Inputs" in loaded["report_to_repro_checklist"]
    assert "Evidence Type" in loaded["report_to_repro_checklist"]
    assert "Stop / Failure Rule" in loaded["report_to_repro_checklist"]
    assert "historical_packet_evidence" in loaded["report_to_repro_checklist"]
    assert "不得指导执行器使用 `report-provided jwt-token`" in loaded["report_to_repro_checklist"]
    assert "不得写成类似 “发送消息并验证请求与响应” 的单一步骤" in loaded["report_to_repro_checklist"]
    assert "不得把 `browser_action(action=\"execute_js\")` 作为默认规划动作" in loaded["report_to_repro_checklist"]
    assert "planner 应尽量把执行当前步骤真正需要的关键字段直接保留在计划中" in loaded["report_to_repro_checklist"]
    assert "最终输出结构" in loaded["repro_plan_executor"]
    assert "决定性验证规则" in loaded["repro_plan_executor"]
    assert "中间层或合成错误不能当作目标侧证据" in loaded["repro_plan_executor"]
    assert "Suggested Action / Invocation" in loaded["repro_plan_executor"]
    assert "每一步都应被视为一个有界合同" in loaded["repro_plan_executor"]
    assert "不得静默替换成同一工具族中的其他动作" in loaded["repro_plan_executor"]
    assert "浏览器 DOM 中存在 payload，并不能替代一个计划中的“请求检查”或“重放检查”步骤" in loaded["repro_plan_executor"]
    assert "连续两次或以上探索性 `execute_js` 调用" in loaded["repro_plan_executor"]
    assert "如果你因为计划约束而拒绝使用 `execute_js`" in loaded["repro_plan_executor"]
    assert "不得在开局阶段重新通读原始漏洞报告" in loaded["repro_plan_executor"]
    assert "必须优先使用 `load_src_report_source`" in loaded["repro_plan_executor"]
