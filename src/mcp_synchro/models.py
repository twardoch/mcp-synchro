# this_file: src/mcp_synchro/models.py
"""Pydantic models for MCP server configurations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class McpServer(BaseModel):
    """Configuration for a single Model Context Protocol (MCP) server.

    MCP bridges AI agents with tools. This model defines *how* an agent connects to an MCP server.
    It supports two main connection types (transports):
    1. stdio: The agent runs a local command (like `npx` or `python`).
    2. HTTP: The agent connects to a remote URL via Server-Sent Events (SSE).

    Because every AI agent flavor (Claude, Cursor, Codex, etc.) invents its own config keys,
    we allow unknown fields (`extra="allow"`). This way, when we pull a config from Cursor,
    we don't lose Cursor's special sauce when pushing it to Claude.

    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Stdio transport fields
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None

    # HTTP transport fields
    url: str | None = None

    # Common fields
    type: str | None = None  # stdio, sse, streamable-http, streamableHttp
    disabled: bool | None = None
    enabled: bool | None = None
    timeout: int | None = None

    # Cline/Roo/Kilo specific
    alwaysAllow: list[str] | None = None
    autoApprove: list[str] | None = None

    # Gemini CLI specific
    trust: bool | None = None

    # Codex CLI specific
    bearerTokenEnvVar: str | None = None
    httpHeaders: dict[str, str] | None = None

    # AI Panel (Omata) specific
    name: str | None = None
    headers: dict[str, str] | None = None  # HTTP headers (distinct from httpHeaders)

    # Transport type (alternative to `type` field used by some agents)
    # Values: stdio, sse, streamable-http, streamableHttp
    transport: str | None = None

    # OpenCode specific (uses `environment` instead of `env`)
    environment: dict[str, str] | None = None

    # 5ire specific
    isActive: bool | None = None
    key: str | None = None
    capabilities: list[str] | None = None
    approvalPolicy: str | None = None  # "never", "always", "once"
    proxy: str | None = None
    description: str | None = None
    homepage: str | None = None

    # Jan specific
    active: bool | None = None
    official: bool | None = None

    # Qwen/Gemini specific
    httpUrl: str | None = None  # Streamable HTTP endpoint (separate from url=SSE)
    includeTools: list[str] | None = None
    excludeTools: list[str] | None = None

    # Windsurf specific
    serverUrl: str | None = None  # Alternative to url for HTTP transport

    # VS Code specific
    envFile: str | None = None
    sandboxEnabled: bool | None = None

    # Copilot CLI specific
    tools: list[str] | None = None
    oauthClientId: str | None = None

    # Crush specific
    disabled_tools: list[str] | None = None

    # Codex CLI additional
    enabled_tools: list[str] | None = None
    required: bool | None = None

    # Roo Code specific
    watchPaths: list[str] | None = None
    disabledTools: list[str] | None = None
    remoteConfigured: bool | None = None

    @model_validator(mode="after")
    def validate_transport(self) -> McpServer:
        """Checks if the transport looks alive. If it lacks both a command and a url, we let it pass, but it might be a ghost config from a weird agent."""
        if not self.command and not self.url:
            # Some agents store command differently (e.g., OpenCode uses array)
            # Don't fail hard - extra fields may carry the command info
            pass
        return self

    @property
    def is_http(self) -> bool:
        """Is this talking over HTTP instead of stdio? Finds the truth hiding in the URL or transport type."""
        if self.url or self.httpUrl or self.serverUrl:
            return True
        t = self.type or self.transport
        if t and t in ("sse", "streamable-http", "streamableHttp", "http"):
            return True
        return False

    @field_validator("args", mode="before")
    @classmethod
    def ensure_args_list(cls, v: Any) -> list[str] | None:
        """Forces arguments into a strict list of strings. No ints, no floats, just stringy goodness."""
        if v is None:
            return None
        if isinstance(v, str):
            return [v]
        return [str(item) for item in v]

    def is_disabled(self) -> bool:
        """Checks the pulse. Various agents use `disabled`, `enabled`, `isActive`, or `active`. We wrangle them all to answer: is this turned off?"""
        if self.disabled is not None:
            return self.disabled
        if self.enabled is not None:
            return not self.enabled
        if self.isActive is not None:
            return not self.isActive
        if self.active is not None:
            return not self.active
        return False

    def to_dict(self, exclude_none: bool = True) -> dict[str, Any]:
        """Dumps to a pure JSON-ready dictionary. Leaves the None values behind by default."""
        data = self.model_dump(exclude_none=exclude_none)
        return data

    def to_toml_dict(self) -> dict[str, Any]:
        """Dumps to a TOML-ready dictionary. Converts camelCase agent keys into snake_case so Python and TOML stay happy."""
        result: dict[str, Any] = {}
        for key, value in self.model_dump(exclude_none=True).items():
            snake_key = _camel_to_snake(key)
            result[snake_key] = value
        return result

    @classmethod
    def from_toml_dict(cls, data: dict[str, Any]) -> McpServer:
        """Inflates a server from TOML. Morphs those snake_case keys back into the camelCase the agents expect."""
        converted: dict[str, Any] = {}
        for key, value in data.items():
            camel_key = _snake_to_camel(key)
            converted[camel_key] = value
        return cls.model_validate(converted)


def _camel_to_snake(name: str) -> str:
    """Turns `camelCase` into `snake_case`."""
    result: list[str] = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def _snake_to_camel(name: str) -> str:
    """Turns `snake_case` into `camelCase`."""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class McpServersConfig(BaseModel):
    """The Source of Truth (SoT) for your MCP universe.

    This holds every MCP server config you care about. When you push, these servers
    get stamped into the native config files for Claude, Cursor, Codex, and friends.
    """

    model_config = ConfigDict(extra="forbid")

    servers: dict[str, McpServer]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> McpServersConfig:
        """Builds the universe from raw JSON bytes. Ignores broken entries instead of crashing the whole sync."""
        servers: dict[str, McpServer] = {}
        for name, config in data.items():
            if isinstance(config, dict):
                try:
                    servers[name] = McpServer.model_validate(config)
                except Exception:
                    # Skip invalid server entries
                    continue
        return cls(servers=servers)

    @classmethod
    def from_toml_dict(cls, data: dict[str, Any]) -> McpServersConfig:
        """Builds the universe from raw TOML bytes."""
        servers: dict[str, McpServer] = {}
        for name, config in data.items():
            if isinstance(config, dict):
                try:
                    servers[name] = McpServer.from_toml_dict(config)
                except Exception:
                    continue
        return cls(servers=servers)

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Spits out a massive JSON-ready dict of every server."""
        return {name: server.to_dict() for name, server in self.servers.items()}

    def to_toml_dict(self) -> dict[str, dict[str, Any]]:
        """Spits out a massive TOML-ready dict of every server."""
        return {name: server.to_toml_dict() for name, server in self.servers.items()}

    def merge(self, other: McpServersConfig) -> McpServersConfig:
        """Smash two configs together. The `other` config wins any fistfights over duplicate server names."""
        merged = dict(self.servers)
        merged.update(other.servers)
        return McpServersConfig(servers=merged)

    def server_names(self) -> list[str]:
        """Alphabetical list of every server we track."""
        return sorted(self.servers.keys())
