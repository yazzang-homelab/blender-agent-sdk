"""blender-agent: drive Blender from AI agents through a plain Python SDK (MCP server optional)."""

from .client import BlenderAgentError, BlenderNotFound, BlenderSession, RemoteError, RequestTooLarge, SessionLost, find_blender
from .tools import TOOLS, anthropic_tools, dispatch, openai_tools

__version__ = "0.2.0"

__all__ = [
    "TOOLS",
    "BlenderAgentError",
    "BlenderNotFound",
    "BlenderSession",
    "RemoteError",
    "RequestTooLarge",
    "SessionLost",
    "anthropic_tools",
    "dispatch",
    "find_blender",
    "openai_tools",
]
