"""
Unit tests for mcp_server_kit.wikipedia

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastmcp.exceptions import ToolError

from mcp_server_kit.database import DatabaseManager
from mcp_server_kit.wikipedia import WikipediaMCPServer


def _tool_fn(server, name):
    """Extract the raw callable from a registered FastMCP tool."""
    return server.mcp._tool_manager._tools[name].fn


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def server(tmp_path):
    db = str(tmp_path / "keys.db")
    s = WikipediaMCPServer(db_path=db)
    s._http = MagicMock()
    return s


def _resp(data, status=200):
    """Build a mock httpx response."""
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    r.raise_for_status.return_value = None
    return r


def _http_error(status):
    """Build a mock HTTPStatusError with the given status code."""
    mock_response = MagicMock()
    mock_response.status_code = status
    return httpx.HTTPStatusError("error", request=MagicMock(), response=mock_response)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestWikipediaMCPServerInit:
    """Tests for WikipediaMCPServer initialisation."""

    def test_server_name(self, temp_db_path):
        s = WikipediaMCPServer(db_path=temp_db_path)
        assert s.mcp.name == "WikipediaMCP"

    def test_four_tools_registered(self, temp_db_path):
        s = WikipediaMCPServer(db_path=temp_db_path)
        assert len(s.mcp._tool_manager._tools) == 4

    def test_tool_names(self, temp_db_path):
        s = WikipediaMCPServer(db_path=temp_db_path)
        assert set(s.mcp._tool_manager._tools) == {
            "search_pages",
            "search_titles",
            "get_page_summary",
            "get_related_pages",
        }

    def test_http_client_created(self, temp_db_path):
        s = WikipediaMCPServer(db_path=temp_db_path)
        assert isinstance(s._http, httpx.Client)

    def test_db_manager_created(self, temp_db_path):
        s = WikipediaMCPServer(db_path=temp_db_path)
        assert isinstance(s.db_manager, DatabaseManager)

    def test_close_closes_http_client(self, server):
        server.close()
        server._http.close.assert_called_once()

    def test_module_level_server_instance(self):
        import mcp_server_kit.wikipedia as m
        assert isinstance(m.server, WikipediaMCPServer)

    def test_module_level_mcp_instance(self):
        import mcp_server_kit.wikipedia as m
        assert m.mcp is m.server.mcp


# ---------------------------------------------------------------------------
# _strip_html helper
# ---------------------------------------------------------------------------

class TestStripHtml:

    def test_strips_span(self, server):
        assert server._strip_html("<span>hello</span>") == "hello"

    def test_strips_multiple_tags(self, server):
        assert server._strip_html("<b>bold</b> and <i>italic</i>") == "bold and italic"

    def test_plain_text_unchanged(self, server):
        assert server._strip_html("plain text") == "plain text"

    def test_empty_string(self, server):
        assert server._strip_html("") == ""

    def test_nested_tags(self, server):
        assert server._strip_html("<div><p>text</p></div>") == "text"


# ---------------------------------------------------------------------------
# search_pages
# ---------------------------------------------------------------------------

class TestSearchPages:

    def test_returns_mapped_results(self, server):
        server._http.get.return_value = _resp({"pages": [
            {"id": 1, "key": "Python", "title": "Python",
             "excerpt": "A <b>language</b>", "description": "Prog lang",
             "thumbnail": {"url": "http://img/py.jpg"}},
        ]})
        results = _tool_fn(server, "search_pages")(query="Python", limit=5)
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "Python"
        assert r["key"] == "Python"
        assert r["excerpt"] == "A language"
        assert r["description"] == "Prog lang"
        assert r["thumbnail_url"] == "http://img/py.jpg"

    def test_null_thumbnail_becomes_empty_string(self, server):
        server._http.get.return_value = _resp({"pages": [
            {"id": 1, "key": "k", "title": "T", "excerpt": "", "description": "",
             "thumbnail": None},
        ]})
        result = _tool_fn(server, "search_pages")(query="test")[0]
        assert result["thumbnail_url"] == ""

    def test_null_description_becomes_empty_string(self, server):
        server._http.get.return_value = _resp({"pages": [
            {"id": 1, "key": "k", "title": "T", "excerpt": None,
             "description": None, "thumbnail": None},
        ]})
        result = _tool_fn(server, "search_pages")(query="test")[0]
        assert result["description"] == ""

    def test_limit_clamped_to_minimum_1(self, server):
        server._http.get.return_value = _resp({"pages": []})
        _tool_fn(server, "search_pages")(query="test", limit=0)
        assert server._http.get.call_args[1]["params"]["limit"] == 1

    def test_limit_clamped_to_maximum_100(self, server):
        server._http.get.return_value = _resp({"pages": []})
        _tool_fn(server, "search_pages")(query="test", limit=999)
        assert server._http.get.call_args[1]["params"]["limit"] == 100

    def test_default_limit_is_10(self, server):
        server._http.get.return_value = _resp({"pages": []})
        _tool_fn(server, "search_pages")(query="test")
        assert server._http.get.call_args[1]["params"]["limit"] == 10

    def test_empty_results_list(self, server):
        server._http.get.return_value = _resp({"pages": []})
        assert _tool_fn(server, "search_pages")(query="xyzzy") == []

    def test_http_status_error_raises_tool_error(self, server):
        server._http.get.return_value.status_code = 503
        server._http.get.return_value.raise_for_status.side_effect = _http_error(503)
        with pytest.raises(ToolError, match="HTTP 503"):
            _tool_fn(server, "search_pages")(query="test")

    def test_request_error_raises_tool_error(self, server):
        server._http.get.side_effect = httpx.RequestError("connection refused")
        with pytest.raises(ToolError, match="request error"):
            _tool_fn(server, "search_pages")(query="test")


# ---------------------------------------------------------------------------
# search_titles
# ---------------------------------------------------------------------------

class TestSearchTitles:

    def test_returns_mapped_results(self, server):
        server._http.get.return_value = _resp({"pages": [
            {"id": 2, "key": "Einstein", "title": "Albert Einstein",
             "excerpt": "Physicist", "description": "Scientist", "thumbnail": None},
        ]})
        results = _tool_fn(server, "search_titles")(query="Einstein", limit=3)
        assert results[0]["title"] == "Albert Einstein"
        assert results[0]["description"] == "Scientist"

    def test_limit_clamped_to_minimum(self, server):
        server._http.get.return_value = _resp({"pages": []})
        _tool_fn(server, "search_titles")(query="test", limit=-5)
        assert server._http.get.call_args[1]["params"]["limit"] == 1

    def test_limit_clamped_to_maximum(self, server):
        server._http.get.return_value = _resp({"pages": []})
        _tool_fn(server, "search_titles")(query="test", limit=200)
        assert server._http.get.call_args[1]["params"]["limit"] == 100

    def test_html_stripped_from_excerpt(self, server):
        server._http.get.return_value = _resp({"pages": [
            {"id": 1, "key": "k", "title": "T",
             "excerpt": "<span>highlighted</span>", "description": "", "thumbnail": None},
        ]})
        result = _tool_fn(server, "search_titles")(query="test")[0]
        assert result["excerpt"] == "highlighted"

    def test_http_status_error(self, server):
        server._http.get.return_value.raise_for_status.side_effect = _http_error(500)
        with pytest.raises(ToolError, match="HTTP 500"):
            _tool_fn(server, "search_titles")(query="test")

    def test_request_error(self, server):
        server._http.get.side_effect = httpx.RequestError("timeout")
        with pytest.raises(ToolError, match="request error"):
            _tool_fn(server, "search_titles")(query="test")


# ---------------------------------------------------------------------------
# get_page_summary
# ---------------------------------------------------------------------------

class TestGetPageSummary:

    def _summary_data(self, **overrides):
        data = {
            "title": "Albert Einstein",
            "description": "German-born physicist",
            "extract": "Albert Einstein was a physicist.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Albert_Einstein"}},
            "thumbnail": {"source": "https://img/einstein.jpg"},
        }
        data.update(overrides)
        return data

    def test_returns_all_fields(self, server):
        server._http.get.return_value = _resp(self._summary_data())
        result = _tool_fn(server, "get_page_summary")(title="Albert_Einstein")
        assert result["title"] == "Albert Einstein"
        assert result["description"] == "German-born physicist"
        assert result["extract"] == "Albert Einstein was a physicist."
        assert result["url"] == "https://en.wikipedia.org/wiki/Albert_Einstein"
        assert result["thumbnail_url"] == "https://img/einstein.jpg"

    def test_spaces_converted_to_underscores_in_url(self, server):
        server._http.get.return_value = _resp(self._summary_data())
        _tool_fn(server, "get_page_summary")(title="Albert Einstein")
        url_called = server._http.get.call_args[0][0]
        assert "Albert_Einstein" in url_called

    def test_404_raises_not_found_tool_error(self, server):
        server._http.get.return_value = _resp({}, status=404)
        with pytest.raises(ToolError, match="not found"):
            _tool_fn(server, "get_page_summary")(title="NoSuchPage")

    def test_http_status_error_raises_tool_error(self, server):
        mock_resp = _resp(self._summary_data(), status=503)
        mock_resp.raise_for_status.side_effect = _http_error(503)
        server._http.get.return_value = mock_resp
        with pytest.raises(ToolError, match="HTTP 503"):
            _tool_fn(server, "get_page_summary")(title="SomePage")

    def test_request_error_raises_tool_error(self, server):
        server._http.get.side_effect = httpx.RequestError("connection failed")
        with pytest.raises(ToolError, match="request error"):
            _tool_fn(server, "get_page_summary")(title="SomePage")

    def test_null_thumbnail_becomes_empty_string(self, server):
        server._http.get.return_value = _resp(self._summary_data(thumbnail=None))
        result = _tool_fn(server, "get_page_summary")(title="T")
        assert result["thumbnail_url"] == ""

    def test_missing_content_urls_becomes_empty_string(self, server):
        data = self._summary_data()
        data["content_urls"] = None
        server._http.get.return_value = _resp(data)
        result = _tool_fn(server, "get_page_summary")(title="T")
        assert result["url"] == ""


# ---------------------------------------------------------------------------
# get_related_pages
# ---------------------------------------------------------------------------

class TestGetRelatedPages:

    def _search_data(self, titles):
        return {"query": {"search": [{"title": t, "snippet": f"<b>{t}</b> excerpt"} for t in titles]}}

    def test_returns_related_list(self, server):
        server._http.get.return_value = _resp(self._search_data(["Special relativity", "General relativity"]))
        results = _tool_fn(server, "get_related_pages")(title="Theory of relativity", limit=5)
        assert len(results) == 2
        assert results[0]["title"] == "Special relativity"

    def test_excerpt_html_stripped(self, server):
        server._http.get.return_value = _resp(self._search_data(["Special relativity"]))
        result = _tool_fn(server, "get_related_pages")(title="Theory of relativity")[0]
        assert result["excerpt"] == "Special relativity excerpt"

    def test_url_constructed_from_title(self, server):
        server._http.get.return_value = _resp(self._search_data(["Special relativity"]))
        result = _tool_fn(server, "get_related_pages")(title="Theory of relativity")[0]
        assert result["url"] == "https://en.wikipedia.org/wiki/Special_relativity"

    def test_limit_controls_srlimit_param(self, server):
        """Verify the limit parameter is forwarded as srlimit in the API call."""
        server._http.get.return_value = _resp(self._search_data([]))
        _tool_fn(server, "get_related_pages")(title="Test", limit=3)
        assert server._http.get.call_args[1]["params"]["srlimit"] == 3

    def test_limit_clamped_to_minimum_1(self, server):
        server._http.get.return_value = _resp(self._search_data([]))
        _tool_fn(server, "get_related_pages")(title="Test", limit=0)
        assert server._http.get.call_args[1]["params"]["srlimit"] == 1

    def test_limit_clamped_to_maximum_50(self, server):
        server._http.get.return_value = _resp(self._search_data([]))
        _tool_fn(server, "get_related_pages")(title="Test", limit=100)
        assert server._http.get.call_args[1]["params"]["srlimit"] == 50

    def test_morelike_query_sent(self, server):
        server._http.get.return_value = _resp(self._search_data([]))
        _tool_fn(server, "get_related_pages")(title="Black hole")
        sent_query = server._http.get.call_args[1]["params"]["srsearch"]
        assert sent_query == "morelike:Black hole"

    def test_http_status_error(self, server):
        server._http.get.return_value.raise_for_status.side_effect = _http_error(500)
        with pytest.raises(ToolError, match="HTTP 500"):
            _tool_fn(server, "get_related_pages")(title="Test")

    def test_request_error(self, server):
        server._http.get.side_effect = httpx.RequestError("timeout")
        with pytest.raises(ToolError, match="request error"):
            _tool_fn(server, "get_related_pages")(title="Test")

    def test_empty_search_results(self, server):
        server._http.get.return_value = _resp(self._search_data([]))
        assert _tool_fn(server, "get_related_pages")(title="xyzzy") == []
