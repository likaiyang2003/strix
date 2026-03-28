import pytest

from strix.src_repro import SrcReproAnalysis, parse_analysis


def test_parse_analysis_reads_json_with_true_flag() -> None:
    raw_text = (
        '{"can_reproduce": true, '
        '"reason": "PoC steps are complete", '
        '"missing_info": ["target version"]}'
    )

    result = parse_analysis(raw_text)

    assert isinstance(result, SrcReproAnalysis)
    assert result.can_reproduce is True
    assert result.reason == "PoC steps are complete"
    assert result.missing_info == ["target version"]


def test_parse_analysis_supports_fenced_json_payload() -> None:
    raw_text = """```json
{"can_reproduce": false, "missing_info": []}
```"""

    result = parse_analysis(raw_text)

    assert result.can_reproduce is False
    assert result.reason == "No reason provided"
    assert result.missing_info == []


def test_parse_analysis_falls_back_for_plain_text() -> None:
    raw_text = "Assessment: not enough information, cannot reproduce now."

    result = parse_analysis(raw_text)

    assert result.can_reproduce is False
    assert result.reason == "Assessment: not enough information, cannot reproduce now."
    assert result.missing_info == []


def test_parse_analysis_infers_missing_info_from_plain_text() -> None:
    raw_text = "missing: target-version, api endpoint"

    result = parse_analysis(raw_text)

    assert result.can_reproduce is False
    assert result.missing_info == ["target-version", "api endpoint"]


def test_parse_analysis_respects_explicit_false_from_json() -> None:
    raw_text = (
        '{"can_reproduce": false, '
        '"reason": "Missing API endpoint details", '
        '"missing_info": ["api endpoint", "http method"]}'
    )

    result = parse_analysis(raw_text)

    assert result.can_reproduce is False
    assert result.reason == "Missing API endpoint details"
    assert result.missing_info == ["api endpoint", "http method"]


def test_parse_analysis_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="raw_text cannot be empty"):
        parse_analysis("   ")
