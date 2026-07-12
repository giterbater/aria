# OpenHands Integration for ARIA

## Architecture

```
CEO
  └─ CTO (Planning & Engineering Decisions)
       └─ Mimo (Core Logic, Memory, Goals)
            └─ Nemotron (I/O, Language, UI)
                 └─ OpenHands (Execution Engine)
                      └─ Repository
```

OpenHands is the **execution engine** for ARIA. It handles code editing, testing, git operations, and command execution. The CTO retains full authority over planning and engineering decisions.

## Prerequisites

| Component | Required | Purpose |
|---|---|---|
| Node.js 22.12+ | Yes | Agent Canvas runtime |
| npm | Yes | Package management |
| uv | Yes | Agent-server backend |
| Git | Yes | Version control |
| NVIDIA API key | Yes | LLM provider |
| Docker | Optional | Container-based execution |

## Installation

Already completed. Components installed:

| Component | Location | Purpose |
|---|---|---|
| `@openhands/agent-canvas` | Global npm (v1.1.0) | Web UI + agent orchestration |
| `config.toml` | `~/.openhands/config.toml` | LLM and app settings |
| `openhands/.env` | Project directory | Environment variables |
| `openhands/bridge.py` | Project directory | CTO-to-OpenHands bridge |

## Configuration

### NVIDIA API

The integration uses the NVIDIA API (OpenAI-compatible endpoint). Configuration is in `openhands/.env`:

```env
NVIDIA_API_KEY=nvapi-...
OPENAI_API_KEY=nvapi-...           # Same key, litellm compatibility
OPENAI_API_BASE=https://integrate.api.nvidia.com/v1
LLM_MODEL=openai/minimaxai/minimax-m2.7
```

### LLM Settings

Pre-configured in `~/.openhands/config.toml`:

```toml
[llm]
model = "openai/minimaxai/minimax-m2.7"
base_url = "https://integrate.api.nvidia.com/v1"

[llm.advanced]
num_retries = 3
retry_min_wait = 5
retry_max_wait = 30

[git]
username = "ARIA-CTO"
email = "aria-cto@aria-project.local"

[app]
max_budget_per_conversation = 10.0
```

### Provider Selection

Changing the model does not require code changes. Edit `~/.openhands/config.toml`:

```toml
[llm]
model = "openai/minimaxai/minimax-m3"
```

Or set via environment variable:

```powershell
$env:LLM_MODEL = "openai/minimaxai/minimax-m3"
```

## Startup

### Quick Start

```powershell
# From the aria_project directory
.\openhands\start.ps1
```

Then open http://localhost:8000 in your browser.

### Options

```powershell
.\openhands\start.ps1                    # Full stack (default)
.\openhands\start.ps1 -Port 3000        # Custom port
.\openhands\start.ps1 -BackendOnly      # API only, no UI
.\openhands\start.ps1 -FrontendOnly     # UI only, connect to external backend
.\openhands\start.ps1 -Public           # Require API key login
```

### Batch File (Double-Click)

```
.\openhands\start.bat
```

## Usage

### First-Time Setup

1. Run `.\openhands\start.ps1`
2. Open http://localhost:8000
3. Go to **Settings > LLM**
4. The NVIDIA API should be pre-configured. Verify the model shows `openai/minimaxai/minimax-m2.7`
5. Click **Save Changes**

### Creating Conversations

1. Click **New Conversation** in the UI
2. Select the ARIA workspace (should be auto-detected)
3. Start giving tasks to the agent

### Example Tasks

```
# Code editing
"Add a new method to aria_core/memory/simple_memory_system.py that tracks conversation history"

# Testing
"Run the test suite and fix any failing tests"

# Git operations
"Create a feature branch and commit the recent changes"

# Analysis
"Analyze the architecture of the language_cortex module and suggest improvements"
```

### Model Switching

OpenHands supports switching models mid-conversation:

1. Create additional LLM profiles in **Settings > LLM**
2. Use `/model` in chat to list profiles
3. Use `/model <profile-name>` to switch

## CTO Bridge

The CTO agent can delegate execution tasks to OpenHands via the bridge module:

```python
from openhands.bridge import OpenHandsBridge

bridge = OpenHandsBridge()

# Run tests
result = bridge.run_tests()
print(result.success, result.output[:200])

# Git status
status = bridge.git_status()
print(status.output)

# Delegate a task
task = bridge.execute_task("Add error handling to the config loader")
print(task.success)
```

The bridge provides safe operations (tests, git status, git diff) that execute without approval. Complex tasks are queued for the OpenHands agent.

## Shutdown

```powershell
# Press Ctrl+C in the terminal running start.ps1
# Or close the terminal window
```

OpenHands state is persisted in `~/.openhands/`. Conversations survive restarts.

## Safety

### Automatic Operations (No Approval Needed)

- Reading files
- Listing directories
- Code search
- Git status, diff, log
- Running tests
- Creating commits

### Operations Requiring Approval

- Deleting files
- Renaming files
- Running arbitrary commands
- Git push

### Blocked Operations (Never Execute)

- Force push (`git push --force`)
- History rewrite (`git rebase -i`, `git reset --hard`)
- Repository deletion

These restrictions are enforced at the OpenHands agent level. The CTO's permission model in `cto/config.py` provides additional governance.

## Validation

Run the integration validator:

```powershell
# Python validator (detailed)
python openhands\validate_integration.py

# PowerShell validator (interactive)
.\openhands\validate.ps1
```

Expected output:

```
=== OpenHands + ARIA Integration Validation ===

  [PASS] NVIDIA API key in .env (nvapi-bpRH49_45...)
  [PASS] NVIDIA API reachable (minimax models: [...])
  [PASS] ARIA repository exists
  [PASS] Git operations (N changes)
  [PASS] Python tests collectible (283 items)
  [PASS] OpenHands config.toml
  [PASS] Node.js (v24.12.0)
  [PASS] Agent Canvas installed (1.1.0)
  [PASS] uv (agent-server) (uv 0.11.23)
  [PASS] Docker daemon (optional)

  Results: 10 passed, 0 failed
```

## Troubleshooting

### "Docker Desktop needs updating"

Update Docker Desktop via its built-in updater, or download from https://docker.com/products/docker-desktop. Docker is optional — OpenHands works without it.

### "Agent Canvas not found"

```powershell
npm install -g @openhands/agent-canvas
```

### "NVIDIA API key not set"

1. Check `openhands/.env` has `NVIDIA_API_KEY=nvapi-...`
2. Or set it in your terminal: `$env:NVIDIA_API_KEY = "nvapi-..."`

### "Model not responding"

1. Verify API key is valid at https://build.nvidia.com
2. Check model availability: the API serves `minimaxai/minimax-m2.7`
3. Try a different model in Settings > LLM

### "Port 8000 already in use"

```powershell
.\openhands\start.ps1 -Port 3000
```

### "uv not found"

```powershell
pip install uv
# or
winget install astral-sh.uv
```

## File Structure

```
aria_project/
├── openhands/
│   ├── .env                    # Environment variables
│   ├── bridge.py               # CTO-to-OpenHands bridge
│   ├── start.ps1               # PowerShell startup script
│   ├── start.bat               # Batch file launcher
│   ├── validate.ps1            # PowerShell validator
│   ├── validate_integration.py # Python validator
│   └── INTEGRATION.md          # This file
├── .env                        # ARIA project env (NVIDIA key)
├── cto/
│   └── config.py               # CTO permission model
└── ...

~/.openhands/
├── config.toml                 # OpenHands configuration
└── (conversation data)
```

## Remaining Limitations

1. **Docker**: Docker Desktop needs updating before container-based execution works. OpenHands functions without Docker via the agent-server backend.
2. **Full API integration**: The bridge module currently queues tasks. Direct REST API integration with the agent-server would enable real-time execution monitoring.
3. **Session persistence**: OpenHands conversations persist in `~/.openhands/`, but the CTO bridge does not yet sync conversation state bidirectionally.

## Support

- OpenHands Docs: https://docs.openhands.dev
- GitHub: https://github.com/OpenHands/OpenHands
- Slack: https://go.openhands.dev/slack
