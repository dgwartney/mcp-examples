"""
FastMCP Client for calling remote MCP tools with API key authentication.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from typing import Any, Dict

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


class MCPClient:
    """
    Client for connecting to and calling tools on a remote MCP server.

    This class handles the connection setup, authentication via API keys,
    and tool invocation. It uses StreamableHttpTransport to pass custom
    headers for authentication.

    Attributes:
        url (str): The MCP server URL endpoint.
        api_key (str): API key for authentication via X-API-Key header.
    """

    def __init__(self, url: str, api_key: str):
        """
        Initialize the MCP client.

        Args:
            url (str): The MCP server URL (e.g., "http://localhost:8000/mcp").
            api_key (str): API key for authentication.
        """
        self.url = url
        self.api_key = api_key

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on the remote MCP server.

        Establishes a connection to the MCP server using StreamableHttpTransport
        with the API key in the X-API-Key header, then invokes the specified tool.

        Args:
            tool_name (str): Name of the tool to call on the server.
            arguments (Dict[str, Any]): Dictionary of arguments to pass to the tool.

        Returns:
            Any: The result returned by the tool.

        Raises:
            Exception: If the connection fails or the tool invocation encounters an error.
        """
        transport = StreamableHttpTransport(
            self.url,
            headers={"X-API-Key": self.api_key}
        )
        client = Client(transport)
        async with client:
            result = await client.call_tool(tool_name, arguments)
            return result

    async def greet(self, name: str) -> None:
        """
        Call the 'greet' tool on the server and print the result.

        This is a convenience method for calling the greet tool specifically.

        Args:
            name (str): The name to pass to the greet tool.

        Raises:
            Exception: If the tool call fails.
        """
        result = await self.call_tool("greet", {"name": name})
        print(result)
