# Publishing to PyPI

`mcp-server-kit` is published with [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
(OIDC) via the [`.github/workflows/publish.yml`](../.github/workflows/publish.yml)
workflow. No API tokens are stored in the repository.

## One-time setup: configure trusted publishing

Do this once on **PyPI** (and, if you want to dry-run first, on **TestPyPI**):

1. Sign in at <https://pypi.org> → your account → **Publishing** → **Add a pending publisher**.
2. Fill in:
   - **PyPI Project Name:** `mcp-server-kit`
   - **Owner:** `dgwartney`
   - **Repository name:** `mcp-examples`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
3. Repeat on <https://test.pypi.org> using **Environment name:** `testpypi`.

Then, in the GitHub repo → **Settings → Environments**, create environments named
`pypi` and `testpypi` (optionally add required reviewers so releases need approval).

## Validate on TestPyPI first (recommended)

1. GitHub → **Actions → Publish → Run workflow**, choose **testpypi**.
2. Install from TestPyPI in a clean environment and smoke-test (uv only):
   ```bash
   uv venv /tmp/v
   uv pip install --python /tmp/v \
     --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ \
     mcp-server-kit
   /tmp/v/bin/python -c "import mcp_server_kit; print(mcp_server_kit.__version__)"
   /tmp/v/bin/mcp-server-kit new /tmp/demo --no-examples
   ```
3. Confirm the project page on TestPyPI renders the README correctly.

## Release to PyPI

1. Bump `__version__` in `mcp_server_kit/__init__.py` (single source of truth; the
   build reads it via `[tool.hatch.version]`). Update `CHANGELOG.md`.
2. Create a GitHub **Release** with a tag like `v0.1.0`.
3. Publishing the release triggers the workflow's `publish-pypi` job automatically.

## Build locally (optional)

```bash
uv build            # -> dist/*.whl and dist/*.tar.gz
uvx twine check dist/*
```
