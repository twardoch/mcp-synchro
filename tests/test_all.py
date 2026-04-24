# this_file: tests/test_all.py
"""The proving grounds. We break things here so they don\'t break on your machine."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError  # noqa: F401 - used in type annotations

from mcp_synchro.agents import (
    AgentDef,
    DiscoveredAgent,
    get_builtin_agents_path,
    load_all_agent_defs,
    parse_agent_defs,
)
from mcp_synchro.config import load_sot, save_sot
from mcp_synchro.models import (
    McpServer,
    McpServersConfig,
    _camel_to_snake,
    _snake_to_camel,
)
from mcp_synchro.readers import (
    extract_mcp_servers,
    read_agent_config,
    read_json,
    read_toml,
)
from mcp_synchro.writers import (
    update_mcp_servers,
    write_agent_config,
    write_json,
    write_toml,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(
    id: str = "t",
    name: str = "T",
    config_format: str = "json",
    mcp_key: str = "mcpServers",
    paths: dict | None = None,
    mcp_wrapper_key: str | None = None,
) -> AgentDef:
    """A factory that spits out dummy AgentDefs for testing."""
    return AgentDef(
        id=id,
        name=name,
        description="",
        config_format=config_format,
        mcp_key=mcp_key,
        paths=paths or {},
        mcp_wrapper_key=mcp_wrapper_key,
    )


def _make_agent_config_file(
    tmp_path: Path,
    filename: str,
    servers: dict,
    mcp_key: str = "mcpServers",
    extra: dict | None = None,
) -> Path:
    """Drops a fake agent config file onto the disk."""
    data = {mcp_key: servers}
    if extra:
        data.update(extra)
    f = tmp_path / filename
    f.write_text(json.dumps(data))
    return f


# ===========================================================================
# Models
# ===========================================================================


class TestCamelSnakeConversion:
    """Tests for _camel_to_snake and _snake_to_camel utility functions."""

    def test_camel_to_snake_when_simple_then_converted(self):
        assert _camel_to_snake("mcpServers") == "mcp_servers"

    def test_camel_to_snake_when_already_snake_then_unchanged(self):
        assert _camel_to_snake("mcp_servers") == "mcp_servers"

    def test_camel_to_snake_when_all_lowercase_then_unchanged(self):
        assert _camel_to_snake("command") == "command"

    def test_camel_to_snake_when_multiple_capitals_then_all_split(self):
        assert _camel_to_snake("bearerTokenEnvVar") == "bearer_token_env_var"

    def test_camel_to_snake_when_single_char_parts_then_correct(self):
        assert _camel_to_snake("aB") == "a_b"

    def test_snake_to_camel_when_simple_then_converted(self):
        assert _snake_to_camel("mcp_servers") == "mcpServers"

    def test_snake_to_camel_when_no_underscore_then_unchanged(self):
        assert _snake_to_camel("command") == "command"

    def test_snake_to_camel_when_multiple_parts_then_all_capitalized(self):
        assert _snake_to_camel("bearer_token_env_var") == "bearerTokenEnvVar"

    def test_snake_to_camel_when_single_part_then_unchanged(self):
        assert _snake_to_camel("url") == "url"

    def test_roundtrip_camel_to_snake_to_camel(self):
        original = "alwaysAllow"
        assert _snake_to_camel(_camel_to_snake(original)) == original

    def test_roundtrip_snake_to_camel_to_snake(self):
        original = "always_allow"
        assert _camel_to_snake(_snake_to_camel(original)) == original


class TestMcpServer:
    """Tests for the McpServer Pydantic model."""

    def test_create_when_stdio_then_fields_set(self):
        server = McpServer(command="npx", args=["-y", "@test/server"])
        assert server.command == "npx"
        assert server.args == ["-y", "@test/server"]
        assert server.url is None

    def test_create_when_url_then_fields_set(self):
        server = McpServer(url="http://localhost:8080")
        assert server.url == "http://localhost:8080"
        assert server.command is None

    def test_create_when_no_command_or_url_then_permissive(self):
        """Validation is permissive since some agents store command differently."""
        server = McpServer()
        assert server.command is None
        assert server.url is None

    def test_create_when_both_command_and_url_then_valid(self):
        server = McpServer(command="npx", url="http://localhost:8080")
        assert server.command == "npx"
        assert server.url == "http://localhost:8080"

    def test_args_when_string_then_converted_to_list(self):
        server = McpServer(command="test", args="single-arg")
        assert server.args == ["single-arg"]

    def test_args_when_none_then_stays_none(self):
        server = McpServer(command="test")
        assert server.args is None

    def test_args_when_integers_then_converted_to_strings(self):
        server = McpServer(command="test", args=[1, 2, 3])
        assert server.args == ["1", "2", "3"]

    def test_is_disabled_when_disabled_true_then_true(self):
        server = McpServer(command="test", disabled=True)
        assert server.is_disabled() is True

    def test_is_disabled_when_disabled_false_then_false(self):
        server = McpServer(command="test", disabled=False)
        assert server.is_disabled() is False

    def test_is_disabled_when_enabled_false_then_true(self):
        server = McpServer(command="test", enabled=False)
        assert server.is_disabled() is True

    def test_is_disabled_when_enabled_true_then_false(self):
        server = McpServer(command="test", enabled=True)
        assert server.is_disabled() is False

    def test_is_disabled_when_default_then_false(self):
        server = McpServer(command="test")
        assert server.is_disabled() is False

    def test_is_disabled_when_disabled_takes_precedence_over_enabled(self):
        server = McpServer(command="test", disabled=True, enabled=True)
        assert server.is_disabled() is True

    def test_to_dict_when_exclude_none_then_no_none_values(self):
        server = McpServer(command="npx", args=["-y", "test"])
        d = server.to_dict()
        assert "command" in d
        assert "args" in d
        assert "url" not in d
        assert "disabled" not in d
        assert "env" not in d

    def test_to_dict_when_include_none_then_has_none_values(self):
        server = McpServer(command="test")
        d = server.to_dict(exclude_none=False)
        assert "url" in d
        assert d["url"] is None

    def test_to_toml_dict_when_camel_fields_then_snake_case(self):
        server = McpServer(command="npx", alwaysAllow=["tool1"])
        d = server.to_toml_dict()
        assert "always_allow" in d
        assert "alwaysAllow" not in d
        assert d["always_allow"] == ["tool1"]

    def test_to_toml_dict_when_bearer_token_then_snake_case(self):
        server = McpServer(command="npx", bearerTokenEnvVar="MY_TOKEN")
        d = server.to_toml_dict()
        assert "bearer_token_env_var" in d
        assert d["bearer_token_env_var"] == "MY_TOKEN"

    def test_from_toml_dict_when_snake_case_then_camel_fields(self):
        data = {
            "command": "npx",
            "always_allow": ["tool1"],
            "bearer_token_env_var": "MY_TOKEN",
        }
        server = McpServer.from_toml_dict(data)
        assert server.command == "npx"
        assert server.alwaysAllow == ["tool1"]
        assert server.bearerTokenEnvVar == "MY_TOKEN"

    def test_extra_fields_when_set_then_preserved_in_dict(self):
        server = McpServer(command="test", custom_field="custom_value")
        d = server.to_dict()
        assert d.get("custom_field") == "custom_value"

    def test_env_when_set_then_preserved(self):
        server = McpServer(command="test", env={"API_KEY": "secret", "OTHER": "val"})
        assert server.env == {"API_KEY": "secret", "OTHER": "val"}

    def test_type_when_set_then_preserved(self):
        server = McpServer(command="test", type="stdio")
        assert server.type == "stdio"

    def test_trust_when_set_then_preserved(self):
        server = McpServer(command="test", trust=True)
        assert server.trust is True

    def test_cwd_when_set_then_preserved(self):
        server = McpServer(command="test", cwd="/some/path")
        assert server.cwd == "/some/path"

    def test_timeout_when_set_then_preserved(self):
        server = McpServer(command="test", timeout=30)
        assert server.timeout == 30


class TestMcpServersConfig:
    """Tests for the McpServersConfig container model."""

    def test_from_dict_when_valid_then_all_parsed(self):
        data = {
            "server1": {"command": "npx", "args": ["-y", "test"]},
            "server2": {"url": "http://localhost:8080"},
        }
        config = McpServersConfig.from_dict(data)
        assert len(config.servers) == 2
        assert "server1" in config.servers
        assert "server2" in config.servers
        assert config.servers["server1"].command == "npx"
        assert config.servers["server2"].url == "http://localhost:8080"

    def test_from_dict_when_no_command_or_url_then_still_parsed(self):
        """Entries without command/url are now accepted (permissive validation)."""
        data = {
            "valid": {"command": "test"},
            "extra_only": {"no_command_or_url": True},
        }
        config = McpServersConfig.from_dict(data)
        assert len(config.servers) == 2
        assert "valid" in config.servers
        assert "extra_only" in config.servers

    def test_from_dict_when_non_dict_entry_then_skipped(self):
        data = {
            "valid": {"command": "test"},
            "not_a_dict": "string_value",
            "also_not_dict": 42,
        }
        config = McpServersConfig.from_dict(data)
        assert len(config.servers) == 1

    def test_from_dict_when_empty_then_empty(self):
        config = McpServersConfig.from_dict({})
        assert len(config.servers) == 0

    def test_to_dict_when_servers_exist_then_correct_structure(self):
        config = McpServersConfig.from_dict({"s1": {"command": "test"}})
        d = config.to_dict()
        assert "s1" in d
        assert d["s1"]["command"] == "test"
        assert "url" not in d["s1"]

    def test_from_toml_dict_when_snake_case_then_converted(self):
        data = {"s1": {"command": "test", "always_allow": ["tool"]}}
        config = McpServersConfig.from_toml_dict(data)
        assert config.servers["s1"].alwaysAllow == ["tool"]

    def test_to_toml_dict_when_camel_case_then_converted(self):
        config = McpServersConfig.from_dict(
            {"s1": {"command": "test", "alwaysAllow": ["tool"]}}
        )
        d = config.to_toml_dict()
        assert "always_allow" in d["s1"]
        assert "alwaysAllow" not in d["s1"]

    def test_merge_when_disjoint_then_all_present(self):
        c1 = McpServersConfig.from_dict({"s1": {"command": "a"}})
        c2 = McpServersConfig.from_dict({"s2": {"command": "b"}})
        merged = c1.merge(c2)
        assert len(merged.servers) == 2
        assert "s1" in merged.servers
        assert "s2" in merged.servers

    def test_merge_when_overlapping_then_other_wins(self):
        c1 = McpServersConfig.from_dict({"s1": {"command": "old"}})
        c2 = McpServersConfig.from_dict({"s1": {"command": "new"}})
        merged = c1.merge(c2)
        assert merged.servers["s1"].command == "new"

    def test_merge_when_complex_then_correct_count(self):
        c1 = McpServersConfig.from_dict(
            {"s1": {"command": "a"}, "s2": {"command": "b"}}
        )
        c2 = McpServersConfig.from_dict(
            {"s2": {"command": "c"}, "s3": {"command": "d"}}
        )
        merged = c1.merge(c2)
        assert len(merged.servers) == 3
        assert merged.servers["s2"].command == "c"

    def test_server_names_when_multiple_then_sorted(self):
        config = McpServersConfig.from_dict(
            {
                "zebra": {"command": "z"},
                "alpha": {"command": "a"},
                "mango": {"command": "m"},
            }
        )
        assert config.server_names() == ["alpha", "mango", "zebra"]

    def test_server_names_when_empty_then_empty_list(self):
        config = McpServersConfig(servers={})
        assert config.server_names() == []


# ===========================================================================
# Agents
# ===========================================================================


class TestAgentDef:
    """Tests for AgentDef dataclass."""

    def test_resolve_path_when_darwin_then_expands_tilde(self):
        agent = _make_agent(paths={"darwin": "~/.test/config.json"})
        with patch("mcp_synchro.agents.sys") as mock_sys:
            mock_sys.platform = "darwin"
            path = agent.resolve_path()
            assert path is not None
            assert str(path).endswith(".test/config.json")
            assert "~" not in str(path)

    def test_resolve_path_when_wrong_platform_then_none(self):
        agent = _make_agent(paths={"win32": "C:\\test\\config.json"})
        with patch("mcp_synchro.agents.sys") as mock_sys:
            mock_sys.platform = "darwin"
            assert agent.resolve_path() is None

    def test_resolve_path_when_no_paths_then_none(self):
        agent = _make_agent(paths={})
        with patch("mcp_synchro.agents.sys") as mock_sys:
            mock_sys.platform = "darwin"
            assert agent.resolve_path() is None

    def test_is_toml_when_toml_format_then_true(self):
        agent = _make_agent(config_format="toml")
        assert agent.is_toml is True

    def test_is_toml_when_json_format_then_false(self):
        agent = _make_agent(config_format="json")
        assert agent.is_toml is False

    def test_config_exists_when_file_exists_then_true(self, tmp_path: Path):
        f = tmp_path / "config.json"
        f.write_text("{}")
        agent = _make_agent(paths={"darwin": str(f)})
        with patch("mcp_synchro.agents.sys") as mock_sys:
            mock_sys.platform = "darwin"
            assert agent.config_exists() is True

    def test_config_exists_when_file_missing_then_false(self, tmp_path: Path):
        agent = _make_agent(paths={"darwin": str(tmp_path / "nope.json")})
        with patch("mcp_synchro.agents.sys") as mock_sys:
            mock_sys.platform = "darwin"
            assert agent.config_exists() is False

    def test_mcp_wrapper_key_when_set_then_accessible(self):
        agent = _make_agent(mcp_wrapper_key="mcp", mcp_key="servers")
        assert agent.mcp_wrapper_key == "mcp"
        assert agent.mcp_key == "servers"


class TestParseAgentDefs:
    """Tests for parse_agent_defs and load_all_agent_defs."""

    def test_parse_agent_defs_when_valid_then_correct(self):
        data = {
            "agents": {
                "test-agent": {
                    "name": "Test Agent",
                    "description": "A test agent",
                    "config_format": "json",
                    "mcp_key": "mcpServers",
                    "paths": {"darwin": "~/.test/mcp.json"},
                }
            }
        }
        agents = parse_agent_defs(data)
        assert len(agents) == 1
        assert agents[0].id == "test-agent"
        assert agents[0].name == "Test Agent"
        assert agents[0].description == "A test agent"
        assert agents[0].config_format == "json"

    def test_parse_agent_defs_when_multiple_then_all_parsed(self):
        data = {
            "agents": {
                "a1": {"name": "A1", "paths": {}},
                "a2": {"name": "A2", "paths": {}},
                "a3": {"name": "A3", "paths": {}},
            }
        }
        agents = parse_agent_defs(data)
        assert len(agents) == 3

    def test_parse_agent_defs_when_defaults_then_json_and_mcpservers(self):
        data = {"agents": {"test": {"name": "Test", "paths": {}}}}
        agents = parse_agent_defs(data)
        assert agents[0].config_format == "json"
        assert agents[0].mcp_key == "mcpServers"

    def test_parse_agent_defs_when_wrapper_key_then_set(self):
        data = {
            "agents": {
                "vscode": {
                    "name": "VS Code",
                    "mcp_key": "servers",
                    "mcp_wrapper_key": "mcp",
                    "paths": {},
                }
            }
        }
        agents = parse_agent_defs(data)
        assert agents[0].mcp_wrapper_key == "mcp"
        assert agents[0].mcp_key == "servers"

    def test_parse_agent_defs_when_empty_agents_then_empty_list(self):
        data = {"agents": {}}
        assert parse_agent_defs(data) == []

    def test_parse_agent_defs_when_no_agents_key_then_empty_list(self):
        data = {"something_else": {}}
        assert parse_agent_defs(data) == []

    def test_builtin_agents_path_when_called_then_exists(self):
        path = get_builtin_agents_path()
        assert path.exists()
        assert path.name == "agents.json"

    def test_load_all_agent_defs_when_default_then_has_known_agents(self):
        agents = load_all_agent_defs()
        assert len(agents) >= 20, f"Expected >=20 agents, got {len(agents)}"
        names = [a.name for a in agents]
        assert "Claude Desktop" in names
        assert "Codex CLI" in names

    def test_load_all_agent_defs_when_user_override_then_merged(self, tmp_path: Path):
        user_agents = tmp_path / "user_agents.json"
        user_agents.write_text(
            json.dumps(
                {
                    "agents": {
                        "custom-agent": {
                            "name": "Custom Agent",
                            "description": "User-defined",
                            "config_format": "json",
                            "mcp_key": "mcpServers",
                            "paths": {"darwin": "~/.custom/config.json"},
                        }
                    }
                }
            )
        )
        agents = load_all_agent_defs(user_agents_path=user_agents)
        names = [a.name for a in agents]
        assert "Custom Agent" in names
        assert "Claude Desktop" in names  # built-in still present

    def test_load_all_agent_defs_when_user_overrides_builtin_then_replaced(
        self, tmp_path: Path
    ):
        user_agents = tmp_path / "user_agents.json"
        user_agents.write_text(
            json.dumps(
                {
                    "agents": {
                        "claude-desktop": {
                            "name": "Claude Desktop Custom",
                            "description": "Overridden",
                            "config_format": "json",
                            "mcp_key": "mcpServers",
                            "paths": {"darwin": "~/.custom/claude.json"},
                        }
                    }
                }
            )
        )
        agents = load_all_agent_defs(user_agents_path=user_agents)
        claude_agents = [a for a in agents if a.id == "claude-desktop"]
        assert len(claude_agents) == 1
        assert claude_agents[0].name == "Claude Desktop Custom"


# ===========================================================================
# Readers
# ===========================================================================


class TestReaders:
    """Tests for JSON/TOML readers and MCP server extraction."""

    def test_read_json_when_valid_then_parsed(self, tmp_path: Path):
        f = tmp_path / "test.json"
        f.write_text('{"mcpServers": {"s1": {"command": "test"}}, "other": 42}')
        data = read_json(f)
        assert "mcpServers" in data
        assert data["other"] == 42

    def test_read_json_when_empty_object_then_empty_dict(self, tmp_path: Path):
        f = tmp_path / "empty.json"
        f.write_text("{}")
        data = read_json(f)
        assert data == {}

    def test_read_toml_when_valid_then_parsed(self, tmp_path: Path):
        f = tmp_path / "test.toml"
        f.write_text('[mcp_servers.my-server]\ncommand = "npx"\n')
        data = read_toml(f)
        assert "mcp_servers" in data
        assert data["mcp_servers"]["my-server"]["command"] == "npx"

    def test_extract_mcp_servers_when_direct_key_then_extracted(self):
        agent = _make_agent(mcp_key="mcpServers")
        data = {"mcpServers": {"s1": {"command": "test"}}, "other": "data"}
        result = extract_mcp_servers(data, agent)
        assert result is not None
        assert "s1" in result
        assert result["s1"]["command"] == "test"

    def test_extract_mcp_servers_when_wrapper_key_then_extracted(self):
        agent = _make_agent(mcp_key="servers", mcp_wrapper_key="mcp")
        data = {"mcp": {"servers": {"s1": {"command": "test"}}}}
        result = extract_mcp_servers(data, agent)
        assert result is not None
        assert "s1" in result

    def test_extract_mcp_servers_when_wrapper_key_missing_then_none(self):
        agent = _make_agent(mcp_key="servers", mcp_wrapper_key="mcp")
        data = {"other": {"servers": {"s1": {"command": "test"}}}}
        result = extract_mcp_servers(data, agent)
        assert result is None

    def test_extract_mcp_servers_when_wrapper_key_inner_missing_then_none(self):
        agent = _make_agent(mcp_key="servers", mcp_wrapper_key="mcp")
        data = {"mcp": {"other_key": {}}}
        result = extract_mcp_servers(data, agent)
        assert result is None

    def test_extract_mcp_servers_when_missing_key_then_none(self):
        agent = _make_agent(mcp_key="mcpServers")
        data = {"other": "stuff"}
        result = extract_mcp_servers(data, agent)
        assert result is None

    def test_extract_mcp_servers_when_key_is_not_dict_then_none(self):
        agent = _make_agent(mcp_key="mcpServers")
        data = {"mcpServers": "not a dict"}
        result = extract_mcp_servers(data, agent)
        assert result is None

    def test_extract_mcp_servers_when_toml_key_then_extracted(self):
        agent = _make_agent(config_format="toml", mcp_key="mcp_servers")
        data = {"mcp_servers": {"s1": {"command": "test"}}}
        result = extract_mcp_servers(data, agent)
        assert result is not None
        assert "s1" in result

    def test_read_agent_config_when_json_with_servers_then_parsed(self, tmp_path: Path):
        f = tmp_path / "config.json"
        f.write_text(
            json.dumps(
                {
                    "mcpServers": {"brave": {"command": "brave-mcp", "args": []}},
                    "preferences": {"theme": "dark"},
                }
            )
        )
        agent = _make_agent(mcp_key="mcpServers")
        data, config = read_agent_config(f, agent)
        assert config is not None
        assert "brave" in config.servers
        assert config.servers["brave"].command == "brave-mcp"
        assert data["preferences"]["theme"] == "dark"

    def test_read_agent_config_when_no_servers_then_none_config(self, tmp_path: Path):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"preferences": {"theme": "dark"}}))
        agent = _make_agent(mcp_key="mcpServers")
        data, config = read_agent_config(f, agent)
        assert config is None
        assert data["preferences"]["theme"] == "dark"

    def test_read_agent_config_when_wrapper_key_then_parsed(self, tmp_path: Path):
        f = tmp_path / "settings.json"
        f.write_text(
            json.dumps(
                {
                    "mcp": {"servers": {"fs": {"command": "fs-mcp"}}},
                    "editor.fontSize": 14,
                }
            )
        )
        agent = _make_agent(mcp_key="servers", mcp_wrapper_key="mcp")
        data, config = read_agent_config(f, agent)
        assert config is not None
        assert "fs" in config.servers
        assert data["editor.fontSize"] == 14

    def test_read_agent_config_when_empty_servers_then_empty_config(
        self, tmp_path: Path
    ):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"mcpServers": {}}))
        agent = _make_agent(mcp_key="mcpServers")
        _data, config = read_agent_config(f, agent)
        assert config is not None
        assert len(config.servers) == 0


# ===========================================================================
# Writers
# ===========================================================================


class TestWriters:
    """Tests for JSON/TOML writers and MCP server update logic."""

    def test_write_json_when_called_then_file_created(self, tmp_path: Path):
        f = tmp_path / "out.json"
        write_json(f, {"key": "value"})
        assert f.exists()
        data = json.loads(f.read_text())
        assert data["key"] == "value"

    def test_write_json_when_nested_dir_then_created(self, tmp_path: Path):
        f = tmp_path / "sub" / "dir" / "out.json"
        write_json(f, {"ok": True})
        assert f.exists()

    def test_write_json_when_preserves_non_mcp_data(self, tmp_path: Path):
        f = tmp_path / "config.json"
        original = {"mcpServers": {}, "preferences": {"theme": "dark"}}
        write_json(f, original)
        data = json.loads(f.read_text())
        assert data["preferences"]["theme"] == "dark"

    def test_write_toml_when_called_then_file_created(self, tmp_path: Path):
        f = tmp_path / "out.toml"
        write_toml(f, {"mcp_servers": {"s1": {"command": "test"}}})
        assert f.exists()
        content = f.read_bytes()
        assert b"command" in content

    def test_update_mcp_servers_when_direct_key_then_updated(self):
        agent = _make_agent(mcp_key="mcpServers")
        data = {"mcpServers": {"old": {"command": "old"}}, "other": "keep"}
        config = McpServersConfig.from_dict({"new": {"command": "new"}})
        result = update_mcp_servers(data, config, agent)
        assert "new" in result["mcpServers"]
        assert "old" not in result["mcpServers"]
        assert result["other"] == "keep"

    def test_update_mcp_servers_when_wrapper_key_then_nested(self):
        agent = _make_agent(mcp_key="servers", mcp_wrapper_key="mcp")
        data = {"mcp": {"servers": {}}, "other": "keep"}
        config = McpServersConfig.from_dict({"s1": {"command": "test"}})
        result = update_mcp_servers(data, config, agent)
        assert "s1" in result["mcp"]["servers"]
        assert result["other"] == "keep"

    def test_update_mcp_servers_when_wrapper_key_missing_then_created(self):
        agent = _make_agent(mcp_key="servers", mcp_wrapper_key="mcp")
        data = {"other": "keep"}
        config = McpServersConfig.from_dict({"s1": {"command": "test"}})
        result = update_mcp_servers(data, config, agent)
        assert "mcp" in result
        assert "s1" in result["mcp"]["servers"]

    def test_update_mcp_servers_when_toml_then_snake_case(self):
        agent = _make_agent(config_format="toml", mcp_key="mcp_servers")
        data = {"mcp_servers": {}}
        config = McpServersConfig.from_dict(
            {"s1": {"command": "test", "alwaysAllow": ["tool"]}}
        )
        result = update_mcp_servers(data, config, agent)
        assert "always_allow" in result["mcp_servers"]["s1"]

    def test_write_agent_config_when_json_then_roundtrip(self, tmp_path: Path):
        f = tmp_path / "config.json"
        original = {
            "mcpServers": {"old": {"command": "old-cmd"}},
            "theme": "dark",
        }
        write_json(f, original)
        agent = _make_agent(mcp_key="mcpServers")
        new_config = McpServersConfig.from_dict({"new": {"command": "new-cmd"}})
        write_agent_config(f, original, new_config, agent)
        result = json.loads(f.read_text())
        assert "new" in result["mcpServers"]
        assert "old" not in result["mcpServers"]
        assert result["theme"] == "dark"

    def test_write_agent_config_when_wrapper_then_preserves_structure(
        self, tmp_path: Path
    ):
        f = tmp_path / "settings.json"
        original = {
            "mcp": {"servers": {"old": {"command": "old"}}},
            "editor.fontSize": 14,
        }
        write_json(f, original)
        agent = _make_agent(mcp_key="servers", mcp_wrapper_key="mcp")
        new_config = McpServersConfig.from_dict({"new": {"command": "new"}})
        write_agent_config(f, original, new_config, agent)
        result = json.loads(f.read_text())
        assert "new" in result["mcp"]["servers"]
        assert result["editor.fontSize"] == 14

    def test_write_agent_config_when_empty_config_then_clears_servers(
        self, tmp_path: Path
    ):
        f = tmp_path / "config.json"
        original = {"mcpServers": {"s1": {"command": "test"}}}
        write_json(f, original)
        agent = _make_agent(mcp_key="mcpServers")
        empty = McpServersConfig(servers={})
        write_agent_config(f, original, empty, agent)
        result = json.loads(f.read_text())
        assert result["mcpServers"] == {}


# ===========================================================================
# Config (SoT)
# ===========================================================================


class TestConfig:
    """Tests for SoT load/save operations."""

    def test_save_and_load_sot_when_roundtrip_then_identical(self, tmp_path: Path):
        sot_path = tmp_path / "mcp.json"
        with patch("mcp_synchro.config.get_sot_path", return_value=sot_path):
            config = McpServersConfig.from_dict(
                {
                    "test-server": {"command": "test", "args": ["-v"]},
                    "url-server": {"url": "http://localhost:3000"},
                }
            )
            save_sot(config)
            loaded = load_sot()
            assert len(loaded.servers) == 2
            assert "test-server" in loaded.servers
            assert "url-server" in loaded.servers
            assert loaded.servers["test-server"].command == "test"
            assert loaded.servers["test-server"].args == ["-v"]
            assert loaded.servers["url-server"].url == "http://localhost:3000"

    def test_load_sot_when_missing_then_empty(self, tmp_path: Path):
        sot_path = tmp_path / "nonexistent.json"
        with patch("mcp_synchro.config.get_sot_path", return_value=sot_path):
            config = load_sot()
            assert len(config.servers) == 0

    def test_save_sot_when_called_then_returns_path(self, tmp_path: Path):
        sot_path = tmp_path / "mcp.json"
        with patch("mcp_synchro.config.get_sot_path", return_value=sot_path):
            config = McpServersConfig.from_dict({"s1": {"command": "cmd"}})
            result_path = save_sot(config)
            assert result_path == sot_path

    def test_save_sot_when_called_then_creates_parent_dirs(self, tmp_path: Path):
        sot_path = tmp_path / "sub" / "dir" / "mcp.json"
        with patch("mcp_synchro.config.get_sot_path", return_value=sot_path):
            config = McpServersConfig.from_dict({"s1": {"command": "cmd"}})
            save_sot(config)
            assert sot_path.exists()

    def test_save_sot_when_called_then_json_has_mcpservers_key(self, tmp_path: Path):
        sot_path = tmp_path / "mcp.json"
        with patch("mcp_synchro.config.get_sot_path", return_value=sot_path):
            config = McpServersConfig.from_dict({"s1": {"command": "cmd"}})
            save_sot(config)
            raw = json.loads(sot_path.read_text())
            assert "mcpServers" in raw
            assert "s1" in raw["mcpServers"]

    def test_load_sot_when_empty_mcpservers_then_empty_config(self, tmp_path: Path):
        sot_path = tmp_path / "mcp.json"
        sot_path.write_text(json.dumps({"mcpServers": {}}))
        with patch("mcp_synchro.config.get_sot_path", return_value=sot_path):
            config = load_sot()
            assert len(config.servers) == 0


# ===========================================================================
# Sync
# ===========================================================================


class TestSync:
    """Tests for push, pull_new, and pull_all sync operations."""

    def _make_discovered(
        self,
        tmp_path: Path,
        name: str,
        servers: dict,
        mcp_key: str = "mcpServers",
        mcp_wrapper_key: str | None = None,
    ) -> tuple[DiscoveredAgent, Path]:
        """Helper: create a temp agent config file and return DiscoveredAgent + path."""
        f = _make_agent_config_file(tmp_path, f"{name}.json", servers, mcp_key=mcp_key)
        agent = _make_agent(
            id=name,
            name=name,
            mcp_key=mcp_key,
            paths={"darwin": str(f)},
            mcp_wrapper_key=mcp_wrapper_key,
        )
        return DiscoveredAgent(agent=agent, path=f), f

    def test_push_when_servers_exist_then_written(self, tmp_path: Path):
        from mcp_synchro.sync import push as _push

        sot_path = tmp_path / "sot.json"
        sot_path.write_text(
            json.dumps({"mcpServers": {"my-server": {"command": "my-cmd", "args": []}}})
        )

        da, path = self._make_discovered(tmp_path, "target", {})

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            results = _push(dry_run=False)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].agent_name == "target"
        data = json.loads(path.read_text())
        assert "my-server" in data["mcpServers"]
        assert data["mcpServers"]["my-server"]["command"] == "my-cmd"

    def test_push_when_dry_run_then_no_write(self, tmp_path: Path):
        from mcp_synchro.sync import push as _push

        sot_path = tmp_path / "sot.json"
        sot_path.write_text(json.dumps({"mcpServers": {"s1": {"command": "cmd"}}}))

        da, path = self._make_discovered(
            tmp_path, "target", {"old": {"command": "old"}}
        )
        original_content = path.read_text()

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            results = _push(dry_run=True)

        assert all(r.success for r in results)
        assert path.read_text() == original_content

    def test_push_when_sot_empty_then_returns_failure(self, tmp_path: Path):
        from mcp_synchro.sync import push as _push

        sot_path = tmp_path / "sot.json"
        sot_path.write_text(json.dumps({"mcpServers": {}}))

        with patch("mcp_synchro.config.get_sot_path", return_value=sot_path):
            results = _push(dry_run=False)

        assert len(results) == 1
        assert results[0].success is False
        assert "empty" in results[0].message.lower()

    def test_push_when_no_agents_discovered_then_returns_failure(self, tmp_path: Path):
        from mcp_synchro.sync import push as _push

        sot_path = tmp_path / "sot.json"
        sot_path.write_text(json.dumps({"mcpServers": {"s1": {"command": "cmd"}}}))

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            results = _push(dry_run=False)

        assert len(results) == 1
        assert results[0].success is False

    def test_push_when_multiple_agents_then_all_written(self, tmp_path: Path):
        from mcp_synchro.sync import push as _push

        sot_path = tmp_path / "sot.json"
        sot_path.write_text(
            json.dumps({"mcpServers": {"shared": {"command": "shared-cmd"}}})
        )

        da1, path1 = self._make_discovered(tmp_path, "agent1", {})
        da2, path2 = self._make_discovered(tmp_path, "agent2", {})

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da1, da2]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            results = _push(dry_run=False)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert "shared" in json.loads(path1.read_text())["mcpServers"]
        assert "shared" in json.loads(path2.read_text())["mcpServers"]

    def test_pull_all_when_multiple_agents_then_merged(self, tmp_path: Path):
        from mcp_synchro.sync import pull_all as _pull_all

        sot_path = tmp_path / "sot.json"

        da1, _ = self._make_discovered(
            tmp_path, "a1", {"server-a": {"command": "cmd-a"}}
        )
        da2, _ = self._make_discovered(
            tmp_path, "a2", {"server-b": {"command": "cmd-b"}}
        )

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da1, da2]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            results = _pull_all(dry_run=False)

        assert all(r.success for r in results)
        data = json.loads(sot_path.read_text())
        assert "server-a" in data["mcpServers"]
        assert "server-b" in data["mcpServers"]

    def test_pull_all_when_overlapping_then_later_wins(self, tmp_path: Path):
        from mcp_synchro.sync import pull_all as _pull_all

        sot_path = tmp_path / "sot.json"

        da1, _ = self._make_discovered(tmp_path, "a1", {"shared": {"command": "first"}})
        da2, _ = self._make_discovered(
            tmp_path, "a2", {"shared": {"command": "second"}}
        )

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da1, da2]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            _pull_all(dry_run=False)

        data = json.loads(sot_path.read_text())
        assert data["mcpServers"]["shared"]["command"] == "second"

    def test_pull_all_when_dry_run_then_no_sot_written(self, tmp_path: Path):
        from mcp_synchro.sync import pull_all as _pull_all

        sot_path = tmp_path / "sot.json"

        da1, _ = self._make_discovered(
            tmp_path, "a1", {"server-a": {"command": "cmd-a"}}
        )

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da1]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            results = _pull_all(dry_run=True)

        assert all(r.success for r in results)
        assert not sot_path.exists()

    def test_pull_all_when_no_agents_then_empty_results(self, tmp_path: Path):
        from mcp_synchro.sync import pull_all as _pull_all

        sot_path = tmp_path / "sot.json"

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            results = _pull_all(dry_run=False)

        assert results == []

    def test_pull_new_when_new_server_then_imported(self, tmp_path: Path):
        from mcp_synchro.sync import pull_new as _pull_new

        sot_path = tmp_path / "sot.json"
        sot_path.write_text(
            json.dumps({"mcpServers": {"existing": {"command": "old"}}})
        )

        da1, _ = self._make_discovered(
            tmp_path,
            "a1",
            {
                "existing": {"command": "new-version"},
                "brand-new": {"command": "new-cmd"},
            },
        )

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da1]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            _pull_new(dry_run=False)

        data = json.loads(sot_path.read_text())
        assert "existing" in data["mcpServers"]
        assert data["mcpServers"]["existing"]["command"] == "old"  # NOT overwritten
        assert "brand-new" in data["mcpServers"]
        assert data["mcpServers"]["brand-new"]["command"] == "new-cmd"

    def test_pull_new_when_no_new_then_sot_unchanged(self, tmp_path: Path):
        from mcp_synchro.sync import pull_new as _pull_new

        sot_path = tmp_path / "sot.json"
        original = {"mcpServers": {"existing": {"command": "old"}}}
        sot_path.write_text(json.dumps(original))

        da1, _ = self._make_discovered(
            tmp_path, "a1", {"existing": {"command": "different"}}
        )

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da1]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            _pull_new(dry_run=False)

        data = json.loads(sot_path.read_text())
        assert data["mcpServers"]["existing"]["command"] == "old"

    def test_pull_new_when_dry_run_then_no_write(self, tmp_path: Path):
        from mcp_synchro.sync import pull_new as _pull_new

        sot_path = tmp_path / "sot.json"
        original = {"mcpServers": {"existing": {"command": "old"}}}
        sot_path.write_text(json.dumps(original))
        original_content = sot_path.read_text()

        da1, _ = self._make_discovered(
            tmp_path,
            "a1",
            {
                "brand-new": {"command": "new-cmd"},
            },
        )

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da1]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            _pull_new(dry_run=True)

        assert sot_path.read_text() == original_content

    def test_pull_new_when_empty_sot_then_all_imported(self, tmp_path: Path):
        from mcp_synchro.sync import pull_new as _pull_new

        sot_path = tmp_path / "sot.json"
        sot_path.write_text(json.dumps({"mcpServers": {}}))

        da1, _ = self._make_discovered(
            tmp_path,
            "a1",
            {
                "s1": {"command": "cmd1"},
                "s2": {"command": "cmd2"},
            },
        )

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da1]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            _pull_new(dry_run=False)

        data = json.loads(sot_path.read_text())
        assert "s1" in data["mcpServers"]
        assert "s2" in data["mcpServers"]

    def test_pull_new_when_sot_missing_then_all_imported(self, tmp_path: Path):
        from mcp_synchro.sync import pull_new as _pull_new

        sot_path = tmp_path / "sot.json"
        # sot_path does not exist

        da1, _ = self._make_discovered(
            tmp_path,
            "a1",
            {
                "s1": {"command": "cmd1"},
            },
        )

        with (
            patch("mcp_synchro.sync._get_discovered_agents", return_value=[da1]),
            patch("mcp_synchro.config.get_sot_path", return_value=sot_path),
        ):
            _pull_new(dry_run=False)

        data = json.loads(sot_path.read_text())
        assert "s1" in data["mcpServers"]
