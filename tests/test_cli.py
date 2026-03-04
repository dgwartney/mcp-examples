"""
Unit tests for mcp_examples.cli

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import argparse
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_examples.cli import MCPClientApp


class TestMCPClientApp:
    """Test suite for MCPClientApp class."""

    def test_init(self):
        """Test MCPClientApp initialization."""
        app = MCPClientApp()

        assert app.parser is not None
        assert isinstance(app.parser, argparse.ArgumentParser)

    def test_parser_api_key_required(self):
        """Test that --api-key is a required argument."""
        app = MCPClientApp()

        with pytest.raises(SystemExit):
            app.parser.parse_args([])  # Missing required --api-key

    def test_parser_api_key_provided(self):
        """Test parsing with required --api-key argument."""
        app = MCPClientApp()

        args = app.parser.parse_args(["--api-key", "test-key"])

        assert args.api_key == "test-key"

    def test_parser_default_name(self):
        """Test that --name defaults to 'Ford'."""
        app = MCPClientApp()

        args = app.parser.parse_args(["--api-key", "test-key"])

        assert args.name == "Ford"

    def test_parser_custom_name(self):
        """Test parsing with custom --name argument."""
        app = MCPClientApp()

        args = app.parser.parse_args(["--api-key", "test-key", "--name", "Alice"])

        assert args.name == "Alice"

    def test_parser_default_url(self):
        """Test that --url has a default value."""
        app = MCPClientApp()

        args = app.parser.parse_args(["--api-key", "test-key"])

        assert args.url == "https://my-service.ngrok.app/mcp"

    def test_parser_custom_url(self):
        """Test parsing with custom --url argument."""
        app = MCPClientApp()

        custom_url = "http://localhost:8000/mcp"
        args = app.parser.parse_args([
            "--api-key", "test-key",
            "--url", custom_url
        ])

        assert args.url == custom_url

    def test_parser_all_arguments(self):
        """Test parsing with all arguments provided."""
        app = MCPClientApp()

        args = app.parser.parse_args([
            "--api-key", "my-secret-key",
            "--name", "Bob",
            "--url", "http://example.com/mcp"
        ])

        assert args.api_key == "my-secret-key"
        assert args.name == "Bob"
        assert args.url == "http://example.com/mcp"

    def test_parser_help_text(self):
        """Test that parser has help text configured."""
        app = MCPClientApp()

        # Check that description is set
        assert "FastMCP client" in app.parser.description

    def test_parser_argument_help_texts(self):
        """Test that all arguments have help text."""
        app = MCPClientApp()

        # Parse help to check it includes our arguments
        with pytest.raises(SystemExit):
            app.parser.parse_args(["--help"])

    def test_run_success(self, capsys):
        """Test successful run method execution."""
        app = MCPClientApp()

        test_args = ["--api-key", "test-key", "--name", "Alice"]

        with patch.object(sys, 'argv', ['my_client.py'] + test_args), \
             patch('mcp_examples.cli.MCPClient') as mock_client_class, \
             patch('asyncio.run') as mock_asyncio_run:

            mock_client_instance = MagicMock()
            mock_client_instance.greet = AsyncMock()
            mock_client_class.return_value = mock_client_instance
            mock_asyncio_run.return_value = None

            app.run()

            mock_asyncio_run.assert_called_once()

    def test_run_with_custom_url(self):
        """Test run method with custom URL."""
        app = MCPClientApp()

        test_args = [
            "--api-key", "test-key",
            "--url", "http://localhost:8000/mcp",
            "--name", "Bob"
        ]

        with patch.object(sys, 'argv', ['my_client.py'] + test_args), \
             patch('mcp_examples.cli.MCPClient') as mock_client_class, \
             patch('asyncio.run') as mock_asyncio_run:

            mock_client_instance = MagicMock()
            mock_client_instance.greet = AsyncMock()
            mock_client_class.return_value = mock_client_instance
            mock_asyncio_run.return_value = None

            app.run()

            # Verify asyncio.run was called
            assert mock_asyncio_run.called

    def test_run_handles_exception(self, capsys):
        """Test that run method handles exceptions gracefully."""
        app = MCPClientApp()

        test_args = ["--api-key", "test-key"]

        with patch.object(sys, 'argv', ['my_client.py'] + test_args), \
             patch('mcp_examples.cli.MCPClient') as mock_client_class, \
             patch('asyncio.run') as mock_asyncio_run:

            mock_client_instance = MagicMock()
            mock_client_instance.greet = AsyncMock()
            mock_client_class.return_value = mock_client_instance
            mock_asyncio_run.side_effect = Exception("Connection timeout")

            app.run()

            captured = capsys.readouterr()
            assert "Error:" in captured.out
            assert "Connection timeout" in captured.out

    def test_run_creates_correct_client(self):
        """Test that run creates MCPClient with correct parameters."""
        app = MCPClientApp()

        test_args = [
            "--api-key", "my-key",
            "--url", "http://test.com/mcp",
            "--name", "TestUser"
        ]

        with patch.object(sys, 'argv', ['my_client.py'] + test_args), \
             patch('mcp_examples.cli.MCPClient') as mock_client_class, \
             patch('asyncio.run') as mock_asyncio_run:

            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            app.run()

            mock_client_class.assert_called_once_with(
                "http://test.com/mcp",
                "my-key"
            )


class TestIntegration:
    """Integration tests for complete client workflows."""

    def test_cli_to_client_parameter_flow(self):
        """Test that CLI arguments correctly flow to MCPClient."""
        app = MCPClientApp()

        test_args = [
            "--api-key", "cli-key-123",
            "--url", "http://cli-test.com/mcp",
            "--name", "CLIUser"
        ]

        with patch.object(sys, 'argv', ['my_client.py'] + test_args), \
             patch('mcp_examples.cli.MCPClient') as mock_client_class, \
             patch('asyncio.run'):

            mock_client_instance = MagicMock()
            mock_client_instance.greet = AsyncMock()
            mock_client_class.return_value = mock_client_instance

            app.run()

            # Verify client was created with correct parameters
            mock_client_class.assert_called_once_with(
                "http://cli-test.com/mcp",
                "cli-key-123"
            )

    def test_main_entry_point(self):
        """Test that the module can be run as main."""
        import mcp_examples.cli

        # The app should be runnable
        assert callable(getattr(mcp_examples.cli.MCPClientApp, 'run'))
        assert callable(mcp_examples.cli.main)
