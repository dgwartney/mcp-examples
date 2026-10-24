"""
Generator tests (plan E6) for ``mcp-server-kit new``.

Generates standalone projects into tmp dirs and verifies they are well-formed
and runnable: the combined app mounts the user's server (and any chosen bundled
servers), enforces API-key auth, and imports without side effects.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import importlib
import os
import subprocess
import sys

import httpx
import pytest

from mcp_server_kit import scaffold

# Warm heavy imports at collection time. fastmcp installs a beartype "claw"
# import hook that raises a spurious circular ImportError if fastmcp is first
# imported mid-test via a dynamically-loaded generated package; importing the
# base + a bundled server here ensures fastmcp is fully loaded beforehand.
import mcp_server_kit.base  # noqa: E402,F401
import mcp_server_kit.server  # noqa: E402,F401


@pytest.fixture
def import_project():
    """Import a generated project's package, cleaning up sys.path/sys.modules after."""
    added_paths = []
    added_modules = set()

    def _import(project_path, pkg, submodule):
        before = set(sys.modules)
        sys.path.insert(0, str(project_path))
        added_paths.append(str(project_path))
        mod = importlib.import_module(f"{pkg}.{submodule}")
        added_modules.update(set(sys.modules) - before)
        return mod

    yield _import

    for p in added_paths:
        if p in sys.path:
            sys.path.remove(p)
    for m in list(added_modules):
        sys.modules.pop(m, None)


async def _route_statuses(app, paths):
    """POST a keyless tools/list to each path in one lifespan; return {path: status}.

    The app lifespan (which starts each sub-app's session manager) may only be
    entered once, so all requests share a single lifespan context.
    """
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    out = {}
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            for path in paths:
                resp = await client.post(path, json=body)
                out[path] = resp.status_code
    return out


def test_depend_mode_tree_and_pyproject(tmp_path):
    proj = scaffold.new_project(str(tmp_path / "dep_proj"), standalone=False, examples=[])
    pkg = "dep_proj"
    assert (proj / pkg / "my_server.py").exists()
    assert (proj / pkg / "combined.py").exists()
    assert (proj / "tests" / "test_my_server.py").exists()
    assert not (proj / pkg / "_base").exists()
    pyproject = (proj / "pyproject.toml").read_text()
    assert "mcp-server-kit>=" in pyproject
    assert 'packages = ["dep_proj"]' in pyproject


@pytest.mark.asyncio
async def test_depend_mode_app_runs_and_enforces_auth(tmp_path, monkeypatch, import_project):
    proj = scaffold.new_project(str(tmp_path / "run_proj"), standalone=False, examples=[])
    monkeypatch.chdir(proj)
    combined = import_project(proj, "run_proj", "combined")
    app = combined.app
    statuses = await _route_statuses(app, ["/my_server/mcp", "/nope/mcp"])
    assert statuses["/my_server/mcp"] == 401  # mounted + auth-guarded
    assert statuses["/nope/mcp"] == 404        # unmounted


def test_standalone_mode_vendors_base_and_drops_dependency(tmp_path):
    proj = scaffold.new_project(str(tmp_path / "vend_proj"), standalone=True, examples=[])
    pkg = "vend_proj"
    assert (proj / pkg / "_base" / "base.py").exists()
    assert (proj / pkg / "_base" / "database.py").exists()
    assert (proj / pkg / "_base" / "middleware.py").exists()
    pyproject = (proj / "pyproject.toml").read_text()
    assert '"mcp-server-kit' not in pyproject  # no dependency line without bundled servers
    server_src = (proj / pkg / "my_server.py").read_text()
    assert f"from {pkg}._base.base import" in server_src


@pytest.mark.asyncio
async def test_bundled_server_is_mounted(tmp_path, monkeypatch, import_project):
    proj = scaffold.new_project(
        str(tmp_path / "ex_proj"), standalone=False, examples=["greet"]
    )
    monkeypatch.chdir(proj)
    combined = import_project(proj, "ex_proj", "combined")
    app = combined.app
    statuses = await _route_statuses(app, ["/greet/mcp", "/my_server/mcp"])
    assert statuses["/greet/mcp"] == 401       # bundled server mounted
    assert statuses["/my_server/mcp"] == 401


def test_standalone_with_examples_readds_dependency(tmp_path):
    proj = scaffold.new_project(
        str(tmp_path / "mix_proj"), standalone=True, examples=["greet"]
    )
    pyproject = (proj / "pyproject.toml").read_text()
    assert "mcp-server-kit>=" in pyproject  # bundled servers force the dependency back
    readme = (proj / "README.md").read_text()
    assert "standalone" in readme.lower()


def test_cli_help_exits_zero():
    for args in (["--help"], ["new", "--help"], ["add-server", "--help"]):
        result = subprocess.run(
            [sys.executable, "-m", "mcp_server_kit.scaffold", *args],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


def test_generated_project_imports_without_db(tmp_path, monkeypatch, import_project):
    proj = scaffold.new_project(str(tmp_path / "clean_proj"), standalone=False, examples=[])
    monkeypatch.chdir(tmp_path)
    import_project(proj, "clean_proj", "my_server")  # import only, do not access server
    assert not list(tmp_path.glob("*.db"))


@pytest.mark.asyncio
@pytest.mark.parametrize("standalone", [False, True])
async def test_generated_server_serves_all_primitives(tmp_path, import_project, standalone):
    """The starter server shows a tool, a resource, a resource template and a prompt."""
    from fastmcp import Client

    pkg = "prim_proj_vend" if standalone else "prim_proj_dep"
    proj = scaffold.new_project(str(tmp_path / pkg), standalone=standalone, examples=[])
    my_server = import_project(proj, pkg, "my_server")
    srv = my_server.MyServer(db_path=str(tmp_path / "keys.db"))
    async with Client(srv.mcp) as client:
        assert {t.name for t in await client.list_tools()} == {"add"}
        assert {str(r.uri) for r in await client.list_resources()} == {"info://my_server"}
        assert {t.uriTemplate for t in await client.list_resource_templates()} == {
            "numbers://{n}/square"
        }
        assert {p.name for p in await client.list_prompts()} == {"explain_sum"}
        square = await client.read_resource("numbers://7/square")
        assert square[0].text == "49"
        prompt = await client.get_prompt("explain_sum", {"a": "2", "b": "3"})
        assert "2 + 3" in prompt.messages[0].content.text


def test_generated_project_tests_pass(tmp_path):
    """The generated project's own test suite runs green."""
    proj = scaffold.new_project(str(tmp_path / "green_proj"), standalone=False, examples=[])
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=",
         "tests"],
        cwd=proj,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(proj)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
