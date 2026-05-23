# this_file: src/mcp_synchro/sync.py
"""The syncing engine. Where configs get pushed, pulled, and merged."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from mcp_synchro.agents import (
    AgentDef,
    DiscoveredAgent,
    discover_agents,
    load_all_agent_defs,
)
from mcp_synchro.config import get_user_agents_path, load_sot, save_sot
from mcp_synchro.models import McpServersConfig
from mcp_synchro.readers import read_agent_config
from mcp_synchro.writers import write_agent_config


@dataclass
class SyncResult:
    """The receipt for a single sync operation. Did it work? What did it touch?"""

    agent_name: str
    path: Path
    success: bool
    message: str
    servers_count: int = 0


def _get_discovered_agents() -> list[DiscoveredAgent]:
    """Wakes up the hunting dogs and finds every agent currently living on this disk."""
    user_agents = get_user_agents_path()
    agent_defs = load_all_agent_defs(
        user_agents_path=user_agents if user_agents.exists() else None
    )
    return discover_agents(agent_defs)


def _get_sync_targets(
    agents: list[str] | None = None,
    workspace: str | Path | None = None,
) -> list[tuple[AgentDef, Path]]:
    """Calculates agent definitions and target paths for the sync operation."""
    if workspace is None:
        discovered = _get_discovered_agents()
        if agents:
            discovered = [
                da
                for da in discovered
                if da.agent.id in agents or da.agent.name in agents
            ]
        return [(da.agent, da.path) for da in discovered]

    user_agents = get_user_agents_path()
    agent_defs = load_all_agent_defs(
        user_agents_path=user_agents if user_agents.exists() else None
    )
    if agents:
        agent_defs = [a for a in agent_defs if a.id in agents or a.name in agents]

    targets: list[tuple[AgentDef, Path]] = []
    for agent in agent_defs:
        if not agent.supports_workspace_scope:
            if agents and agent.id in agents:
                raise ValueError(
                    f"✗ {agent.id} does not support workspace-level MCP config as of May 2026.\n"
                    f"  Track https://github.com/google/antigravity/issues for status."
                )
            continue
        if agent.workspace_config_path:
            targets.append((agent, Path(workspace) / agent.workspace_config_path))
    return targets


def push(
    agents: list[str] | None = None,
    workspace: str | Path | None = None,
    dry_run: bool = False,
    resolve_commands: bool = True,
    probe_tools: bool = False,
) -> list[SyncResult]:
    """Stamps the Source of Truth onto every agent config we can find.

    We read `mcp.json` (the SoT), hunt down Claude, Cursor, Codex, etc.,
    and surgically overwrite their MCP sections. The rest of their configs
    (like UI settings or API keys) are safely ignored.
    """
    results: list[SyncResult] = []
    sot = load_sot()

    if not sot.servers:
        logger.warning("SoT is empty, nothing to push")
        return [
            SyncResult(
                agent_name="SoT",
                path=Path(""),
                success=False,
                message="SoT is empty. Run 'pull_all' or 'init' first.",
            )
        ]

    try:
        targets = _get_sync_targets(agents, workspace)
    except ValueError as e:
        raise ValueError(str(e)) from e

    if not targets:
        return [
            SyncResult(
                agent_name="System",
                path=Path(""),
                success=False,
                message="No agent configs found on this system.",
            )
        ]

    for agent, path in targets:
        try:
            if agent.deprecated:
                logger.warning(
                    agent.migration_hint or f"Agent '{agent.id}' is deprecated."
                )

            if not path.exists():
                data: dict[str, Any] = {}
            else:
                data, _ = read_agent_config(path, agent)

            # Probe tools if requested and limit exists
            if probe_tools and agent.tools_per_server_limit is not None:
                from mcp_synchro.prober import probe_tool_count

                for name, server in sot.servers.items():
                    if not server.is_disabled():
                        tool_count = probe_tool_count(server)
                        if (
                            tool_count is not None
                            and tool_count > agent.tools_per_server_limit
                        ):
                            limit = agent.tools_per_server_limit
                            logger.warning(
                                f'⚠ {agent.id}: server "{name}" exposes {tool_count} tools — '
                                f"Antigravity will reject it (hardcoded {limit}-tool cap).\n"
                                "  Consider splitting the server or using a filtering proxy."
                            )

            if dry_run:
                results.append(
                    SyncResult(
                        agent_name=agent.name,
                        path=path,
                        success=True,
                        message=f"Would write {len(sot.servers)} servers (dry run)",
                        servers_count=len(sot.servers),
                    )
                )
            else:
                write_agent_config(path, data, sot, agent, resolve_commands)
                results.append(
                    SyncResult(
                        agent_name=agent.name,
                        path=path,
                        success=True,
                        message=f"Wrote {len(sot.servers)} servers",
                        servers_count=len(sot.servers),
                    )
                )

        except PermissionError:
            results.append(
                SyncResult(
                    agent_name=agent.name,
                    path=path,
                    success=False,
                    message="Permission denied",
                )
            )
        except Exception as e:
            results.append(
                SyncResult(
                    agent_name=agent.name,
                    path=path,
                    success=False,
                    message=str(e),
                )
            )

    return results


def pull_new(
    agents: list[str] | None = None,
    workspace: str | Path | None = None,
    dry_run: bool = False,
) -> list[SyncResult]:
    """Scavenges for new servers the Source of Truth doesn't know about yet.

    If you manually added a server to Cursor, this function finds it and
    adds it to `mcp.json`. Existing servers in `mcp.json` are left untouched.
    """
    results: list[SyncResult] = []
    sot = load_sot()
    existing_names = set(sot.servers.keys())
    new_servers: dict[str, Any] = {}

    try:
        targets = _get_sync_targets(agents, workspace)
    except ValueError as e:
        raise ValueError(str(e)) from e

    for agent, path in targets:
        try:
            if agent.deprecated:
                logger.warning(
                    agent.migration_hint or f"Agent '{agent.id}' is deprecated."
                )

            if not path.exists():
                results.append(
                    SyncResult(
                        agent_name=agent.name,
                        path=path,
                        success=True,
                        message="No MCP servers found (config file does not exist)",
                    )
                )
                continue

            _, agent_config = read_agent_config(path, agent)
            if agent_config is None:
                results.append(
                    SyncResult(
                        agent_name=agent.name,
                        path=path,
                        success=True,
                        message="No MCP servers found",
                    )
                )
                continue

            added = []
            for name, server in agent_config.servers.items():
                if name not in existing_names and name not in new_servers:
                    new_servers[name] = server
                    added.append(name)

            if added:
                results.append(
                    SyncResult(
                        agent_name=agent.name,
                        path=path,
                        success=True,
                        message=f"New: {', '.join(added)}",
                        servers_count=len(added),
                    )
                )
            else:
                results.append(
                    SyncResult(
                        agent_name=agent.name,
                        path=path,
                        success=True,
                        message="No new servers",
                    )
                )

        except Exception as e:
            results.append(
                SyncResult(
                    agent_name=agent.name,
                    path=path,
                    success=False,
                    message=str(e),
                )
            )

    if new_servers:
        merged_servers = dict(sot.servers)
        merged_servers.update(new_servers)
        merged = McpServersConfig(servers=merged_servers)

        if dry_run:
            logger.info(f"Would add {len(new_servers)} new servers to SoT (dry run)")
        else:
            save_sot(merged)
            logger.info(f"Added {len(new_servers)} new servers to SoT")

    return results


def pull_all(
    agents: list[str] | None = None,
    workspace: str | Path | None = None,
    dry_run: bool = False,
) -> list[SyncResult]:
    """Nukes the Source of Truth and rebuilds it from scratch by reading everyone."""
    results: list[SyncResult] = []
    all_servers: dict[str, Any] = {}

    try:
        targets = _get_sync_targets(agents, workspace)
    except ValueError as e:
        raise ValueError(str(e)) from e

    for agent, path in targets:
        try:
            if agent.deprecated:
                logger.warning(
                    agent.migration_hint or f"Agent '{agent.id}' is deprecated."
                )

            if not path.exists():
                results.append(
                    SyncResult(
                        agent_name=agent.name,
                        path=path,
                        success=True,
                        message="No MCP servers found (config file does not exist)",
                    )
                )
                continue

            _, agent_config = read_agent_config(path, agent)
            if agent_config is None:
                results.append(
                    SyncResult(
                        agent_name=agent.name,
                        path=path,
                        success=True,
                        message="No MCP servers found",
                    )
                )
                continue

            count = 0
            for name, server in agent_config.servers.items():
                all_servers[name] = server
                count += 1

            results.append(
                SyncResult(
                    agent_name=agent.name,
                    path=path,
                    success=True,
                    message=f"Found {count} servers",
                    servers_count=count,
                )
            )

        except Exception as e:
            results.append(
                SyncResult(
                    agent_name=agent.name,
                    path=path,
                    success=False,
                    message=str(e),
                )
            )

    if all_servers:
        merged = McpServersConfig(servers=all_servers)
        if dry_run:
            logger.info(f"Would save {len(all_servers)} servers to SoT (dry run)")
        else:
            save_sot(merged)
            logger.info(f"Saved {len(all_servers)} servers to SoT")

    return results
