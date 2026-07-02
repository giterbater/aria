from __future__ import annotations

from dataclasses import dataclass
from .state import CognitiveState


@dataclass
class Need:
    """A high-level drive computed from internal state."""
    name: str
    strength: float  # 0.0-1.0
    reason: str = ""


class NeedSystem:
    """Computes higher-level drives from internal state.

    Needs influence planning decisions but never directly execute actions.
    """

    def compute(self, state: CognitiveState, context: dict | None = None) -> list[Need]:
        context = context or {}
        needs = []

        # Need for Information — driven by curiosity and novelty
        nfi = (state.curiosity * 0.6 + state.novelty * 0.4)
        if nfi > 0.5:
            needs.append(Need(
                name="information",
                strength=nfi,
                reason="High curiosity or novelty — seek knowledge",
            ))

        # Need for Verification — driven by caution and low confidence
        nfv = (state.caution * 0.5 + (1.0 - state.confidence) * 0.5)
        if nfv > 0.4:
            needs.append(Need(
                name="verification",
                strength=nfv,
                reason="High caution or low confidence — verify before acting",
            ))

        # Need for Exploration — driven by curiosity and low frustration
        nfe = (state.curiosity * 0.4 + state.novelty * 0.3 + (1.0 - state.frustration) * 0.3)
        if nfe > 0.5:
            needs.append(Need(
                name="exploration",
                strength=nfe,
                reason="Curious and capable — explore the problem space",
            ))

        # Need for Simplicity — driven by frustration and low persistence
        nfs = (state.frustration * 0.5 + (1.0 - state.persistence) * 0.3 + (1.0 - state.confidence) * 0.2)
        if nfs > 0.4:
            needs.append(Need(
                name="simplicity",
                strength=nfs,
                reason="Frustrated or uncertain — prefer simpler approaches",
            ))

        # Need for Recovery — driven by consecutive failures
        if state.consecutive_failures >= 2:
            nfr = min(1.0, state.consecutive_failures * 0.25)
            needs.append(Need(
                name="recovery",
                strength=nfr,
                reason=f"Consecutive failures ({state.consecutive_failures}) — need to recover",
            ))

        # Need for Depth — driven by high persistence and confidence
        nfd = (state.persistence * 0.5 + state.confidence * 0.3 + (1.0 - state.frustration) * 0.2)
        if nfd > 0.6:
            needs.append(Need(
                name="depth",
                strength=nfd,
                reason="Confident and persistent — dig deeper",
            ))

        needs.sort(key=lambda n: n.strength, reverse=True)
        return needs

    def get_strongest_need(self, state: CognitiveState, context: dict | None = None) -> Need | None:
        needs = self.compute(state, context)
        return needs[0] if needs else None
