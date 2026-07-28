"""
Unit tests for mcp_server_kit.client

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server_kit.client import MCPClient


class TestMCPClient:
    """Test suite for MCPClient class."""

    @pytest.fixture
    def client(self):
        """Create an MCPClient instance."""
        return MCPClient(
            url="http://test-server.example.com/mcp",
            api_key="test-api-key-123"
        )

    def test_init(self):
        """Test MCPClient initialization."""
        url = "http://example.com/mcp"
        api_key = "my-api-key"

        client = MCPClient(url, api_key)

        assert client.url == url
        assert client.api_key == api_key

    def test_init_different_urls(self):
        """Test MCPClient with various URL formats."""
        test_cases = [
            "http://localhost:8000/mcp",
            "https://api.example.com/mcp",
            "http://192.168.1.1:3000/mcp",
            "https://subdomain.example.org/api/mcp"
        ]

        for url in test_cases:
            client = MCPClient(url, "key")
            assert client.url == url

    @pytest.mark.asyncio
    async def test_call_tool_success(self, client):
        """Test successful tool invocation."""
        mock_result = {"content": [{"type": "text", "text": "Hello, World!"}]}

        with patch("mcp_server_kit.client.StreamableHttpTransport") as mock_transport_class, \
             patch("mcp_server_kit.client.Client") as mock_client_class:

            # Setup mocks
            mock_transport = MagicMock()
            mock_transport_class.return_value = mock_transport

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.call_tool = AsyncMock(return_value=mock_result)
            mock_client_class.return_value = mock_client_instance

            # Execute
            result = await client.call_tool("test_tool", {"arg1": "value1"})

            # Verify
            assert result == mock_result
            mock_transport_class.assert_called_once_with(
                "http://test-server.example.com/mcp",
                headers={"X-API-Key": "test-api-key-123"}
            )
            mock_client_class.assert_called_once_with(mock_transport)
            mock_client_instance.call_tool.assert_called_once_with(
                "test_tool",
                {"arg1": "value1"}
            )

    @pytest.mark.asyncio
    async def test_call_tool_with_different_arguments(self, client):
        """Test call_tool with various argument types."""
        test_cases = [
            ("tool1", {"name": "Alice"}),
            ("tool2", {"count": 42, "enabled": True}),
            ("tool3", {}),
            ("tool4", {"data": [1, 2, 3], "metadata": {"key": "value"}})
        ]

        for tool_name, arguments in test_cases:
            with patch("mcp_server_kit.client.StreamableHttpTransport"), \
                 patch("mcp_server_kit.client.Client") as mock_client_class:

                mock_client_instance = MagicMock()
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_client_instance.call_tool = AsyncMock(return_value={"success": True})
                mock_client_class.return_value = mock_client_instance

                result = await client.call_tool(tool_name, arguments)

                assert result == {"success": True}
                mock_client_instance.call_tool.assert_called_once_with(tool_name, arguments)

    @pytest.mark.asyncio
    async def test_call_tool_connection_error(self, client):
        """Test call_tool handles connection errors."""
        with patch("mcp_server_kit.client.StreamableHttpTransport"), \
             patch("mcp_server_kit.client.Client") as mock_client_class:

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(side_effect=ConnectionError("Connection failed"))
            mock_client_class.return_value = mock_client_instance

            with pytest.raises(ConnectionError, match="Connection failed"):
                await client.call_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_tool_error(self, client):
        """Test call_tool handles tool execution errors."""
        with patch("mcp_server_kit.client.StreamableHttpTransport"), \
             patch("mcp_server_kit.client.Client") as mock_client_class:

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.call_tool = AsyncMock(side_effect=Exception("Tool execution failed"))
            mock_client_class.return_value = mock_client_instance

            with pytest.raises(Exception, match="Tool execution failed"):
                await client.call_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_greet_success(self, client, capsys):
        """Test greet method with successful response."""
        mock_result = {"content": [{"type": "text", "text": "Hello, Bob!"}]}

        with patch.object(client, 'call_tool', new_callable=AsyncMock) as mock_call_tool:
            mock_call_tool.return_value = mock_result

            await client.greet("Bob")

            mock_call_tool.assert_called_once_with("greet", {"name": "Bob"})

            captured = capsys.readouterr()
            assert str(mock_result) in captured.out

    @pytest.mark.asyncio
    async def test_greet_with_different_names(self, client, capsys):
        """Test greet with various names."""
        test_names = ["Alice", "Bob", "Charlie", "世界", "123"]

        for name in test_names:
            with patch.object(client, 'call_tool', new_callable=AsyncMock) as mock_call_tool:
                mock_result = {"content": [{"type": "text", "text": f"Hello, {name}!"}]}
                mock_call_tool.return_value = mock_result

                await client.greet(name)

                mock_call_tool.assert_called_once_with("greet", {"name": name})

    @pytest.mark.asyncio
    async def test_greet_error_handling(self, client):
        """Test greet handles errors from call_tool."""
        with patch.object(client, 'call_tool', new_callable=AsyncMock) as mock_call_tool:
            mock_call_tool.side_effect = Exception("API error")

            with pytest.raises(Exception, match="API error"):
                await client.greet("Test")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_tool_name(self):
        """Test call_tool with empty tool name."""
        client = MCPClient("http://test.com/mcp", "key")

        with patch("mcp_server_kit.client.StreamableHttpTransport"), \
             patch("mcp_server_kit.client.Client") as mock_client_class:

            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.call_tool = AsyncMock(return_value={"result": "ok"})
            mock_client_class.return_value = mock_client_instance

            result = await client.call_tool("", {})
            assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_special_characters_in_name(self, capsys):
        """Test greet with special characters in name."""
        client = MCPClient("http://test.com/mcp", "key")

        special_names = ["O'Brien", "José", "Anna-Marie", "李明", "user@example.com"]

        for name in special_names:
            with patch.object(client, 'call_tool', new_callable=AsyncMock) as mock_call_tool:
                mock_call_tool.return_value = {"content": [{"type": "text", "text": f"Hello, {name}!"}]}

                await client.greet(name)

                mock_call_tool.assert_called_once_with("greet", {"name": name})

    def test_very_long_api_key(self):
        """Test client with very long API key."""
        long_key = "a" * 1000
        client = MCPClient("http://test.com/mcp", long_key)

        assert client.api_key == long_key

    def test_unusual_url_formats(self):
        """Test client with various unusual but valid URLs."""
        unusual_urls = [
            "http://localhost/mcp",
            "https://example.com:8080/api/v1/mcp",
            "http://192.168.1.1/mcp",
            "https://sub.domain.example.co.uk/mcp"
        ]

        for url in unusual_urls:
            client = MCPClient(url, "key")
            assert client.url == url
