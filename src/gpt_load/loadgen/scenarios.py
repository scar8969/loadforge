import yaml

def load_scenario(path: str) -> dict:
    with open(path) as f:
        d = yaml.safe_load(f)
    validate_scenario(d)
    return d

def validate_scenario(d: dict) -> None:
    for k in ("endpoint", "model", "concurrency", "duration"):
        if k not in d:
            raise ValueError(f"scenario missing '{k}'")
