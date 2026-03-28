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
