# Prerequisites

Before you can run this project you need a terminal, Git, and `uv`. You do **not** need to install Python separately — `uv` will download and manage the correct Python version for you.

## 1. Open a terminal

A terminal (also called a shell or command prompt) is where you type commands to run software.

- **macOS**: Press `Cmd + Space`, type `Terminal`, press Enter
- **Windows**: Search for **PowerShell** in the Start menu and open it. Use PowerShell for all commands in this guide.

## 2. Install Git

Git is the tool used to download (clone) this project from GitHub.

**macOS** — Git is usually pre-installed. Confirm by running:
```bash
git --version
```
If it is not found, install the Xcode Command Line Tools:
```bash
xcode-select --install
```

**Windows** — Download and run the installer from [git-scm.com/download/win](https://git-scm.com/download/win). Accept the defaults. After installation, close and reopen PowerShell, then confirm:
```powershell
git --version
```

## 3. Install uv

`uv` is the package and Python manager used by this project. It installs all dependencies and the correct version of Python automatically.

**macOS** (Terminal):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows** (PowerShell):
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

After installation, close and reopen your terminal, then confirm:
```bash
uv --version
```

> `uv` will automatically download Python 3.12 the first time you run `uv sync` — no separate Python installation needed.
