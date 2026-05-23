# this_file: src/mcp_synchro/prober.py
"""Probes MCP servers to count the number of tools they expose."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

from loguru import logger

from mcp_synchro.models import McpServer


def probe_tool_count(server: McpServer) -> int | None:
    """Probes the MCP server to count its tools.

    Runs the stdio server, performs the JSON-RPC initialize handshake,
    requests the list of tools, and returns the tool count.
    Returns None if the server is HTTP/SSE, if select is not supported (Windows),
    or if the handshake fails.
    """
    if server.is_http:
        # HTTP/SSE is not easily probed; return None
        return None

    if not server.command:
        return None

    if sys.platform == "win32":
        # Windows select does not support pipes, so skip to avoid blocking indefinitely
        return None

    import select

    cmd = [server.command] + (server.args or [])
    # If command is not absolute and we are on darwin, resolve it
    if not server.command.startswith(("/", ".")):
        resolved = shutil.which(server.command)
        if resolved:
            cmd[0] = resolved

    env = server.env or {}

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=server.cwd,
            env=env,
        )
    except Exception as e:
        logger.debug(f"Failed to start process for probing {server.command}: {e}")
        return None

    try:
        # 1. Send initialize request
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-synchro-probe", "version": "0.4.0"},
            },
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()

        # Read initialize response with a 2.0s timeout
        r, _, _ = select.select([proc.stdout], [], [], 2.0)
        if not r:
            logger.debug(
                f"Timeout waiting for initialize response from {server.command}"
            )
            proc.terminate()
            return None
        line = proc.stdout.readline()
        if not line:
            proc.terminate()
            return None

        # 2. Send initialized notification
        init_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        proc.stdin.write(json.dumps(init_notif) + "\n")
        proc.stdin.flush()

        # 3. Send tools/list request
        tools_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        proc.stdin.write(json.dumps(tools_req) + "\n")
        proc.stdin.flush()

        # Read tools/list response with a 2.0s timeout
        r, _, _ = select.select([proc.stdout], [], [], 2.0)
        if not r:
            logger.debug(
                f"Timeout waiting for tools/list response from {server.command}"
            )
            proc.terminate()
            return None
        line = proc.stdout.readline()
        if not line:
            proc.terminate()
            return None

        data = json.loads(line)
        result = data.get("result", {})
        tools = result.get("tools", [])
        return len(tools)
    except Exception as e:
        logger.debug(f"Error during probing {server.command}: {e}")
        return None
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except Exception:
            pass
