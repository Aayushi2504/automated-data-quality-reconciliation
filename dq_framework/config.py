from pathlib import Path

import yaml
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_engines(conn_cfg: dict) -> dict:
    return {name: create_engine(url) for name, url in conn_cfg["connections"].items()}
