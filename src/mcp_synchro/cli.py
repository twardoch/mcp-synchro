# this_file: src/mcp_synchro/cli.py
"""The command line interface. Powered by Google Fire and heavily decorated by Rich."""

from __future__ import annotations

import json
import shutil
import sys

import fire  # type: ignore[import-untyped]
from loguru import logger
from rich.console import Console
from rich.table import Table

from mcp_synchro.agents import load_all_agent_defs
from mcp_synchro.config import (
    get_config_dir,
    get_sot_path,
    get_user_agents_path,
    load_sot,
)
from mcp_synchro.sync import SyncResult
from mcp_synchro.sync import pull_all as _pull_all
from mcp_synchro.sync import pull_new as _pull_new
from mcp_synchro.sync import push as _push

console = Console()


def _configure_logging(verbose: bool = False) -> None:
    """Hooks up loguru. Quiets the noise unless `--verbose` is thrown."""
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(sys.stderr, format="<level>{level}</level> | {message}", level=level)


def _print_results(results: list[SyncResult], title: str) -> None:
    """Renders our sync receipts into a pretty CLI table."""
    table = Table(title=title)
    table.add_column("Agent", style="cyan", no_wrap=True)
    table.add_column("Path", style="dim")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    success_count = 0
    fail_count = 0

    for r in results:
        if r.success:
            status = "[green]OK[/green]"
            success_count += 1
        else:
            status = "[red]FAIL[/red]"
            fail_count += 1

        table.add_row(r.agent_name, str(r.path), status, r.message)

    console.print(table)
    console.print(
        f"\n[green]{success_count} succeeded[/green], [red]{fail_count} failed[/red]"
    )


class McpSynchroCLI:
    """Synchronizes MCP configurations across the AI agent multiverse.

    mcp-synchro maintains one master `mcp.json` file. Change a server here,
    push it, and Claude, Cursor, Codex, and 20+ other agents instantly know about it.
    """

    def push(
        self,
        *agents: str,
        workspace: str | None = None,
        dry_run: bool = False,
        verbose: bool = False,
        probe_tools: bool = False,
        no_resolve_commands: bool = False,
        validate: bool = False,
    ) -> None:
        """Stamps your master config onto every AI agent installed on your machine.

        Args:
            *agents: Specific agent ID(s) or name(s) to target.
            workspace: Path to a project workspace to sync a project-level configuration.
            dry_run: Look but don't touch. We print what would happen without modifying files.
            verbose: Print verbose debug logs.
            probe_tools: Verify that stdio servers do not exceed the tool limit before pushing.
            no_resolve_commands: Do not resolve executable commands on macOS to absolute paths.
            validate: Run post-write validation commands for updated agents.
        """
        _configure_logging(verbose)
        sot_path = get_sot_path()
        console.print(f"[cyan]SoT:[/cyan] {sot_path}")

        if dry_run:
            console.print("[yellow]Dry run mode - no changes will be made[/yellow]\n")

        agent_list = list(agents) if agents else None
        resolve_commands = not no_resolve_commands

        try:
            results = _push(
                agents=agent_list,
                workspace=workspace,
                dry_run=dry_run,
                resolve_commands=resolve_commands,
                probe_tools=probe_tools,
            )
            _print_results(results, "Push Results")

            if validate and not dry_run:
                console.print("\n[cyan]Running validation check...[/cyan]")
                self.doctor(agents=agent_list, verbose=verbose)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

    def sync(
        self,
        *agents: str,
        workspace: str | None = None,
        dry_run: bool = False,
        verbose: bool = False,
        probe_tools: bool = False,
        no_resolve_commands: bool = False,
        validate: bool = False,
    ) -> None:
        """Alias for `push`. Stamps your master config onto the agents."""
        self.push(
            *agents,
            workspace=workspace,
            dry_run=dry_run,
            verbose=verbose,
            probe_tools=probe_tools,
            no_resolve_commands=no_resolve_commands,
            validate=validate,
        )

    def pull_new(
        self,
        *agents: str,
        workspace: str | None = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        """Scavenges for new servers.

        Did you manually install a server directly into Cursor? This command finds it,
        extracts it, and adds it to your master `mcp.json` file.

        Args:
            *agents: Specific agent ID(s) or name(s) to target.
            workspace: Path to a project workspace to sync a project-level configuration.
            dry_run: Look but don't touch.
            verbose: Print verbose debug logs.
        """
        _configure_logging(verbose)
        sot_path = get_sot_path()
        console.print(f"[cyan]SoT:[/cyan] {sot_path}")

        if dry_run:
            console.print("[yellow]Dry run mode - no changes will be made[/yellow]\n")

        agent_list = list(agents) if agents else None

        try:
            results = _pull_new(
                agents=agent_list,
                workspace=workspace,
                dry_run=dry_run,
            )
            _print_results(results, "Pull New Results")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

    def pull_all(
        self,
        *agents: str,
        workspace: str | None = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        """The nuclear option. Rebuilds the master config from scratch.

        Scans every agent, extracts every server, and merges them into a brand new `mcp.json`.

        Args:
            *agents: Specific agent ID(s) or name(s) to target.
            workspace: Path to a project workspace to sync a project-level configuration.
            dry_run: Look but don't touch.
            verbose: Print verbose debug logs.
        """
        _configure_logging(verbose)
        sot_path = get_sot_path()
        console.print(f"[cyan]SoT:[/cyan] {sot_path}")

        if dry_run:
            console.print("[yellow]Dry run mode - no changes will be made[/yellow]\n")

        agent_list = list(agents) if agents else None

        try:
            results = _pull_all(
                agents=agent_list,
                workspace=workspace,
                dry_run=dry_run,
            )
            _print_results(results, "Pull All Results")

            sot = load_sot()
            console.print(f"\n[green]SoT now has {len(sot.servers)} server(s)[/green]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

    def init(
        self,
        *agents: str,
        workspace: str | None = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        """Alias for `pull_all`. Use this when starting fresh."""
        self.pull_all(*agents, workspace=workspace, dry_run=dry_run, verbose=verbose)

    def list(self, verbose: bool = False) -> None:
        """Shows a roster of every AI agent we know about, and whether they exist on your machine.

        Args:
            verbose: Print verbose debug logs.
        """
        _configure_logging(verbose)
        user_agents = get_user_agents_path()
        agent_defs = load_all_agent_defs(
            user_agents_path=user_agents if user_agents.exists() else None
        )

        table = Table(title="Known MCP Agents")
        table.add_column("Agent", style="cyan", no_wrap=True)
        table.add_column("Format", style="yellow")
        table.add_column("Path", style="dim")
        table.add_column("Status", style="bold")

        found_count = 0
        for agent in agent_defs:
            path = agent.resolve_path()
            if path and path.exists():
                status = "[green]Found[/green]"
                found_count += 1
            elif path:
                status = "[dim]Not found[/dim]"
            else:
                status = "[dim]N/A (platform)[/dim]"

            table.add_row(
                agent.name,
                agent.config_format.upper(),
                str(path) if path else "-",
                status,
            )

        console.print(table)
        console.print(
            f"\n[green]{found_count}[/green] of {len(agent_defs)} agents found"
        )
        console.print(f"[cyan]SoT:[/cyan] {get_sot_path()}")
        console.print(f"[cyan]Config dir:[/cyan] {get_config_dir()}")

    def show(self, verbose: bool = False) -> None:
        """Prints a human-readable table of your master config.

        Args:
            verbose: Print verbose debug logs.
        """
        _configure_logging(verbose)
        sot_path = get_sot_path()
        console.print(f"[cyan]SoT:[/cyan] {sot_path}\n")

        sot = load_sot()
        if not sot.servers:
            console.print(
                "[yellow]SoT is empty. Run 'init' or 'pull_all' first.[/yellow]"
            )
            return

        table = Table(title=f"SoT: {len(sot.servers)} MCP Server(s)")
        table.add_column("Server", style="cyan", no_wrap=True)
        table.add_column("Transport", style="yellow")
        table.add_column("Command/URL", style="green")
        table.add_column("Status")

        for name, server in sorted(sot.servers.items()):
            transport = "URL" if server.url else "stdio"
            cmd_or_url = server.url or server.command or "-"
            status = (
                "[red]disabled[/red]"
                if server.is_disabled()
                else "[green]enabled[/green]"
            )
            table.add_row(name, transport, cmd_or_url, status)

        console.print(table)

    def dump(self, verbose: bool = False) -> None:
        """Spits out the master config as raw JSON.

        Great for piping into `jq` or dumping into another tool.

        Args:
            verbose: Print verbose debug logs.
        """
        _configure_logging(verbose)
        sot = load_sot()
        print(json.dumps({"mcpServers": sot.to_dict()}, indent=2, ensure_ascii=False))

    def migrate(self, source_agent: str, to: str) -> None:
        """Migrates configurations from one agent to another (one-shot).

        Args:
            source_agent: The name or ID of the legacy agent.
            to: The name or ID of the successor agent.
        """
        # Load agent definitions
        user_agents = get_user_agents_path()
        agent_defs = load_all_agent_defs(
            user_agents_path=user_agents if user_agents.exists() else None
        )

        source = next(
            (a for a in agent_defs if a.id == source_agent or a.name == source_agent),
            None,
        )
        target = next((a for a in agent_defs if a.id == to or a.name == to), None)

        if not source:
            console.print(f"[red]Error: Source agent '{source_agent}' not found.[/red]")
            sys.exit(1)
        if not target:
            console.print(f"[red]Error: Target agent '{to}' not found.[/red]")
            sys.exit(1)

        source_path = source.resolve_path()
        target_path = target.resolve_path()

        if not source_path or not source_path.exists():
            console.print(
                f"[yellow]No legacy config file found for {source.name} at {source_path}. Nothing to migrate.[/yellow]"
            )
            return

        console.print(
            f"[cyan]Migrating {source.name} ({source_path}) -> {target.name} ({target_path})...[/cyan]"
        )

        try:
            from mcp_synchro.readers import read_agent_config
            from mcp_synchro.writers import write_agent_config

            _, mcp_config = read_agent_config(source_path, source)
            if not mcp_config or not mcp_config.servers:
                console.print(
                    f"[yellow]No MCP servers found in legacy config {source_path}.[/yellow]"
                )
                return

            target_data = {}
            if target_path and target_path.exists():
                try:
                    from mcp_synchro.readers import read_json, read_toml

                    if target.is_toml:
                        target_data = read_toml(target_path)
                    else:
                        target_data = read_json(target_path)
                except Exception:
                    pass

            if target_path:
                write_agent_config(target_path, target_data, mcp_config, target)
                console.print(
                    f"[green]Successfully migrated {len(mcp_config.servers)} servers to {target.name} at {target_path}.[/green]"
                )

                backup_path = source_path.with_suffix(".backup")
                source_path.rename(backup_path)
                console.print(f"[dim]Legacy config backed up to {backup_path}[/dim]")
            else:
                console.print(
                    f"[red]Error: Could not resolve path for target agent {target.name}.[/red]"
                )
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]Migration failed: {e}[/red]")
            sys.exit(1)

    def doctor(self, agents: list[str] | None = None, verbose: bool = False) -> None:
        """Runs each agent's validation command to report health and configuration status.

        Args:
            agents: Specific agent ID(s) to check. If None, checks all installed/supported agents.
            verbose: Print verbose output.
        """
        _configure_logging(verbose)
        import subprocess

        user_agents = get_user_agents_path()
        agent_defs = load_all_agent_defs(
            user_agents_path=user_agents if user_agents.exists() else None
        )

        if agents:
            agent_defs = [a for a in agent_defs if a.id in agents or a.name in agents]

        table = Table(title="MCP Synchro Doctor Report")
        table.add_column("Agent", style="cyan")
        table.add_column("Validation Command", style="yellow")
        table.add_column("Status", style="bold")
        table.add_column("Details")

        for agent in agent_defs:
            path = agent.resolve_path()
            if not path or not path.exists():
                continue

            if not agent.post_write_validate_cmd:
                table.add_row(
                    agent.name,
                    "-",
                    "[yellow]No validation cmd[/yellow]",
                    "Skips validation",
                )
                continue

            cmd = agent.post_write_validate_cmd
            cmd_str = " ".join(cmd)
            try:
                binary = shutil.which(cmd[0])
                if not binary:
                    table.add_row(
                        agent.name,
                        cmd_str,
                        "[red]Binary missing[/red]",
                        f"Executable '{cmd[0]}' not in PATH",
                    )
                    continue

                full_cmd = [binary, *cmd[1:]]
                proc = subprocess.run(
                    full_cmd,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
                if proc.returncode == 0:
                    output = proc.stdout.strip()
                    details = output.replace("\n", " | ")[:60]
                    table.add_row(agent.name, cmd_str, "[green]OK[/green]", details)
                else:
                    err_msg = (
                        (proc.stderr or proc.stdout).strip().replace("\n", " | ")[:60]
                    )
                    table.add_row(
                        agent.name,
                        cmd_str,
                        "[red]FAIL[/red]",
                        f"Exit code {proc.returncode}: {err_msg}",
                    )
            except subprocess.TimeoutExpired:
                table.add_row(
                    agent.name,
                    cmd_str,
                    "[red]TIMEOUT[/red]",
                    "Command timed out after 5 seconds",
                )
            except Exception as e:
                table.add_row(agent.name, cmd_str, "[red]ERROR[/red]", str(e))

        console.print(table)

    def agy_sync(
        self,
        dry_run: bool = False,
        verbose: bool = False,
        probe_tools: bool = False,
        no_resolve_commands: bool = False,
        validate: bool = False,
    ) -> None:
        """Convenience command targeting the 3 Antigravity products at once."""
        self.push(
            "antigravity-desktop",
            "antigravity-ide",
            "antigravity-cli",
            dry_run=dry_run,
            verbose=verbose,
            probe_tools=probe_tools,
            no_resolve_commands=no_resolve_commands,
            validate=validate,
        )


def main() -> None:
    """Lights the fire."""
    fire.Fire(McpSynchroCLI)


if __name__ == "__main__":
    main()
