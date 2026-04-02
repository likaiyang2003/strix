from strix.skills import get_available_skills, load_skills


def test_src_report_skills_are_listed_in_available_skills() -> None:
    available = get_available_skills()

    assert "src_report" in available
    assert "report_repro_analyzer" in available["src_report"]
    assert "report_to_repro_checklist" in available["src_report"]
    assert "repro_plan_executor" in available["src_report"]
    assert "verify_plan_executor" in available["src_report"]


def test_load_skills_can_load_src_root_skills_and_src_report_skills() -> None:
    loaded = load_skills(
        [
            "src_repro_root",
            "src_verify_root",
            "report_repro_analyzer",
            "report_to_repro_checklist",
            "repro_plan_executor",
            "verify_plan_executor",
        ]
    )

    assert "src_repro_root" in loaded
    assert "src_verify_root" in loaded
    assert "report_repro_analyzer" in loaded
    assert "report_to_repro_checklist" in loaded
    assert "repro_plan_executor" in loaded
    assert "verify_plan_executor" in loaded

    root_skill = loaded["src_repro_root"]
    assert "analyzer -> reproducer" in root_skill
    assert "report_to_repro_checklist" in root_skill

    verify_root_skill = loaded["src_verify_root"]
    assert "/src verify" in verify_root_skill
    assert "SRC Verify Executor" in verify_root_skill
    assert "verify_plan_executor" in verify_root_skill

    analyzer_skill = loaded["report_repro_analyzer"]
    assert '"can_reproduce"' in analyzer_skill
    assert "historical_packet_evidence" in analyzer_skill
    assert "post_exploitation_result" in analyzer_skill
    assert "Authorization: bearer null" in analyzer_skill

    planner_skill = loaded["report_to_repro_checklist"]
    assert "Detailed Reproduction Steps" in planner_skill
    assert "Suggested Action / Invocation" in planner_skill
    assert "Required Inputs" in planner_skill
    assert "Evidence Type" in planner_skill
    assert "Stop / Failure Rule" in planner_skill

    executor_skill = loaded["repro_plan_executor"]
    assert "## 1) Execution Todo" in executor_skill
    assert "`create_src_plan`" in executor_skill
    assert "`update_src_plan_step`" in executor_skill
    assert "`get_src_plan`" in executor_skill
    assert "`success_judgment`" in executor_skill
    assert "`negative_judgment`" in executor_skill
    assert "`blocked_judgment`" in executor_skill
    assert "`browser_action(action=\"execute_js\")`" in executor_skill
    assert "ui_navigation + packet_replay" in executor_skill
    assert "stored_xss_or_stored_injection" in executor_skill
    assert "authz_or_idor_or_logic_bypass" in executor_skill
    assert "ssrf_or_blind_oob" in executor_skill

    verify_executor_skill = loaded["verify_plan_executor"]
    assert "/src verify" in verify_executor_skill
    assert "`still reproducible`" in verify_executor_skill
    assert "`fixed`" in verify_executor_skill
    assert "`blocked`" in verify_executor_skill
    assert "comparability" in verify_executor_skill
    assert "secure_behavior" in verify_executor_skill
    assert "## 2) Verification Execution Notes" in verify_executor_skill
    assert "`create_src_plan`" in verify_executor_skill
    assert "不得把修复后验证变成“修复后绕过挖掘”" in verify_executor_skill
    assert "不得把“这次没打出来”直接判成 `fixed`" in verify_executor_skill
