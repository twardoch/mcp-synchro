# this_file: src/mcp_synchro/cli.py
"""The command line interface. Powered by Google Fire and heavily decorated by Rich."""

from __future__ import annotations

import json
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

    def push(self, dry_run: bool = False, verbose: bool = False) -> None:
        """Stamps your master config onto every AI agent installed on your machine.

        Args:
            dry_run: Look but don\'t touch. We print what would happen without modifying files.
            verbose: Print verbose debug logs.
        """
        _configure_logging(verbose)
        sot_path = get_sot_path()
        console.print(f"[cyan]SoT:[/cyan] {sot_path}")

        if dry_run:
            console.print("[yellow]Dry run mode - no changes will be made[/yellow]\n")

        results = _push(dry_run=dry_run)
        _print_results(results, "Push Results")

    def sync(self, dry_run: bool = False, verbose: bool = False) -> None:
        """Alias for `push`. Stamps your master config onto the agents."""
        self.push(dry_run=dry_run, verbose=verbose)

    def pull_new(self, dry_run: bool = False, verbose: bool = False) -> None:
        """Scavenges for new servers.

        Did you manually install a server directly into Cursor? This command finds it,
        extracts it, and adds it to your master `mcp.json` file.

        Args:
            dry_run: Look but don\'t touch.
            verbose: Print verbose debug logs.
        """
        _configure_logging(verbose)
        sot_path = get_sot_path()
        console.print(f"[cyan]SoT:[/cyan] {sot_path}")

        if dry_run:
            console.print("[yellow]Dry run mode - no changes will be made[/yellow]\n")

        results = _pull_new(dry_run=dry_run)
        _print_results(results, "Pull New Results")

    def pull_all(self, dry_run: bool = False, verbose: bool = False) -> None:
        """The nuclear option. Rebuilds the master config from scratch.

        Scans every agent, extracts every server, and merges them into a brand new `mcp.json`.

        Args:
            dry_run: Look but don\'t touch.
            verbose: Print verbose debug logs.
        """
        _configure_logging(verbose)
        sot_path = get_sot_path()
        console.print(f"[cyan]SoT:[/cyan] {sot_path}")

        if dry_run:
            console.print("[yellow]Dry run mode - no changes will be made[/yellow]\n")

        results = _pull_all(dry_run=dry_run)
        _print_results(results, "Pull All Results")

        sot = load_sot()
        console.print(f"\n[green]SoT now has {len(sot.servers)} server(s)[/green]")

    def init(self, dry_run: bool = False, verbose: bool = False) -> None:
        """Alias for `pull_all`. Use this when starting fresh."""
        self.pull_all(dry_run=dry_run, verbose=verbose)

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


def main() -> None:
    """Lights the fire."""
    fire.Fire(McpSynchroCLI)


if __name__ == "__main__":
    main()
