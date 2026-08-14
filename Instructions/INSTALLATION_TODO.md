# Future TODO: Simplifying Job-Hunt-Agent Installation

Inspired by the Hermes Agent installation flow, here is a roadmap to transform our setup process into a seamless, one-line installation experience for end-users.

## 1. One-Line Installer Script (`install.sh`)
**Goal:** Allow users to install the agent with a single command without cloning the repo manually.
- **Action:** Host an `install.sh` script on GitHub that users can run via `curl -fsSL https://.../install.sh | bash`.
- **Functionality:** The script should fetch the latest release, extract it to a standard hidden directory (e.g., `~/.job-hunt-agent/`), and handle all environment setups automatically.

## 2. Leverage `uv` for Fast, Isolated Environments
**Goal:** Eliminate Python environment nightmares (e.g., "pip not found", "externally-managed-environment" errors).
- **Action:** Bundle or download `uv` (Astral's fast Python package manager) within the install script.
- **Functionality:** Use `uv venv` and `uv pip install -r requirements.txt` to silently and rapidly build an isolated Python environment that won't conflict with system packages.

## 3. Automated Playwright Dependency Handling
**Goal:** Stop Playwright from crashing on first run due to missing OS libraries.
- **Action:** In the install script, automatically execute:
  ```bash
  ~/.job-hunt-agent/venv/bin/python -m playwright install chromium
  ```
- **Action (Optional):** Attempt to run `playwright install-deps` (or prompt the user for `sudo` if they are missing critical system libraries like `libnss3`).

## 4. Global CLI Launcher
**Goal:** Allow the user to run the agent from anywhere using a simple command like `job-hunt`.
- **Action:** The installer should create a bash wrapper script in `~/.local/bin/job-hunt` (which is usually in the user's `$PATH`).
- **Functionality:** 
  ```bash
  #!/bin/bash
  # ~/.local/bin/job-hunt
  cd ~/.job-hunt-agent
  exec ~/.job-hunt-agent/venv/bin/python scripts/orchestrator/orchestrator.py "$@"
  ```

## 5. First-Run Config Wizard
**Goal:** Replace the manual editing of `.env` files and `personal_details/*.json` files.
- **Action:** Upon first running the `job-hunt` command, if no config is found, trigger a CLI wizard.
- **Functionality:** Prompt the user for required credentials (e.g., OpenAI/Claude keys) and automatically generate the necessary configuration files and `personal_details` boilerplate.

## 6. MCP Auto-Registration
**Goal:** Instantly hook into Claude Desktop or Hermes Agent.
- **Action:** Add a command like `job-hunt mcp-install` which automatically edits the user's `claude_desktop_config.json` or `~/.hermes/config.yaml` to inject the absolute path of the `mcp_server.py` executing inside the isolated `uv` virtual environment.
