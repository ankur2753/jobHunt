# Installation tasks

I want to make the setup process a single-command installation. The current manual setup is too involved.

## 1. One-line installer script
Users should install the agent with a single command instead of cloning the repository. 

We will host an `install.sh` script on GitHub that users can run via `curl -fsSL https://.../install.sh | bash`. The script will fetch the latest release, extract it to a hidden directory like `~/.job-hunt-agent/`, and handle the environment setup.

## 2. Use uv for virtual environments
System Python environments break often. Users run into "pip not found" or "externally-managed-environment" errors. 

The install script will download `uv`. We will use `uv venv` and `uv pip install -r requirements.txt` to build an isolated Python environment fast. This keeps our dependencies away from the system Python.

## 3. Automated Playwright dependencies
Playwright crashes on the first run if OS libraries are missing. 

The install script will run this command:
```bash
~/.job-hunt-agent/venv/bin/python -m playwright install chromium
```
It should also run `playwright install-deps` or prompt the user for `sudo` if critical system libraries like `libnss3` are missing.

## 4. Global CLI launcher
Users need to run the agent from anywhere by typing `job-hunt`. 

The installer will create a bash wrapper script in `~/.local/bin/job-hunt`. This script runs the agent inside its virtual environment:
```bash
#!/bin/bash
# ~/.local/bin/job-hunt
cd ~/.job-hunt-agent
exec ~/.job-hunt-agent/venv/bin/python scripts/orchestrator/orchestrator.py "$@"
```

## 5. First-run config wizard
Editing `.env` files and `personal_details/*.json` by hand is tedious. 

When someone runs `job-hunt` for the first time, the CLI will start a setup wizard. It will prompt for API keys and generate the configuration files and `personal_details` templates.

## 6. MCP auto-registration
Connecting to Claude Desktop or Hermes Agent should happen without manual file edits. 

We need a `job-hunt mcp-install` command. It will edit the user's `claude_desktop_config.json` or `~/.hermes/config.yaml` to include the absolute path of `mcp_server.py` running in our virtual environment.
