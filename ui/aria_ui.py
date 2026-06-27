# aria_project/ui/aria_ui.py
"""
CustomTkinter based ARIA face.
All widgets are updated exclusively via the Event Bus.
"""

from __future__ import annotations
import tkinter as tk
import customtkinter as ctk
from datetime import datetime
from typing import Dict
import logging

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

print("[UI] Importing ui module")

from event_bus import bus
from output_planner.alang_serialization import alang_to_str


# ----------------------------------------------------------------------
# Main UI class
# ----------------------------------------------------------------------
class ARIAUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        print("[UI] ARIAUI __init__ started")
        logger.debug("ARIAUI __init__ started")
        self.title("ARIA – Cognitive Avatar")
        self.geometry("460x620")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ---- state holders ------------------------------------------------
        self._state: Dict[str, Any] = {
            "listening": False,
            "thinking": False,
            "speaking": False,
            "transcript": "",
            "response": "",
            "working_mem": [],
            "goals": [],
            "emotion": None,
            "task": "",
            "time": "",
            "status": "OK",
            "alang_thought": None,   # latest internal ALang term (debug)
        }

        # ---- layout -------------------------------------------------------
        try:
            self._build_widgets()
            logger.debug("_build_widgets completed")
        except Exception as e:
            logger.exception("Exception in _build_widgets: %s", e)
            raise

        self._subscribe_to_bus()
        logger.debug("Subscribed to bus")
        self._start_clock()
        logger.debug("Clock started")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_widgets(self):
        logger.debug("_build_widgets entering")
        pad = {"padx": 10, "pady": 5}
        # ----- Avatar ----------------------------------------------------
        self.avatar_canvas = tk.Canvas(self, width=120, height=120, highlightthickness=0, bg="#2b2b2b")
        self.avatar_canvas.grid(row=0, column=0, columnspan=2, **pad)
        self.avatar_id = self.avatar_canvas.create_oval(10, 10, 110, 110, fill="#4a90e2", outline="")
        self.avatar_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12, weight="bold"))
        self.avatar_label.grid(row=1, column=0, columnspan=2, **pad)

        # ----- Status line ------------------------------------------------
        self.lbl_status = ctk.CTkLabel(self, text="Status: …", anchor="w")
        self.lbl_status.grid(row=2, column=0, columnspan=2, sticky="we", **pad)

        # ----- Listening / Thinking / Speaking ---------------------------
        self.lbl_listen = ctk.CTkLabel(self, text="● Listening: off", text_color="gray")
        self.lbl_listen.grid(row=3, column=0, sticky="w", **pad)
        self.lbl_think = ctk.CTkLabel(self, text="● Thinking: off", text_color="gray")
        self.lbl_think.grid(row=3, column=1, sticky="w", **pad)
        self.lbl_speak = ctk.CTkLabel(self, text="● Speaking: off", text_color="gray")
        self.lbl_speak.grid(row=4, column=0, sticky="w", **pad)

        # ----- Transcript & Response --------------------------------------
        ctk.CTkLabel(self, text="User:", anchor="w").grid(row=5, column=0, sticky="w", **pad)
        self.txt_transcript = ctk.CTkTextbox(self, height=40, width=200)
        self.txt_transcript.grid(row=5, column=1, sticky="we", **pad)
        self.txt_transcript.configure(state="disabled")

        ctk.CTkLabel(self, text="ARIA:", anchor="w").grid(row=6, column=0, sticky="w", **pad)
        self.txt_response = ctk.CTkTextbox(self, height=40, width=200)
        self.txt_response.grid(row=6, column=1, sticky="we", **pad)
        self.txt_response.configure(state="disabled")

        # ----- Working memory & Goals --------------------------------------
        ctk.CTkLabel(self, text="Working Memory:", anchor="w").grid(row=7, column=0, sticky="w", **pad)
        self.txt_wmem = ctk.CTkTextbox(self, height=50, width=200)
        self.txt_wmem.grid(row=7, column=1, sticky="we", **pad)
        self.txt_wmem.configure(state="disabled")

        ctk.CTkLabel(self, text="Active Goals:", anchor="w").grid(row=8, column=0, sticky="w", **pad)
        self.txt_goals = ctk.CTkTextbox(self, height=50, width=200)
        self.txt_goals.grid(row=8, column=1, sticky="we", **pad)
        self.txt_goals.configure(state="disabled")

        # ----- Emotion / Task / Time ---------------------------------------
        self.lbl_emotion = ctk.CTkLabel(self, text="Emotion: –", anchor="w")
        self.lbl_emotion.grid(row=9, column=0, columnspan=2, sticky="w", **pad)
        self.lbl_task = ctk.CTkLabel(self, text="Task: –", anchor="w")
        self.lbl_task.grid(row=10, column=0, columnspan=2, sticky="w", **pad)
        self.lbl_time = ctk.CTkLabel(self, text="Time: –", anchor="w")
        self.lbl_time.grid(row=11, column=0, columnspan=2, sticky="w", **pad)

        # ----- ALang thought (debug) ---------------------------------------
        ctk.CTkLabel(self, text="ALang Thought (debug):", anchor="w").grid(row=12, column=0, sticky="w", **pad)
        self.txt_alang = ctk.CTkTextbox(self, height=40, width=200)
        self.txt_alang.grid(row=12, column=1, sticky="we", **pad)
        self.txt_alang.configure(state="disabled")

        # ----- System status ------------------------------------------------
        self.lbl_sys = ctk.CTkLabel(self, text="System: OK", anchor="w")
        self.lbl_sys.grid(row=13, column=0, columnspan=2, sticky="w", **pad)
        logger.debug("_build_widgets finished")

    # ------------------------------------------------------------------
    # Event subscription
    # ------------------------------------------------------------------
    def _subscribe_to_bus(self):
        logger.debug("Subscribing to bus events")
        bus.subscribe("SpeechStarted", self._on_speech_started)
        bus.subscribe("SpeechRecognized", self._on_speech_recognized)
        bus.subscribe("InterpretationReady", self._on_interpretation_ready)
        bus.subscribe("DecisionMade", self._on_decision_made)
        bus.subscribe("ActionPlanned", self._on_action_planned)
        bus.subscribe("ResponseGenerated", self._on_response_generated)
        bus.subscribe("SpeakingStarted", self._on_speaking_started)
        bus.subscribe("SpeakingStopped", self._on_speaking_stopped)
        bus.subscribe("MemoryStored", self._on_memory_stored)
        bus.subscribe("GoalCreated", self._on_goal_created)
        bus.subscribe("GoalCompleted", self._on_goal_completed)
        bus.subscribe("ThoughtGenerated", self._on_thought_generated)
        bus.subscribe("SystemStatus", self._on_system_status)
        bus.subscribe("InternalState", self._on_internal_state)
        bus.subscribe("CurrentTask", self._on_current_task)

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------
    def _start_clock(self):
        self._update_clock()
        self.after(1000, self._start_clock)   # tick every second

    def _update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self._state["time"] = now
        self.lbl_time.configure(text=f"Time: {now}")

    # ------------------------------------------------------------------
    # UI update helpers (called from event handlers)
    # ------------------------------------------------------------------
    def _set_avatar(self, state: str):
        """state ∈ {idle, listening, thinking, speaking}"""
        colors = {
            "idle": "#4a90e2",
            "listening": "#50e3c2",
            "thinking": "#f5a623",
            "speaking": "#d0021b",
        }
        text = {
            "idle": "IDLE",
            "listening": "LISTENING",
            "thinking": "THINKING",
            "speaking": "SPEAKING",
        }[state]
        self.avatar_canvas.itemconfig(self.avatar_id, fill=colors[state])
        self.avatar_label.configure(text=text)

    def _set_textbox(self, widget: ctk.CTkTextbox, content: str):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        widget.configure(state="disabled")

    # ------------------------------------------------------------------
    # Event handlers – each simply updates the internal state and refreshes UI
    # ------------------------------------------------------------------
    def _on_speech_started(self, _):
        self._state["listening"] = True
        self._set_avatar("listening")
        self.lbl_listen.configure(text="● Listening: on", text_color="#50e3c2")

    def _on_speech_recognized(self, payload: str):
        self._state["transcript"] = payload
        self._set_textbox(self.txt_transcript, payload)
        self.lbl_listen.configure(text="● Listening: off", text_color="gray")

    def _on_interpretation_ready(self, payload: dict):
        # payload may contain the StructuredInput as a dict; we just show intent/confidence
        intent = payload.get("intent", "?")
        conf = payload.get("confidence", 0.0)
        # not shown directly in UI, but we could store for debugging if needed
        pass

    def _on_decision_made(self, payload: dict):
        # payload contains the ARIDecision as dict; we also store the ALang term if present
        self._state["response"] = payload.get("response_text", "")
        self._set_textbox(self.txt_response, self._state["response"])
        # also store the ALang thought if supplied
        alang = payload.get("alang")
        if alang is not None:
            self._state["alang_thought"] = alang
            self._set_textbox(self.txt_alang, alang_to_str(alang))

    def _on_action_planned(self, payload: dict):
        # Not directly visualized; could be used to show planned action type
        pass

    def _on_response_generated(self, payload: str):
        # same as decision made – keeps UI in sync if the language cortex is called separately
        self._state["response"] = payload
        self._set_textbox(self.txt_response, payload)

    def _on_speaking_started(self, _):
        self._state["speaking"] = True
        self._set_avatar("speaking")
        self.lbl_speak.configure(text="● Speaking: on", text_color="#d0021b")

    def _on_speaking_stopped(self, _):
        self._state["speaking"] = False
        self._set_avatar("idle")
        self.lbl_speak.configure(text="● Speaking: off", text_color="gray")

    def _on_memory_stored(self, payload: dict):
        # payload may contain a summary of working memory
        wmem = payload.get("working_memory", [])
        self._state["working_mem"] = wmem
        # Show a compact representation (first 2 items)
        short = "\n".join(str(item) for item in wmem[:2])
        self._set_textbox(self.txt_wmem, short or "(empty)")

    def _on_goal_created(self, payload: dict):
        # payload = {"goal": goal_dict}
        goal = payload.get("goal", {})
        self._state["goals"].append(goal)
        self._refresh_goals_display()

    def _on_goal_completed(self, payload: dict):
        # payload = {"goal_id": gid}
        gid = payload.get("goal_id")
        self._state["goals"] = [g for g in self._state["goals"] if g.get("id") != gid]
        self._refresh_goals_display()

    def _refresh_goals_display(self):
        lines = []
        for g in self._state["goals"]:
            desc = g.get("description", "(no description)")
            prio = g.get("priority", 1.0)
            lines.append(f"- {desc} (prio:{prio:.2f})")
        self._set_textbox(self.txt_goals, "\n".join(lines) or "(none)")

    def _on_thought_generated(self, payload: Any):
        """Called whenever ARIA produces an internal ALang term we want to show."""
        self._state["alang_thought"] = payload
        self._set_textbox(self.txt_alang, alang_to_str(payload))

    def _on_system_status(self, payload: str):
        self._state["status"] = payload
        self.lbl_sys.configure(text=f"System: {payload}")

    def _on_internal_state(self, payload: dict):
        emo = payload.get("emotion")
        if emo is not None:
            self._state["emotion"] = emo
            self.lbl_emotion.configure(text=f"Emotion: {emo}")

    def _on_current_task(self, payload: str):
        self._state["task"] = payload
        self.lbl_task.configure(text=f"Task: {payload}")

# ----------------------------------------------------------------------
# Entry point – run the UI in the main thread
# ----------------------------------------------------------------------
def run_ui():
    app = ARIAUI()
    app.mainloop()