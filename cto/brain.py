from __future__ import annotations

import logging
import time
from typing import Any

from .config import CTOConfig
from .loop import CTOLoop
from tools.registry import CTOToolRegistry
from permissions.tiered_model import TieredPermissionPolicy
from git.operations import GitOperationsImpl
from memory_ext.project_memory import ProjectMemorySQLite
from delegation.manager import SpecialistManager

logger = logging.getLogger("aria.cto.brain")


class CTOBrain:
    """The central orchestrator for the ARIA CTO autonomous agent.

    Owns the tool registry, permission policy, git operations, project memory,
    specialist manager, and the autonomous loop. The LLM is accessed through
    a provider abstraction — the CTO never knows which backend is in use.
    """

    def __init__(self, config: CTOConfig) -> None:
        self.config = config

        self.tools = CTOToolRegistry.with_defaults()
        self.permissions = TieredPermissionPolicy(config.permissions)
        self.git = GitOperationsImpl(default_cwd=str(config.repo_path_resolved()))
        self.project_memory = ProjectMemorySQLite(
            db_path=str(config.repo_path_resolved() / ".aria" / "project_memory.db")
        )
        self.specialist_manager = SpecialistManager()

        self._llm = self._init_provider()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl: float = 30.0

        self.context: dict[str, Any] = {}
        self.current_action: dict[str, Any] = {}
        self.test_failures: str | None = None

        self._loop = CTOLoop(self)

        logger.info(
            "CTOBrain initialized (repo=%s, provider=%s, model=%s)",
            config.repo_path,
            config.provider,
            config.model,
        )

    def _init_provider(self):
        """Initialize the LLM provider with automatic failover."""
        from language_cortex.providers import create_provider, FailoverProvider
        from language_cortex.providers.base import ProviderConfig

        primary_config = ProviderConfig(
            provider=self.config.provider,
            model=self.config.model,
            api_key=self.config.resolve_api_key(),
            base_url=self.config.base_url,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            top_p=self.config.top_p,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )

        try:
            primary = create_provider(primary_config)
            logger.info("Primary provider: %s (model=%s)", primary_config.provider, primary_config.model)
        except Exception as exc:
            logger.warning("Failed to init primary provider %s: %s", primary_config.provider, exc)
            primary = None

        fallback = None
        if self.config.fallback_provider and self.config.fallback_provider != self.config.provider:
            fallback_config = ProviderConfig(
                provider=self.config.fallback_provider,
                model=self.config.fallback_model,
                base_url=self.config.ollama_base_url,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout,
            )
            try:
                fallback = create_provider(fallback_config)
                logger.info("Fallback provider: %s", fallback_config.provider)
            except Exception as exc:
                logger.warning("Failed to init fallback provider %s: %s", fallback_config.provider, exc)

        if primary is not None:
            return FailoverProvider(
                primary=primary,
                fallback=fallback,
                max_retries=self.config.max_retries,
            )

        if fallback is not None:
            logger.info("Using fallback provider as primary")
            return fallback

        logger.warning("No LLM provider available")
        return None

    @property
    def llm(self):
        return self._llm

    def generate(self, prompt: str, *, max_tokens: int = 2048, temperature: float = 0.3):
        """Generate a response from the LLM. Provider-agnostic."""
        if self._llm is None:
            from language_cortex.providers.base import LanguageResponse
            return LanguageResponse.fail("No LLM provider configured")
        return self._llm.generate(prompt, max_tokens=max_tokens, temperature=temperature)

    def cached(self, key: str, compute_fn, ttl: float | None = None):
        """Return cached value or compute and cache it."""
        ttl = ttl or self._cache_ttl
        now = time.monotonic()
        if key in self._cache:
            ts, val = self._cache[key]
            if now - ts < ttl:
                return val
        val = compute_fn()
        self._cache[key] = (now, val)
        return val

    def invalidate_cache(self, key: str | None = None) -> None:
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    def build_choose_prompt(self) -> str:
        from prompts.cto_system import CTO_SYSTEM_PROMPT, TOOL_DESCRIPTIONS_TEMPLATE

        tool_descs = []
        for name in self.tools.known_tools():
            tool = self.tools.get(name)
            if tool:
                tool_descs.append(f"- {name}: {tool.description}")

        tools_text = TOOL_DESCRIPTIONS_TEMPLATE.format(tools="\n".join(tool_descs))
        prompt = CTO_SYSTEM_PROMPT.format(tool_descriptions=tools_text)

        roadmap = self.project_memory.get_roadmap()
        roadmap_text = ""
        if roadmap:
            items = [f"- {r.get('value', {}).get('title', r['key'])}: {r.get('value', {}).get('status', 'unknown')}" for r in roadmap[:10]]
            roadmap_text = "\n".join(items)

        codebase_facts = self.project_memory.get_codebase_facts()
        facts_text = ""
        if codebase_facts:
            facts_text = "\n".join(f"- {k}: {v}" for k, v in codebase_facts[:10])

        recent = self.project_memory.get_recent_decisions(limit=5)
        recent_text = ""
        if recent:
            recent_text = "\n".join(
                f"- {d.get('value', {}).get('outcome', '?')}: {', '.join(a.get('tool', '?') for a in d.get('value', {}).get('actions', []))}"
                for d in recent
            )

        tool_names = ", ".join(self.tools.known_tools())

        sections = []
        sections.append(f"EXACT TOOL NAMES (use one of these): {tool_names}")
        sections.append(f"Git Status:\n{self.context.get('git_status', '(clean)')}")
        structure = self.context.get('project_structure', '(unknown)')
        if len(structure) > 2000:
            structure = structure[:2000] + "\n... (truncated)"
        sections.append(f"Project Structure:\n{structure}")
        py_files = self.context.get("python_files", "")
        if py_files and py_files != "(none)":
            if len(py_files) > 3000:
                py_files = py_files[:3000] + "\n... (truncated)"
            sections.append(f"Python Files:\n{py_files}")
        todos = self.context.get("todos_found", "")
        if todos and todos != "(none)":
            if len(todos) > 1000:
                todos = todos[:1000] + "\n... (truncated)"
            sections.append(f"TODOs Found:\n{todos}")
        if roadmap_text:
            sections.append(f"Roadmap:\n{roadmap_text}")
        if facts_text:
            sections.append(f"Known Facts:\n{facts_text}")
        if recent_text:
            sections.append(f"Recent Actions:\n{recent_text}")
        last = self.context.get("last_actions_done", "")
        if last and last != "(none)":
            sections.append(f"LAST 3 ACTIONS ALREADY COMPLETED (pick something DIFFERENT): {last}")

        context_text = "\n\n".join(sections)
        return f"{prompt}\n\n## Current Context\n{context_text}\n\n## Your Action\nRespond with JSON:"

    def build_review_prompt(self, diff: str) -> str:
        from prompts.review import REVIEW_PROMPT
        return REVIEW_PROMPT.format(
            diff=diff[:4000],
            context="Automated review of CTO cycle changes",
        )

    def run_single_cycle(self):
        return self._loop.run_single_cycle()

    def run_continuous(self):
        self._loop.run_continuous(
            interval_seconds=self.config.cycle_interval_seconds,
            max_cycles=self.config.max_cycles,
        )

    def stop(self) -> None:
        self._loop.stop()

    def shutdown(self) -> None:
        self.project_memory.close()
        if self._llm and hasattr(self._llm, "close"):
            try:
                self._llm.close()
            except Exception:
                pass
        logger.info("CTOBrain shut down")
