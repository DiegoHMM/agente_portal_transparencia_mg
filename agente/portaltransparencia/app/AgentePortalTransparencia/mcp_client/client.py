import os
import logging
from mcp.client.streamable_http import streamable_http_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

# MCP do Portal da Transparência MG rodando localmente (server.py com DATABRICKS_APP_PORT=8001)
PORTAL_MCP_ENDPOINT = os.getenv("PORTAL_MCP_URL", "http://localhost:8001/mcp")

def get_streamable_http_mcp_client() -> MCPClient:
    """Returns an MCP Client compatible with Strands"""
    return MCPClient(lambda: streamable_http_client(PORTAL_MCP_ENDPOINT))
