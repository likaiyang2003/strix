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
