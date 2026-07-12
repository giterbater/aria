"""Launch OpenHands Agent Server for ARIA.

Usage:
    python openhands\launch.py
    python openhands\launch.py --port 3000
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Suppress OpenHands banner
os.environ["OPENHANDS_SUPPRESS_BANNER"] = "1"

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value

# Set OpenHands LLM configuration for NVIDIA
os.environ.setdefault("LLM_MODEL", "openai/minimaxai/minimax-m2.7")
os.environ.setdefault("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")

# Verify API key
if not os.environ.get("NVIDIA_API_KEY"):
    print("ERROR: NVIDIA_API_KEY not set. Check .env file.")
    sys.exit(1)

print("=" * 50)
print("  ARIA - OpenHands Agent Server")
print("  Execution Engine for CTO Architecture")
print("=" * 50)
print()
print(f"  LLM:       {os.environ['LLM_MODEL']} (NVIDIA API)")
print(f"  Workspace: {Path.cwd()}")
print(f"  API Key:   {os.environ['NVIDIA_API_KEY'][:15]}...")
print()

try:
    from openhands.app_server.app import app
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"  Starting on http://localhost:{port}")
    print("  Press Ctrl+C to stop")
    print()

    uvicorn.run(app, host="0.0.0.0", port=port)
except ImportError as e:
    print(f"ERROR: OpenHands not installed: {e}")
    print("Run: uv venv .venv-openhands --python 3.12")
    print("Then: uv pip install --python .venv-openhands\\Scripts\\python.exe openhands-ai")
    sys.exit(1)
except KeyboardInterrupt:
    print("\nShutting down...")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
