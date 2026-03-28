from typing import Any


def main(*args: Any, **kwargs: Any) -> Any:
    from .main import main as _main

    return _main(*args, **kwargs)


__all__ = ["main"]
