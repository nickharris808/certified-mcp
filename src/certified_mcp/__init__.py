"""certified-mcp — an MCP server giving AI agents a verifier they cannot argue with."""
from .server import (  # noqa: F401
    HANDLERS, PROTOCOL_VERSION, SERVER_NAME, SERVER_VERSION, TOOLS, handle, main, serve,
)

__version__ = "1.0.0"
__all__ = ["TOOLS", "HANDLERS", "handle", "serve", "main", "PROTOCOL_VERSION",
           "SERVER_NAME", "SERVER_VERSION", "__version__"]
