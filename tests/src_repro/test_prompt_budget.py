from strix.src_repro import (
    build_budgeted_prompt,
    trim_for_reproduction,
    trim_plan_for_reproduction,
)


def test_trim_reduces_oversized_cookie_and_keeps_core_fields() -> None:
    oversized_cookie = "jwt-token=" + ("x" * 3000)
    text = "\n".join(
        [
            "URL: https://target.local/login",
            "Account: admin",
            "Password: Password123!",
            "payload: <script>alert(1)</script>",
            f"Cookie: {oversized_cookie}",
            "Step: log in and submit the payload, then observe the alert.",
        ]
    )

    trimmed = trim_for_reproduction(text, max_chars=700)

    assert len(trimmed) <= 700
    assert "https://target.local/login" in trimmed
    assert "Account: admin" in trimmed
    assert "<script>alert(1)</script>" in trimmed
    assert "Cookie:" in trimmed
    assert oversized_cookie not in trimmed


def test_build_budgeted_prompt_respects_max_chars() -> None:
    template = "Report:\n{text}\n\nPlan:\n{plan}"
    text = "A" * 2000
    plan = "B" * 2000

    prompt = build_budgeted_prompt(
        template,
        text=text,
        plan=plan,
        max_chars=600,
    )

    assert len(prompt) <= 600
    assert "Report:" in prompt
    assert "Plan:" in prompt


def test_trim_plan_for_reproduction_preserves_success_criteria_tail_section() -> None:
    plan = "\n".join(
        [
            "## Extracted Facts",
            "- Target: demo",
            "## Detailed Reproduction Steps",
            "1. Open the page and inspect the flow " + ("A" * 600),
            "2. Click the action and inspect the response " + ("B" * 600),
            "3. Visit the detail page and verify the leak " + ("C" * 600),
            "## Success Criteria",
            "- Success Marker: admin credentials are visible in the page response",
            "- Stop Conditions: finish the review and stop if no admin credentials appear",
        ]
    )

    trimmed = trim_plan_for_reproduction(plan, max_chars=900)

    assert len(trimmed) <= 900
    assert "## Success Criteria" in trimmed
    assert "Success Marker" in trimmed
    assert "Stop Conditions" in trimmed


def test_trim_plan_for_reproduction_prioritizes_all_steps_before_facts_and_preconditions() -> None:
    plan = "\n".join(
        [
            "## Extracted Facts",
            "- Target System: demo " + ("A" * 500),
            "## Preconditions",
            "- Environment: login required " + ("B" * 500),
            "## Detailed Reproduction Steps",
            "1. Open the homepage",
            "2. Enter the chat page",
            "3. Input the XSS payload",
            "4. Submit the message",
            "5. Validate the execution result",
            "## Success Criteria",
            "- Success Marker: alert pops up and shows cookie info",
            "- Stop Conditions: stop after step 5 if the marker is absent",
            "## Evidence Checklist",
            "- Screenshot of popup",
        ]
    )

    trimmed = trim_plan_for_reproduction(plan, max_chars=700)

    assert len(trimmed) <= 700
    assert "## Detailed Reproduction Steps" in trimmed
    assert "1. Open the homepage" in trimmed
    assert "5. Validate the execution result" in trimmed
    assert "## Success Criteria" in trimmed
    assert "## Extracted Facts" not in trimmed
    assert "## Preconditions" not in trimmed


def test_trim_plan_for_reproduction_keeps_steps_when_step_section_itself_exceeds_budget() -> None:
    plan = "\n".join(
        [
            "## Detailed Reproduction Steps",
            "1. " + ("A" * 900),
            "2. " + ("B" * 900),
            "3. " + ("C" * 900),
            "## Success Criteria",
            "- Success Marker: alert pops up and shows cookie information",
            "- Stop Conditions: stop immediately after the final validation step",
        ]
    )

    trimmed = trim_plan_for_reproduction(plan, max_chars=900)

    assert len(trimmed) <= 900
    assert "## Detailed Reproduction Steps" in trimmed
    assert "## Success Criteria" in trimmed
    assert "1. " in trimmed
