"""Quick validation of OpenHands + ARIA integration."""
import os
import subprocess
import sys

sys.path.insert(0, r"C:\Users\nevaan kaul\aria_project")

repo = r"C:\Users\nevaan kaul\aria_project"
passed = 0
failed = 0


def check(name, ok, detail=""):
    global passed, failed
    status = "PASS" if ok else "FAIL"
    color = "\033[92m" if ok else "\033[91m"
    reset = "\033[0m"
    print(f"  {color}[{status}]{reset} {name}" + (f" ({detail})" if detail else ""))
    if ok:
        passed += 1
    else:
        failed += 1


print("\n=== OpenHands + ARIA Integration Validation ===\n")

# 1. NVIDIA API key
env_path = os.path.join(repo, "openhands", ".env")
key = None
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith("NVIDIA_API_KEY="):
                key = line.split("=", 1)[1].strip()
                break
check("NVIDIA API key in .env", bool(key) and key.startswith("nvapi-"), key[:15] + "..." if key else "missing")

# 2. API connectivity
try:
    import httpx
    r = httpx.get(
        "https://integrate.api.nvidia.com/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
    )
    models = [m["id"] for m in r.json().get("data", []) if "minimax" in m["id"]]
    check("NVIDIA API reachable", len(models) > 0, f"minimax models: {models}")
except Exception as e:
    check("NVIDIA API reachable", False, str(e))

# 3. Repository
check("ARIA repository exists", os.path.isdir(repo))

# 4. Git
result = subprocess.run(["git", "-C", repo, "status", "--short"], capture_output=True, text=True)
check("Git operations", result.returncode == 0, f"{len(result.stdout.splitlines())} changes")

# 5. Python tests
result = subprocess.run(
    [sys.executable, "-m", "pytest", os.path.join(repo, "tests"), "--co", "-q"],
    capture_output=True, text=True, cwd=repo,
)
lines = [l for l in result.stdout.splitlines() if "test" in l.lower()]
check("Python tests collectible", result.returncode == 0, f"{len(lines)} items")

# 6. OpenHands config
config_path = os.path.expanduser(r"~\.openhands\config.toml")
check("OpenHands config.toml", os.path.exists(config_path), config_path)

# 7. Node.js
try:
    r = subprocess.run(["node", "--version"], capture_output=True, text=True)
    check("Node.js", r.returncode == 0, r.stdout.strip())
except FileNotFoundError:
    check("Node.js", False, "not found")

# 8. Agent Canvas
try:
    r = subprocess.run(
        "npx @openhands/agent-canvas --version",
        capture_output=True, text=True, timeout=15, shell=True,
    )
    check("Agent Canvas installed", r.returncode == 0, r.stdout.strip() if r.stdout else "unknown")
except Exception as e:
    check("Agent Canvas installed", False, str(e))

# 9. uv
try:
    r = subprocess.run(["uv", "--version"], capture_output=True, text=True)
    check("uv (agent-server)", r.returncode == 0, r.stdout.strip())
except FileNotFoundError:
    check("uv (agent-server)", False, "not found")

# 10. Docker (optional)
try:
    r = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=5)
    docker_ok = r.returncode == 0
    check("Docker daemon", docker_ok, "running" if docker_ok else "not running (optional)")
except Exception:
    check("Docker daemon", False, "not available (optional)")

# Summary
print(f"\n{'=' * 48}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'=' * 48}")

if failed == 0:
    print("\n  All checks passed. OpenHands is ready.")
    print("  Run: .\\openhands\\start.ps1")
else:
    print(f"\n  {failed} check(s) failed. Fix issues above.")

print()
