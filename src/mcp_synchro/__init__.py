# this_file: src/mcp_synchro/__init__.py
"""mcp-synchro: Synchronize MCP server configurations across AI agents."""

try:
    from mcp_synchro._version import __version__, __version_tuple__
except ImportError:
    __version__ = "0.0.0"
    __version_tuple__ = (0, 0, 0)
