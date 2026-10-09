from typing import Any

import yaml


def load_scenario(path: str) -> dict[str, Any]:
    with open(path) as f:
        d: dict[str, Any] = yaml.safe_load(f)
    validate_scenario(d)
    return d


def validate_scenario(d: dict[str, Any]) -> None:
    for k in ("endpoint", "model", "concurrency", "duration"):
        if k not in d:
            raise ValueError(f"scenario missing '{k}'")
