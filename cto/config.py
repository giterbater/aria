from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env file from repo root or CWD if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        for candidate in [
            Path(__file__).resolve().parent.parent / ".env",
            Path.cwd() / ".env",
        ]:
            if candidate.is_file():
                load_dotenv(candidate, override=False)
                return
    except ImportError:
        pass


_load_dotenv()


def _env(key: str, default: str = "") -> str:
    """Read an environment variable, returning *default* if unset or empty."""
    return os.environ.get(key, "").strip() or default


@dataclass
class CTOConfig:
    """Configuration for the ARIA CTO autonomous agent."""

    repo_path: str

    provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "nvidia"))
    model: str = field(default_factory=lambda: _env("LLM_MODEL", "minimaxai/minimax-m2.7"))
    api_key: str = ""
    base_url: str = "https://integrate.api.nvidia.com/v1"
    temperature: float = 0.3
    max_tokens: int = 8192
    top_p: float = 0.95
    timeout: float = 120.0
    max_retries: int = 2

    ollama_base_url: str = field(default_factory=lambda: _env("OLLAMA_URL", "http://localhost:11434"))
    fallback_provider: str = "ollama"
    fallback_model: str = "deepseek-coder-v2:16b"

    cycle_interval_seconds: int = 30
    max_review_retries: int = 3
    max_cycles: int | None = None
    auto_approve: bool = False
    single_cycle: bool = False

    permissions: dict[str, str] = field(default_factory=lambda: {
        "read_file": "auto",
        "list_files": "auto",
        "search_code": "auto",
        "get_structure": "auto",
        "git_status": "auto",
        "git_diff": "auto",
        "git_log": "auto",
        "git_add": "auto",
        "git_commit": "auto",
        "apply_edit": "auto",
        "create_file": "auto",
        "delete_file": "ask",
        "rename_file": "ask",
        "run_command": "ask",
        "run_tests": "auto",
        "git_push": "ask",
        "git_branch_create": "auto",
        "git_branch_delete": "block",
        "git_reset_hard": "block",
        "git_force_push": "block",
    })

    def repo_path_resolved(self) -> Path:
        return Path(self.repo_path).resolve()

    def resolve_api_key(self) -> str:
        """Resolve API key from config value, then environment variables."""
        if self.api_key:
            return self.api_key
        env_map = {
            "nvidia": "NVIDIA_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_var = env_map.get(self.provider.lower(), "")
        if env_var:
            return os.environ.get(env_var, "")
        return ""
