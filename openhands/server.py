"""Start OpenHands server for ARIA."""
import os
import sys
from pathlib import Path

os.environ["OPENHANDS_SUPPRESS_BANNER"] = "1"

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if k and k not in os.environ:
                os.environ[k] = v

os.environ.setdefault("LLM_MODEL", "openai/minimaxai/minimax-m2.7")
os.environ.setdefault("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")

if not os.environ.get("NVIDIA_API_KEY"):
    print("ERROR: NVIDIA_API_KEY not set"); sys.exit(1)

from openhands.app_server.app import app
import uvicorn
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
print(f"OpenHands running on http://localhost:{port}")
uvicorn.run(app, host="0.0.0.0", port=port)
