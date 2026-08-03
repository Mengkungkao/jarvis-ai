import os
from pathlib import Path

import yaml


def load_config(root: Path):
    config_path = root / "config" / "config.yaml"
    secrets_path = root / "config" / "secrets.env"
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    if secrets_path.exists():
        for line in secrets_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

    return config
