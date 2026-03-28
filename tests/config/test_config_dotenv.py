import os

from strix.config.config import find_dotenv_file, load_dotenv_file


def test_load_dotenv_file_populates_env_without_overriding_existing(monkeypatch, tmp_path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "STRIX_LLM=openai/gpt-5.4",
                "LLM_API_KEY=dotenv-key",
                "LLM_API_BASE=http://127.0.0.1:11434/v1",
                'STRIX_REASONING_EFFORT="medium"',
                "export EXTRA_VALUE=from-dotenv",
                "COMMENTED_VALUE=kept # trailing comment",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("STRIX_LLM", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "existing-key")
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("STRIX_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("EXTRA_VALUE", raising=False)
    monkeypatch.delenv("COMMENTED_VALUE", raising=False)

    loaded = load_dotenv_file(dotenv_path)

    assert loaded == dotenv_path
    assert os.environ["STRIX_LLM"] == "openai/gpt-5.4"
    assert os.environ["LLM_API_KEY"] == "existing-key"
    assert os.environ["LLM_API_BASE"] == "http://127.0.0.1:11434/v1"
    assert os.environ["STRIX_REASONING_EFFORT"] == "medium"
    assert os.environ["EXTRA_VALUE"] == "from-dotenv"
    assert os.environ["COMMENTED_VALUE"] == "kept"


def test_find_dotenv_file_searches_parent_directories(tmp_path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("STRIX_LLM=openai/gpt-5.4\n", encoding="utf-8")
    nested_dir = tmp_path / "a" / "b" / "c"
    nested_dir.mkdir(parents=True)

    found = find_dotenv_file(nested_dir)

    assert found == dotenv_path


def test_load_dotenv_file_returns_none_when_missing(tmp_path) -> None:
    assert load_dotenv_file(tmp_path / ".env") is None
