"""Agent identity and configuration management."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str

    @classmethod
    def config_dir(cls) -> Path:
        """Get the gastown config directory."""
        return Path.home() / ".gastown"

    @classmethod
    def config_path(cls) -> Path:
        """Get the path to the agent config file."""
        return cls.config_dir() / "config.yaml"

    @classmethod
    def load(cls) -> Optional["AgentConfig"]:
        """Load agent config from disk. Returns None if not configured."""
        config_path = cls.config_path()
        if not config_path.exists():
            return None

        with open(config_path) as f:
            data = yaml.safe_load(f)

        return cls(name=data["name"])

    def save(self) -> None:
        """Save agent config to disk."""
        config_dir = self.config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)

        with open(self.config_path(), "w") as f:
            yaml.dump({"name": self.name}, f)

    @classmethod
    def require(cls) -> "AgentConfig":
        """Load agent config, raising an error if not configured."""
        config = cls.load()
        if config is None:
            raise RuntimeError(
                "Agent not initialized. Run 'gastown init <name>' first."
            )
        return config


def get_agent_name() -> str:
    """Get the current agent's name."""
    return AgentConfig.require().name
