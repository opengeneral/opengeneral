from __future__ import annotations

from pathlib import Path

from opengeneral.config import AgentConfig, AgentsConfig, KeyConfig, KeysConfig


def test_key_config_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "keys.json"
    KeysConfig(
        {
            "personal-anthropic": KeyConfig(
                "personal-anthropic",
                "anthropic",
            ),
            "work-openai": KeyConfig(
                "work-openai",
                "openai",
                base_url="https://gateway.example.com/v1",
            ),
        }
    ).write(path)

    config = KeysConfig.from_path(path)

    assert config.keys["personal-anthropic"].provider_type == "anthropic"
    assert config.keys["work-openai"].base_url == "https://gateway.example.com/v1"


def test_keys_config_for_provider_filters_by_type(tmp_path: Path) -> None:
    config = KeysConfig(
        {
            "a": KeyConfig("a", "anthropic"),
            "b": KeyConfig("b", "openai"),
            "c": KeyConfig("c", "anthropic"),
        }
    )

    anthropic_keys = config.for_provider("anthropic")

    assert {key.name for key in anthropic_keys} == {"a", "c"}


def test_agent_config_round_trips_key_and_model(tmp_path: Path) -> None:
    path = tmp_path / "agents.json"
    AgentsConfig(
        {
            "coder": AgentConfig(
                "coder",
                "coder-abc123",
                "coder",
                "default",
                "personal-anthropic",
                "anthropic/claude-opus-4-7",
            )
        }
    ).write(path)

    config = AgentsConfig.from_path(path)

    assert config.agents["coder"].key == "personal-anthropic"
    assert config.agents["coder"].model == "anthropic/claude-opus-4-7"
