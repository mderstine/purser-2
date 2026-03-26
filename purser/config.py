"""Configuration management for Purser."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel

from purser.models import AdapterConfig


class PurserConfig(BaseModel):
    adapter: AdapterConfig = AdapterConfig()
    specs_dir: Path = Path("specs")
    formulas_dir: Path = Path("formulas")
    memory_db: Path = Path(".purser/memory.duckdb")
    max_agent_iterations: int = 50


def load_config(project_dir: Path | None = None) -> PurserConfig:
    """Load config from purser.toml + environment variables."""
    root = project_dir or Path.cwd()
    config_data: dict = {}

    # Read config file
    for name in ("purser.toml", ".purser/config.toml"):
        cfg_path = root / name
        if cfg_path.exists():
            with open(cfg_path, "rb") as f:
                config_data = tomllib.load(f)
            break

    # Also check global config
    global_cfg = Path.home() / ".config" / "purser" / "config.toml"
    if global_cfg.exists() and not config_data:
        with open(global_cfg, "rb") as f:
            config_data = tomllib.load(f)

    # Build adapter config from file + env
    adapter_data = config_data.get("adapter", {})
    env_map = {
        "PURSER_ADAPTER": "provider",
        "PURSER_MODEL": "model",
        "PURSER_API_KEY": "api_key",
        "PURSER_BASE_URL": "base_url",
    }
    for env_key, field in env_map.items():
        val = os.environ.get(env_key)
        if val:
            adapter_data[field] = val

    config_data["adapter"] = adapter_data

    return PurserConfig.model_validate(config_data)
