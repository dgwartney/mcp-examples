"""
Command-line application for the MCP client.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Basic usage with required API key:
        $ python -m mcp_examples.cli --api-key YOUR_API_KEY

    Custom name and server URL:
        $ python -m mcp_examples.cli --api-key YOUR_API_KEY --name Alice --url http://localhost:8000/mcp
"""

import argparse
import asyncio

from mcp_examples.client import MCPClient


class MCPClientApp:
    """
    Command-line application for the MCP client.

    Handles argument parsing and execution flow for the MCP client.
    Provides a CLI interface for connecting to MCP servers and calling tools.

    Attributes:
        parser (argparse.ArgumentParser): Command-line argument parser.
    """

    def __init__(self):
        """Initialize the CLI application with argument parser."""
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """
        Create and configure the argument parser.

        Returns:
            argparse.ArgumentParser: Configured parser with all CLI arguments.
        """
        parser = argparse.ArgumentParser(
            description="FastMCP client for calling remote tools",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s --api-key abc123xyz
  %(prog)s --api-key abc123xyz --name Alice
  %(prog)s --api-key abc123xyz --url http://localhost:8000/mcp --name Bob
            """
        )
        parser.add_argument(
            "--api-key",
            required=True,
            help="API key for authentication (required)"
        )
        parser.add_argument(
            "--name",
            default="Ford",
            help="Name to greet (default: Ford)"
        )
        parser.add_argument(
            "--url",
            default="https://my-service.ngrok.app/mcp",
            help="MCP server URL (default: https://my-service.ngrok.app/mcp)"
        )
        return parser

    def run(self) -> None:
        """
        Parse arguments and run the client.

        Parses command-line arguments, creates an MCPClient instance,
        and calls the greet tool. Handles and displays any errors that occur.
        """
        args = self.parser.parse_args()
        client = MCPClient(args.url, args.api_key)

        try:
            asyncio.run(client.greet(args.name))
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Entry point for the mcp-client console script."""
    app = MCPClientApp()
    app.run()


if __name__ == "__main__":
    main()
