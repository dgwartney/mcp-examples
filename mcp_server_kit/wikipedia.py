"""
FastMCP Server with Wikipedia search and lookup tools.

Demonstrates how to build an MCP server by subclassing
``AuthenticatedMCPServer`` and registering tools that query the
Wikipedia REST API.

Author:
    David Gwartney <david.gwartney@gmail.com>

Example:
    Run the server directly (stdio transport):
        $ uv run -m mcp_server_kit.wikipedia

    Run as HTTP server:
        $ uv run -m mcp_server_kit.wikipedia --transport streamable-http --port 8001

    Run with custom database path:
        $ MCP_DB_PATH=/var/data/keys.db uv run -m mcp_server_kit.wikipedia
"""

import re
from typing import Optional
from urllib.parse import quote

import httpx
from fastmcp.exceptions import ToolError

from mcp_server_kit.base import AuthenticatedMCPServer, lazy_module_instances

_BASE_URL = "https://en.wikipedia.org"
_USER_AGENT = "mcp-wikipedia-example/1.0"


class WikipediaMCPServer(AuthenticatedMCPServer):
    """
    MCP server with Wikipedia search and lookup tools.

    Exposes four tools backed by the Wikipedia REST API:
    - search_pages: full-text article search
    - search_titles: autocomplete-style title search
    - get_page_summary: article summary and extract
    - get_related_pages: articles related to a given page
    """

    def __init__(self, db_path: Optional[str] = None):
        self._http = httpx.Client(
            base_url=_BASE_URL,
            headers={"User-Agent": _USER_AGENT},
            timeout=10.0,
            follow_redirects=True,
        )
        super().__init__(name="WikipediaMCP", db_path=db_path)

    def _strip_html(self, text: str) -> str:
        return re.sub(r"<[^>]+>", "", text)

    def _register_tools(self) -> None:
        """Register Wikipedia MCP tools."""

        @self.mcp.tool(
            description=(
                "Full-text search of Wikipedia articles. Returns matching pages "
                "with titles, short descriptions, and text excerpts."
            )
        )
        def search_pages(query: str, limit: int = 10) -> list[dict]:
            """
            Search Wikipedia articles by full-text query.

            Args:
                query: Search terms.
                limit: Maximum number of results (1-100, default 10).

            Returns:
                List of dicts with keys: id, key, title, excerpt,
                description, thumbnail_url.
            """
            limit = max(1, min(limit, 100))
            try:
                resp = self._http.get(
                    "/w/rest.php/v1/search/page",
                    params={"q": query, "limit": limit},
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ToolError(
                    f"Wikipedia search failed: HTTP {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                raise ToolError(f"Wikipedia search request error: {exc}") from exc

            pages = resp.json().get("pages", [])
            return [
                {
                    "id": p.get("id"),
                    "key": p.get("key"),
                    "title": p.get("title"),
                    "excerpt": self._strip_html(p.get("excerpt") or ""),
                    "description": p.get("description") or "",
                    "thumbnail_url": (p.get("thumbnail") or {}).get("url") or "",
                }
                for p in pages
            ]

        @self.mcp.tool(
            description=(
                "Autocomplete-style Wikipedia title search. Best for finding "
                "the exact page title to use with get_page_summary."
            )
        )
        def search_titles(query: str, limit: int = 10) -> list[dict]:
            """
            Search Wikipedia page titles by prefix or keyword.

            Args:
                query: Title search terms.
                limit: Maximum number of results (1-100, default 10).

            Returns:
                List of dicts with keys: id, key, title, excerpt,
                description, thumbnail_url.
            """
            limit = max(1, min(limit, 100))
            try:
                resp = self._http.get(
                    "/w/rest.php/v1/search/title",
                    params={"q": query, "limit": limit},
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ToolError(
                    f"Wikipedia title search failed: HTTP {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                raise ToolError(f"Wikipedia title search request error: {exc}") from exc

            pages = resp.json().get("pages", [])
            return [
                {
                    "id": p.get("id"),
                    "key": p.get("key"),
                    "title": p.get("title"),
                    "excerpt": self._strip_html(p.get("excerpt") or ""),
                    "description": p.get("description") or "",
                    "thumbnail_url": (p.get("thumbnail") or {}).get("url") or "",
                }
                for p in pages
            ]

        @self.mcp.tool(
            description=(
                "Fetch a Wikipedia article's summary: plain-text extract, "
                "short description, and link to the full article."
            )
        )
        def get_page_summary(title: str) -> dict:
            """
            Retrieve a Wikipedia article summary by title.

            Args:
                title: Exact Wikipedia page title (e.g. 'Albert_Einstein').
                       Spaces and underscores are both accepted.

            Returns:
                Dict with keys: title, description, extract, url,
                thumbnail_url.

            Raises:
                ToolError: If the page is not found or the request fails.
            """
            encoded = quote(title.replace(" ", "_"), safe="")
            try:
                resp = self._http.get(f"/api/rest_v1/page/summary/{encoded}")
                if resp.status_code == 404:
                    raise ToolError(f"Wikipedia page not found: '{title}'")
                resp.raise_for_status()
            except ToolError:
                raise
            except httpx.HTTPStatusError as exc:
                raise ToolError(
                    f"Wikipedia summary failed: HTTP {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                raise ToolError(f"Wikipedia summary request error: {exc}") from exc

            data = resp.json()
            return {
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "extract": data.get("extract", ""),
                "url": (data.get("content_urls") or {})
                .get("desktop", {})
                .get("page", ""),
                "thumbnail_url": (data.get("thumbnail") or {}).get("source", ""),
            }

        @self.mcp.tool(
            description=(
                "Find Wikipedia articles semantically related to a given page title. "
                "Uses 'morelike' search to surface topically similar articles."
            )
        )
        def get_related_pages(title: str, limit: int = 10) -> list[dict]:
            """
            Retrieve Wikipedia articles semantically related to a given page.

            Uses the MediaWiki Action API's ``morelike:`` operator, which
            returns articles with similar content to the specified page.

            Args:
                title: Wikipedia page title to find related articles for.
                limit: Maximum number of results to return (1-50, default 10).

            Returns:
                List of dicts with keys: title, excerpt, url.

            Raises:
                ToolError: If the request fails.
            """
            limit = max(1, min(limit, 50))
            try:
                resp = self._http.get(
                    "/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": f"morelike:{title}",
                        "srlimit": limit,
                        "srprop": "snippet",
                        "format": "json",
                    },
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ToolError(
                    f"Wikipedia related pages failed: HTTP {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                raise ToolError(
                    f"Wikipedia related pages request error: {exc}"
                ) from exc

            results = resp.json().get("query", {}).get("search", [])
            return [
                {
                    "title": r.get("title", ""),
                    "excerpt": self._strip_html(r.get("snippet") or ""),
                    "url": (
                        f"https://en.wikipedia.org/wiki/"
                        f"{quote(r.get('title', '').replace(' ', '_'), safe='')}"
                    ),
                }
                for r in results
            ]


# Lazy module-level ``server`` / ``mcp`` — built on first attribute access, not
# on import, so ``import mcp_server_kit.wikipedia`` performs no database I/O.
__getattr__ = lazy_module_instances(WikipediaMCPServer)

if __name__ == "__main__":
    WikipediaMCPServer().main()
