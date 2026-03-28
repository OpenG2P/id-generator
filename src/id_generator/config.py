"""
Configuration management.

Loads settings from YAML config file with environment variable overrides.
"""

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class NamespaceConfig(BaseModel):
    """Configuration for a single namespace."""

    id_length: int = Field(ge=2, le=32, description="ID length (2-32 digits)")


class IdGeneratorConfig(BaseModel):
    """Core ID generator configuration."""

    # Filter rules
    sequence_limit: int = 3
    repeating_limit: int = 2
    repeating_block_limit: int = 2
    conjugative_even_digits_limit: int = 3
    digits_group_limit: int = 5
    reverse_digits_group_limit: int = 5
    not_start_with: list[str] = ["0", "1"]
    restricted_numbers: list[str] = []

    # Pool management
    pool_min_threshold: int = 1000
    pool_generation_batch_size: int = 5000
    pool_check_interval_seconds: int = 30
    exhaustion_max_attempts: int = 1000
    sub_batch_size: int = 10000

    # Namespaces
    namespaces: dict[str, NamespaceConfig] = {}

    def get_filter_config(self) -> dict:
        """Return filter parameters as a plain dict for the filter functions."""
        return {
            "sequence_limit": self.sequence_limit,
            "repeating_limit": self.repeating_limit,
            "repeating_block_limit": self.repeating_block_limit,
            "conjugative_even_digits_limit": self.conjugative_even_digits_limit,
            "digits_group_limit": self.digits_group_limit,
            "reverse_digits_group_limit": self.reverse_digits_group_limit,
            "not_start_with": self.not_start_with,
            "restricted_numbers": self.restricted_numbers,
        }


class Settings(BaseSettings):
    """Top-level settings."""

    id_generator: IdGeneratorConfig = IdGeneratorConfig()

    model_config = {"env_nested_delimiter": "__"}


def _find_config_path() -> Path:
    """Resolve the YAML config file path."""
    config_path = os.environ.get("CONFIG_PATH", None)
    if config_path:
        return Path(config_path)

    # Default: config/default.yaml relative to working directory
    cwd_config = Path.cwd() / "config" / "default.yaml"
    if cwd_config.exists():
        return cwd_config

    # Try relative to this source file (for installed packages)
    src_config = Path(__file__).parent.parent.parent / "config" / "default.yaml"
    if src_config.exists():
        return src_config

    raise FileNotFoundError(
        "Config file not found. Set CONFIG_PATH env var or place "
        "config/default.yaml in the working directory."
    )


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings from YAML + environment overrides."""
    config_path = _find_config_path()

    with open(config_path) as f:
        yaml_data = yaml.safe_load(f)

    if yaml_data is None:
        yaml_data = {}

    return Settings(**yaml_data)
