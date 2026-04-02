import contextlib
import json
import os
import re
from pathlib import Path
from typing import Any


STRIX_API_BASE = "https://models.strix.ai/api/v1"
_DOTENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Config:
    """Configuration Manager for Strix."""

    # LLM Configuration
    strix_llm = None
    llm_api_key = None
    llm_api_base = None
    openai_api_base = None
    litellm_base_url = None
    ollama_api_base = None
    strix_reasoning_effort = "high"
    strix_llm_max_retries = "5"
    strix_memory_compressor_timeout = "30"
    llm_timeout = "300"
    _LLM_CANONICAL_NAMES = (
        "strix_llm",
        "llm_api_key",
        "llm_api_base",
        "openai_api_base",
        "litellm_base_url",
        "ollama_api_base",
        "strix_reasoning_effort",
        "strix_llm_max_retries",
        "strix_memory_compressor_timeout",
        "llm_timeout",
    )

    # Tool & Feature Configuration
    perplexity_api_key = None
    strix_disable_browser = "false"

    # Runtime Configuration
    strix_image = "ghcr.io/usestrix/strix-sandbox:0.1.13"
    strix_runtime_backend = "docker"
    strix_sandbox_execution_timeout = "120"
    strix_sandbox_connect_timeout = "10"
    strix_src_child_agent_timeout = None

    # Telemetry
    strix_telemetry = "1"
    strix_otel_telemetry = None
    strix_posthog_telemetry = None
    traceloop_base_url = None
    traceloop_api_key = None
    traceloop_headers = None

    # Config file override (set via --config CLI arg)
    _config_file_override: Path | None = None

    @classmethod
    def _tracked_names(cls) -> list[str]:
        return [
            k
            for k, v in vars(cls).items()
            if not k.startswith("_") and k[0].islower() and (v is None or isinstance(v, str))
        ]

    @classmethod
    def tracked_vars(cls) -> list[str]:
        return [name.upper() for name in cls._tracked_names()]

    @classmethod
    def _llm_env_vars(cls) -> set[str]:
        return {name.upper() for name in cls._LLM_CANONICAL_NAMES}

    @classmethod
    def _llm_env_changed(cls, saved_env: dict[str, Any]) -> bool:
        for var_name in cls._llm_env_vars():
            current = os.getenv(var_name)
            if current is None:
                continue
            if saved_env.get(var_name) != current:
                return True
        return False

    @classmethod
    def get(cls, name: str) -> str | None:
        env_name = name.upper()
        default = getattr(cls, name, None)
        return os.getenv(env_name, default)

    @classmethod
    def config_dir(cls) -> Path:
        return Path.home() / ".strix"

    @classmethod
    def config_file(cls) -> Path:
        if cls._config_file_override is not None:
            return cls._config_file_override
        return cls.config_dir() / "cli-config.json"

    @classmethod
    def load(cls) -> dict[str, Any]:
        path = cls.config_file()
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                return data
        except (json.JSONDecodeError, OSError):
            return {}

    @classmethod
    def save(cls, config: dict[str, Any]) -> bool:
        try:
            cls.config_dir().mkdir(parents=True, exist_ok=True)
            config_path = cls.config_dir() / "cli-config.json"
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except OSError:
            return False
        with contextlib.suppress(OSError):
            config_path.chmod(0o600)  # may fail on Windows
        return True

    @classmethod
    def apply_saved(cls, force: bool = False) -> dict[str, str]:
        saved = cls.load()
        env_vars = saved.get("env", {})
        if not isinstance(env_vars, dict):
            env_vars = {}
        cleared_vars = {
            var_name
            for var_name in cls.tracked_vars()
            if var_name in os.environ and os.environ.get(var_name) == ""
        }
        if cleared_vars:
            for var_name in cleared_vars:
                env_vars.pop(var_name, None)
            if cls._config_file_override is None:
                cls.save({"env": env_vars})
        if cls._llm_env_changed(env_vars):
            for var_name in cls._llm_env_vars():
                env_vars.pop(var_name, None)
            if cls._config_file_override is None:
                cls.save({"env": env_vars})
        applied = {}

        for var_name, var_value in env_vars.items():
            if var_name in cls.tracked_vars() and (force or var_name not in os.environ):
                os.environ[var_name] = var_value
                applied[var_name] = var_value

        return applied

    @classmethod
    def capture_current(cls) -> dict[str, Any]:
        env_vars = {}
        for var_name in cls.tracked_vars():
            value = os.getenv(var_name)
            if value:
                env_vars[var_name] = value
        return {"env": env_vars}

    @classmethod
    def save_current(cls) -> bool:
        existing = cls.load().get("env", {})
        merged = dict(existing)

        for var_name in cls.tracked_vars():
            value = os.getenv(var_name)
            if value is None:
                pass
            elif value == "":
                merged.pop(var_name, None)
            else:
                merged[var_name] = value

        return cls.save({"env": merged})


def apply_saved_config(force: bool = False) -> dict[str, str]:
    return Config.apply_saved(force=force)


def save_current_config() -> bool:
    return Config.save_current()


def find_dotenv_file(start: Path | None = None, filename: str = ".env") -> Path | None:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for directory in (current, *current.parents):
        candidate = directory / filename
        if candidate.is_file():
            return candidate

    return None


def load_dotenv_file(path: Path | None = None, *, override: bool = False) -> Path | None:
    dotenv_path = path.resolve() if path is not None else find_dotenv_file()
    if dotenv_path is None or not dotenv_path.is_file():
        return None

    content = dotenv_path.read_text(encoding="utf-8-sig")
    for raw_line in content.splitlines():
        parsed = _parse_dotenv_line(raw_line)
        if parsed is None:
            continue

        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value

    return dotenv_path


def resolve_llm_config() -> tuple[str | None, str | None, str | None]:
    """Resolve LLM model, api_key, and api_base based on STRIX_LLM prefix.

    Returns:
        tuple: (model_name, api_key, api_base)
        - model_name: Original model name (strix/ prefix preserved for display)
        - api_key: LLM API key
        - api_base: API base URL (auto-set to STRIX_API_BASE for strix/ models)
    """
    model = Config.get("strix_llm")
    if not model:
        return None, None, None

    api_key = Config.get("llm_api_key")

    if model.startswith("strix/"):
        api_base: str | None = STRIX_API_BASE
    else:
        api_base = (
            Config.get("llm_api_base")
            or Config.get("openai_api_base")
            or Config.get("litellm_base_url")
            or Config.get("ollama_api_base")
        )

    return model, api_key, api_base


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[7:].lstrip()

    if "=" not in stripped:
        return None

    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    if not _DOTENV_KEY_PATTERN.match(key):
        return None

    return key, _parse_dotenv_value(raw_value.strip())


def _parse_dotenv_value(value: str) -> str:
    if not value:
        return ""

    if value[0] in {'"', "'"}:
        return _parse_quoted_dotenv_value(value)

    return _strip_unquoted_dotenv_comment(value)


def _parse_quoted_dotenv_value(value: str) -> str:
    quote = value[0]
    chars: list[str] = []
    index = 1

    while index < len(value):
        char = value[index]
        if char == quote:
            return "".join(chars)

        if quote == '"' and char == "\\":
            index += 1
            if index >= len(value):
                chars.append("\\")
                break
            chars.append(_decode_dotenv_escape(value[index]))
            index += 1
            continue

        chars.append(char)
        index += 1

    return value


def _decode_dotenv_escape(char: str) -> str:
    escapes = {
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "\\": "\\",
        '"': '"',
    }
    return escapes.get(char, char)


def _strip_unquoted_dotenv_comment(value: str) -> str:
    for index, char in enumerate(value):
        if char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.rstrip()
