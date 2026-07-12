"""
ARIA Cognitive Operating System UI — PySide6-based three-zone shell.

Architecture:
- Main window with three regions: Map (left), Brain sidebar (right), Thought stream (bottom)
- Every component subscribes to the event bus; no direct core access
- Dream mode is a global state overlaid on the existing layout
- All rendering from CognitiveEvent payloads only
"""

from __future__ import annotations

import sys
import logging
from typing import Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QTabWidget,
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, Slot
from PySide6.QtGui import QFont, QColor

from event_bus import bus
from aria_core.cognition.events import Event, CognitiveEvent

logger = logging.getLogger("aria.ui")


class EventDispatcher(QObject):
    """Qt signals bridge for the event bus (thread-safe)."""

    observation_received = Signal(CognitiveEvent)
    memory_retrieved = Signal(CognitiveEvent)
    hypothesis_generated = Signal(CognitiveEvent)
    prediction_made = Signal(CognitiveEvent)
    decision_made = Signal(CognitiveEvent)
    action_taken = Signal(CognitiveEvent)
    action_rejected = Signal(CognitiveEvent)
    outcome_observed = Signal(CognitiveEvent)
    learning_completed = Signal(CognitiveEvent)
    emotion_updated = Signal(CognitiveEvent)
    memory_stored = Signal(CognitiveEvent)
    dream_started = Signal(CognitiveEvent)
    dream_ended = Signal(CognitiveEvent)
    dream_replay = Signal(CognitiveEvent)
    dream_consolidate = Signal(CognitiveEvent)


class CognitiveOSUI(QMainWindow):
    """Three-zone Cognitive Operating System UI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ARIA Cognitive Operating System")
        self.setGeometry(100, 100, 1920, 1080)

        # --- Theme setup ---
        self._setup_theme()

        # --- State ---
        self._mode: str = "awake"  # "awake" or "dream"
        self._episode_buffer: list[CognitiveEvent] = []
        self._current_episode_id: str | None = None
        self._dispatcher = EventDispatcher()
        self._bus_subscriptions: dict[str, Any] = {}

        # --- Layout ---
        self._build_ui()

        # --- Event bridge and bus subscriptions ---
        # Event publishers may run on worker threads. The bus callbacks
        # therefore emit Qt signals; Qt delivers the UI slots on this
        # window's thread instead of allowing a worker to touch widgets.
        self._connect_dispatcher()
        self._subscribe_to_events()

        # --- Timer for periodic updates (e.g., clock) ---
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(1000)

    def _setup_theme(self) -> None:
        """Apply a professional dark theme."""
        self.setStyleSheet(
            """
            QMainWindow { background-color: #0E0F11; }
            QWidget { background-color: #0E0F11; color: #E8E9EB; }
            QLabel { color: #E8E9EB; }
            QTabWidget::pane { border: 1px solid #1E2127; }
            QTabBar::tab { background-color: #16181C; color: #E8E9EB; padding: 6px 12px; }
            QTabBar::tab:selected { background-color: #7C5CFF; }
            """
        )

    def _build_ui(self) -> None:
        """Construct the three-zone shell."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Top bar ---
        top_bar = self._build_top_bar()
        main_layout.addWidget(top_bar)

        # --- Middle splitter: Map | Brain sidebar ---
        middle_splitter = QSplitter(Qt.Horizontal)
        self._map_zone = self._build_map_zone()
        self._brain_sidebar = self._build_brain_sidebar()
        middle_splitter.addWidget(self._map_zone)
        middle_splitter.addWidget(self._brain_sidebar)
        middle_splitter.setSizes([1400, 500])
        main_layout.addWidget(middle_splitter)

        # --- Bottom: Thought stream ---
        self._thought_stream = self._build_thought_stream()
        main_layout.addWidget(self._thought_stream, 1)

        central_widget.setLayout(main_layout)

    def _build_top_bar(self) -> QWidget:
        """Top status bar with world metrics."""
        widget = QWidget()
        widget.setMaximumHeight(40)
        widget.setStyleSheet("background-color: #16181C; border-bottom: 1px solid #1E2127;")

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 0, 12, 0)

        self._lbl_world_status = QLabel("Day 1 · Spring · Stable · Population 0 · FPS 60")
        self._lbl_world_status.setFont(QFont("Inter", 12))
        layout.addWidget(self._lbl_world_status)
        layout.addStretch()

        self._lbl_mode = QLabel("AWAKE")
        self._lbl_mode.setStyleSheet("color: #3FB950;")
        self._lbl_mode.setFont(QFont("Inter", 12, weight=700))
        layout.addWidget(self._lbl_mode)

        widget.setLayout(layout)
        return widget

    def _build_map_zone(self) -> QWidget:
        """Left zone: world visualization."""
        widget = QWidget()
        widget.setStyleSheet("background-color: #1E2127;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Placeholder for now; real renderer would use QPainter or OpenGL
        self._map_display = QLabel("MAP: World visualization (placeholder)")
        self._map_display.setAlignment(Qt.AlignCenter)
        self._map_display.setStyleSheet("color: #7C5CFF; font-size: 14px;")
        layout.addWidget(self._map_display)

        widget.setLayout(layout)
        return widget

    def _build_brain_sidebar(self) -> QWidget:
        """Right zone: emotion, goals, memory, actions."""
        widget = QWidget()
        widget.setMaximumWidth(500)
        widget.setStyleSheet("background-color: #16181C; border-left: 1px solid #1E2127;")

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.setStyleSheet("QTabWidget::pane { border: none; }")

        # --- Emotion panel ---
        self._emotion_panel = self._build_emotion_panel()
        tabs.addTab(self._emotion_panel, "Emotion")

        # --- Goals panel ---
        self._goals_panel = self._build_goals_panel()
        tabs.addTab(self._goals_panel, "Goals")

        # --- Memory panel ---
        self._memory_panel = self._build_memory_panel()
        tabs.addTab(self._memory_panel, "Memory")

        # --- Action panel ---
        self._action_panel = self._build_action_panel()
        tabs.addTab(self._action_panel, "Actions")

        # --- World inspector ---
        self._world_inspector = self._build_world_inspector()
        tabs.addTab(self._world_inspector, "World")

        layout.addWidget(tabs)
        widget.setLayout(layout)
        return widget

    def _build_emotion_panel(self) -> QWidget:
        """Emotion state with explanations."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._emotion_displays = {}
        dims = [
            "confidence",
            "curiosity",
            "frustration",
            "motivation",
            "caution",
            "persistence",
            "novelty",
        ]
        for dim in dims:
            lbl = QLabel(f"{dim}: —")
            lbl.setFont(QFont("Inter", 11))
            self._emotion_displays[dim] = lbl
            layout.addWidget(lbl)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _build_goals_panel(self) -> QWidget:
        """Active goals with progress."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        self._goals_display = QLabel("No active goals")
        self._goals_display.setFont(QFont("Inter", 11))
        layout.addWidget(self._goals_display)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _build_memory_panel(self) -> QWidget:
        """Memory store display (episodic, semantic, procedural)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        self._memory_display = QLabel("Memory stores: (empty)")
        self._memory_display.setFont(QFont("Inter", 11))
        self._memory_display.setWordWrap(True)
        layout.addWidget(self._memory_display)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _build_action_panel(self) -> QWidget:
        """Available actions from the environment."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        self._action_display = QLabel("No available actions")
        self._action_display.setFont(QFont("Inter", 11))
        layout.addWidget(self._action_display)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _build_world_inspector(self) -> QWidget:
        """World state metrics (population, resources, etc.)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        self._world_metrics_display = QLabel("World metrics: (waiting for data)")
        self._world_metrics_display.setFont(QFont("Inter", 11))
        self._world_metrics_display.setWordWrap(True)
        layout.addWidget(self._world_metrics_display)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _build_thought_stream(self) -> QWidget:
        """Append-only log of the nine-step pipeline."""
        widget = QWidget()
        widget.setMaximumHeight(300)
        widget.setStyleSheet("background-color: #0E0F11; border-top: 1px solid #1E2127;")

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        self._stream_display = QLabel("Thought stream: (waiting for cognition events)")
        self._stream_display.setFont(QFont("Courier New", 10))
        self._stream_display.setStyleSheet("color: #7C5CFF;")
        self._stream_display.setWordWrap(True)
        self._stream_display.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        layout.addWidget(self._stream_display)
        widget.setLayout(layout)
        return widget

    def _subscribe_to_events(self) -> None:
        """Connect event bus to UI updates."""
        subscriptions = {
            Event.OBSERVATION: self._dispatcher.observation_received.emit,
            Event.MEMORY_RETRIEVED: self._dispatcher.memory_retrieved.emit,
            Event.HYPOTHESIS: self._dispatcher.hypothesis_generated.emit,
            Event.PREDICTION: self._dispatcher.prediction_made.emit,
            Event.DECISION: self._dispatcher.decision_made.emit,
            Event.ACTION: self._dispatcher.action_taken.emit,
            Event.ACTION_REJECTED: self._dispatcher.action_rejected.emit,
            Event.OUTCOME: self._dispatcher.outcome_observed.emit,
            Event.LEARNING: self._dispatcher.learning_completed.emit,
            Event.EMOTION: self._dispatcher.emotion_updated.emit,
            Event.DREAM_START: self._dispatcher.dream_started.emit,
            Event.DREAM_END: self._dispatcher.dream_ended.emit,
        }
        for event_name, callback in subscriptions.items():
            bus.subscribe(event_name, callback)
        self._bus_subscriptions = subscriptions

    def _connect_dispatcher(self) -> None:
        """Deliver bus events to widget-mutating handlers on the Qt thread."""
        self._dispatcher.observation_received.connect(self._on_observation)
        self._dispatcher.memory_retrieved.connect(self._on_memory_retrieved)
        self._dispatcher.hypothesis_generated.connect(self._on_hypothesis)
        self._dispatcher.prediction_made.connect(self._on_prediction)
        self._dispatcher.decision_made.connect(self._on_decision)
        self._dispatcher.action_taken.connect(self._on_action)
        self._dispatcher.action_rejected.connect(self._on_action_rejected)
        self._dispatcher.outcome_observed.connect(self._on_outcome)
        self._dispatcher.learning_completed.connect(self._on_learning)
        self._dispatcher.emotion_updated.connect(self._on_emotion)
        self._dispatcher.dream_started.connect(self._on_dream_start)
        self._dispatcher.dream_ended.connect(self._on_dream_end)

    def closeEvent(self, event: Any) -> None:
        """Detach the UI bridge before Qt destroys the window."""
        for event_name, callback in self._bus_subscriptions.items():
            bus.unsubscribe(event_name, callback)
        self._bus_subscriptions.clear()
        super().closeEvent(event)

    # --- Event handlers ---

    def _on_observation(self, event: CognitiveEvent) -> None:
        """Handle observation event."""
        if event.episode_id != self._current_episode_id:
            self._current_episode_id = event.episode_id
            self._episode_buffer = []
        self._episode_buffer.append(event)
        intent = event.payload.get("intent", "?")
        self._world_metrics_display.setText(f"Latest observation: {intent}")
        self._append_to_stream(f"[OBS] {intent}")

    def _on_memory_retrieved(self, event: CognitiveEvent) -> None:
        """Handle memory retrieved event."""
        self._episode_buffer.append(event)
        total = event.payload.get("total", 0)
        self._memory_display.setText(f"Retrieved memories: {total}")
        self._append_to_stream(f"[MEM] {total} matches")

    def _on_hypothesis(self, event: CognitiveEvent) -> None:
        """Handle hypothesis event."""
        self._episode_buffer.append(event)
        hypotheses = event.payload.get("hypotheses", [])
        top_h = hypotheses[0] if hypotheses else {}
        self._append_to_stream(f"[HYP] {top_h.get('text', '?')} (prior={top_h.get('prior', 0):.2f})")

    def _on_prediction(self, event: CognitiveEvent) -> None:
        """Handle prediction event."""
        self._episode_buffer.append(event)
        predicted_outcome = event.payload.get("predicted_outcome", "?")
        confidence = event.payload.get("confidence", 0)
        self._append_to_stream(
            f"[PRED] {predicted_outcome} (conf={confidence:.2f})"
        )

    def _on_decision(self, event: CognitiveEvent) -> None:
        """Handle decision event."""
        self._episode_buffer.append(event)
        decision = event.payload.get("decision", {})
        action_type = (
            decision.get("action_type", "?")
            if isinstance(decision, dict)
            else getattr(decision, "action_type", "?")
        )
        self._action_display.setText(f"Decision: {action_type}")
        self._append_to_stream(f"[DEC] {action_type}")

    def _on_action(self, event: CognitiveEvent) -> None:
        """Handle action event."""
        self._episode_buffer.append(event)
        action = event.payload.get("action", {})
        action_type = (
            action.get("action_type", "?")
            if isinstance(action, dict)
            else getattr(action, "action_type", "?")
        )
        self._action_display.setText(f"Last action: {action_type}")
        self._append_to_stream(f"[ACT] {action_type}")

    def _on_action_rejected(self, event: CognitiveEvent) -> None:
        """Handle action rejected event."""
        self._append_to_stream(f"[REJECT] Action invalid")

    def _on_outcome(self, event: CognitiveEvent) -> None:
        """Handle outcome event."""
        self._episode_buffer.append(event)
        result = event.payload.get("result", "?")
        reward = event.payload.get("reward", 0)
        self._append_to_stream(f"[OUT] {result} (reward={reward:.2f})")

    def _on_learning(self, event: CognitiveEvent) -> None:
        """Handle learning event."""
        self._episode_buffer.append(event)
        updates = event.payload.get("memory_updates", [])
        self._append_to_stream(f"[LEARN] {len(updates)} memory updates")

    def _on_emotion(self, event: CognitiveEvent) -> None:
        """Handle emotion update event."""
        self._episode_buffer.append(event)
        state = event.payload.get("state", {})
        delta = event.payload.get("delta", {})
        cause = event.payload.get("cause", {})

        # Update emotion panel
        for dim in state:
            val = state[dim]
            delta_val = delta.get(dim, 0)
            cause_text = cause.get(dim, "")
            arrow = "↑" if delta_val > 0 else ("↓" if delta_val < 0 else "→")
            if dim in self._emotion_displays:
                display_text = f"{dim}: {val:.2f} {arrow}"
                if cause_text:
                    display_text += f" ({cause_text})"
                self._emotion_displays[dim].setText(display_text)

        self._append_to_stream(f"[EMO] {list(delta.keys())}")

    def _on_dream_start(self, event: CognitiveEvent) -> None:
        """Handle dream mode start."""
        self._mode = "dream"
        self._lbl_mode.setText("DREAMING")
        self._lbl_mode.setStyleSheet("color: #D29922;")
        self._append_to_stream("[DREAM] Memory consolidation started...")

    def _on_dream_end(self, event: CognitiveEvent) -> None:
        """Handle dream mode end."""
        self._mode = "awake"
        self._lbl_mode.setText("AWAKE")
        self._lbl_mode.setStyleSheet("color: #3FB950;")
        self._append_to_stream("[DREAM] Consolidation complete.")

    def _append_to_stream(self, text: str) -> None:
        """Append a line to the thought stream."""
        current = self._stream_display.text()
        if current.startswith("Thought stream:"):
            current = ""
        lines = current.split("\n") if current else []
        lines.append(text)
        # Keep last 100 lines
        lines = lines[-100:]
        self._stream_display.setText("\n".join(lines))

    @Slot()
    def _on_tick(self) -> None:
        """Periodic update (e.g., clock)."""
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        # Could update top bar clock here if needed


def main() -> None:
    app = QApplication(sys.argv)
    window = CognitiveOSUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
