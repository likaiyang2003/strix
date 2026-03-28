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
    assert "analyzer -> planner -> reproducer" in loaded["src_repro_root"]
    assert '"can_reproduce"' in loaded["report_repro_analyzer"]
    assert "historical_packet_evidence" in loaded["report_repro_analyzer"]
    assert "post_exploitation_result" in loaded["report_repro_analyzer"]
    assert "Authorization: bearer null" in loaded["report_repro_analyzer"]
    assert "Detailed Reproduction Steps" in loaded["report_to_repro_checklist"]
    assert "Do not place `historical_packet_evidence` in `## Preconditions`" in loaded["report_to_repro_checklist"]
    assert "Do not instruct the executor to use `report-provided jwt-token`" in loaded["report_to_repro_checklist"]
    assert "Final Verdict" in loaded["repro_plan_executor"]
    assert "Decisive Validation Rules" in loaded["repro_plan_executor"]
    assert "Synthetic or intermediary failures are not target-side evidence" in loaded["repro_plan_executor"]
