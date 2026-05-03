"""Main window for the Gemma Agent desktop application."""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from ui.theme import *
from ui.agent_worker import AgentWorker, AgentEvent
from ui.settings_dialog import SettingsDialog
from tool_registry import list_tools
import config


class MainWindow:
    """The primary application window with chat, sidebar, and input."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Gemma Agent")
        self.root.configure(bg=BG_PRIMARY)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(800, 500)

        # Event queue for worker → UI communication
        self.event_queue: queue.Queue[AgentEvent] = queue.Queue()
        self.worker = AgentWorker(self.event_queue)

        self._build_ui()
        self._setup_tags()
        self._poll_events()

        # Auto-connect with defaults
        try:
            self.worker.connect(config.GEMMA_BASE_URL, config.GEMMA_MODEL)
        except Exception:
            pass

        self._update_status_bar()

    # ══════════════════════════════════════════════════════════════
    # BUILD UI
    # ══════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        # ── Top bar ────────────────────────────────────────────────
        self._build_topbar()

        # ── Body (sidebar + chat) ──────────────────────────────────
        body = tk.Frame(self.root, bg=BG_PRIMARY)
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)
        self._build_chat_area(body)

        # ── Status bar ─────────────────────────────────────────────
        self._build_status_bar()

    # ── TOP BAR ────────────────────────────────────────────────────

    def _build_topbar(self) -> None:
        bar = tk.Frame(self.root, bg=BG_SECONDARY, height=48)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Logo / title
        tk.Label(bar, text="\U0001f916  Gemma Agent", font=(FONT_FAMILY, FONT_SIZE_LARGE, "bold"),
                 fg=FG_HEADING, bg=BG_SECONDARY).pack(side="left", padx=16)

        # Right-side buttons
        btn_opts = dict(relief="flat", cursor="hand2", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                        bg=BG_SECONDARY, fg=FG_SECONDARY, padx=10, pady=4)

        tk.Button(bar, text="\u2699 Settings", command=self._open_settings, **btn_opts).pack(side="right", padx=(0, 12))
        tk.Button(bar, text="\U0001f5d1 Clear", command=self._clear_chat, **btn_opts).pack(side="right")

        self.btn_stop = tk.Button(bar, text="\u25a0 Stop", command=self._stop_agent,
                                  bg=BG_BUTTON_DANGER, fg=FG_BUTTON, relief="flat",
                                  font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
                                  padx=12, pady=4, cursor="hand2", state="disabled")
        self.btn_stop.pack(side="right", padx=8)

    # ── SIDEBAR ────────────────────────────────────────────────────

    def _build_sidebar(self, parent: tk.Frame) -> None:
        sidebar = tk.Frame(parent, bg=BG_SECONDARY, width=SIDEBAR_WIDTH)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Connection info
        conn_frame = tk.Frame(sidebar, bg=BG_SECONDARY, padx=14, pady=12)
        conn_frame.pack(fill="x")
        tk.Label(conn_frame, text="CONNECTION", fg=FG_SECONDARY, bg=BG_SECONDARY,
                 font=(FONT_FAMILY, 9, "bold")).pack(anchor="w")

        self.lbl_model = tk.Label(conn_frame, text=config.GEMMA_MODEL,
                                  fg=FG_PRIMARY, bg=BG_SECONDARY,
                                  font=(FONT_FAMILY, FONT_SIZE, "bold"))
        self.lbl_model.pack(anchor="w", pady=(4, 0))

        self.lbl_endpoint = tk.Label(conn_frame, text=config.GEMMA_BASE_URL,
                                     fg=FG_SECONDARY, bg=BG_SECONDARY,
                                     font=(FONT_FAMILY, 9), wraplength=SIDEBAR_WIDTH - 30)
        self.lbl_endpoint.pack(anchor="w")

        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=14)

        # Tools list
        tools_frame = tk.Frame(sidebar, bg=BG_SECONDARY, padx=14, pady=10)
        tools_frame.pack(fill="x")
        tk.Label(tools_frame, text="TOOLS", fg=FG_SECONDARY, bg=BG_SECONDARY,
                 font=(FONT_FAMILY, 9, "bold")).pack(anchor="w", pady=(0, 6))

        for t in list_tools():
            row = tk.Frame(tools_frame, bg=BG_SECONDARY)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"\u2022 {t.name}", fg=FG_ACTION, bg=BG_SECONDARY,
                     font=(FONT_MONO, 9), anchor="w").pack(anchor="w")

        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=14, pady=(6, 0))

        # Quick actions
        qa_frame = tk.Frame(sidebar, bg=BG_SECONDARY, padx=14, pady=10)
        qa_frame.pack(fill="x")
        tk.Label(qa_frame, text="QUICK ACTIONS", fg=FG_SECONDARY, bg=BG_SECONDARY,
                 font=(FONT_FAMILY, 9, "bold")).pack(anchor="w", pady=(0, 6))

        quick_actions = [
            ("List project files", "List all files in the workspace and describe the structure"),
            ("Explain codebase", "Read the key files and explain what this project does"),
            ("Find bugs", "Analyze the code for potential bugs and suggest fixes"),
            ("Generate tests", "Generate unit tests for the main modules"),
        ]
        for label, prompt in quick_actions:
            btn = tk.Button(qa_frame, text=label, anchor="w",
                            bg=BG_INPUT, fg=FG_PRIMARY, relief="flat",
                            font=(FONT_FAMILY, FONT_SIZE_SMALL), padx=10, pady=4,
                            cursor="hand2",
                            command=lambda p=prompt: self._send_quick(p))
            btn.pack(fill="x", pady=2)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=BG_HOVER))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=BG_INPUT))

    # ── CHAT AREA ──────────────────────────────────────────────────

    def _build_chat_area(self, parent: tk.Frame) -> None:
        chat_container = tk.Frame(parent, bg=BG_PRIMARY)
        chat_container.pack(side="left", fill="both", expand=True)

        # Scrollable chat display
        chat_frame = tk.Frame(chat_container, bg=BG_PRIMARY)
        chat_frame.pack(fill="both", expand=True, padx=12, pady=(8, 0))

        self.chat_scroll = tk.Scrollbar(chat_frame, orient="vertical")
        self.chat_scroll.pack(side="right", fill="y")

        self.chat_display = tk.Text(
            chat_frame,
            wrap="word",
            bg=BG_PRIMARY,
            fg=FG_PRIMARY,
            font=(FONT_FAMILY, FONT_SIZE),
            relief="flat",
            bd=0,
            padx=12,
            pady=8,
            state="disabled",
            yscrollcommand=self.chat_scroll.set,
            cursor="arrow",
            insertbackground=BG_PRIMARY,
            selectbackground=BG_HOVER,
        )
        self.chat_display.pack(fill="both", expand=True)
        self.chat_scroll.config(command=self.chat_display.yview)

        # Welcome message
        self._append_chat("system",
            "\U0001f916 Welcome to Gemma Agent!\n"
            "Type a message below to give the agent a task. "
            "It will reason step-by-step and use tools to complete it.\n"
            "Use the sidebar quick actions or type freely.\n")

        # ── Input area ─────────────────────────────────────────────
        input_frame = tk.Frame(chat_container, bg=BG_SECONDARY, padx=12, pady=10)
        input_frame.pack(fill="x")

        input_inner = tk.Frame(input_frame, bg=BG_INPUT, bd=0, highlightthickness=1,
                               highlightbackground=BORDER, highlightcolor=BORDER_FOCUS)
        input_inner.pack(fill="x")

        self.input_text = tk.Text(
            input_inner,
            wrap="word",
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            font=(FONT_FAMILY, FONT_SIZE),
            relief="flat",
            bd=0,
            height=3,
            padx=10,
            pady=8,
            insertbackground=FG_PRIMARY,
        )
        self.input_text.pack(side="left", fill="both", expand=True)
        self.input_text.bind("<Return>", self._on_enter)
        self.input_text.bind("<Shift-Return>", lambda e: None)  # allow shift+enter for newlines

        # Send button
        self.btn_send = tk.Button(
            input_inner, text=" Send \u27a4 ",
            bg=BG_BUTTON, fg=FG_BUTTON, relief="flat",
            font=(FONT_FAMILY, FONT_SIZE, "bold"),
            padx=16, pady=8, cursor="hand2",
            command=self._send_message,
        )
        self.btn_send.pack(side="right", padx=(0, 6), pady=6)
        self.btn_send.bind("<Enter>", lambda e: self.btn_send.configure(bg=BG_BUTTON_HOVER))
        self.btn_send.bind("<Leave>", lambda e: self.btn_send.configure(bg=BG_BUTTON))

    # ── STATUS BAR ─────────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self.root, bg=BG_SECONDARY, height=26)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        self.lbl_status = tk.Label(bar, text="Ready", fg=FG_SECONDARY, bg=BG_SECONDARY,
                                   font=(FONT_FAMILY, 9), padx=12)
        self.lbl_status.pack(side="left")

        self.lbl_workspace = tk.Label(bar, text=f"Workspace: {config.AGENT_WORKSPACE}",
                                      fg=FG_SECONDARY, bg=BG_SECONDARY,
                                      font=(FONT_FAMILY, 9), padx=12)
        self.lbl_workspace.pack(side="right")

    # ══════════════════════════════════════════════════════════════
    # TEXT TAGS (colours for different message types)
    # ══════════════════════════════════════════════════════════════

    def _setup_tags(self) -> None:
        cd = self.chat_display
        cd.tag_configure("user_label", foreground=FG_USER, font=(FONT_FAMILY, FONT_SIZE, "bold"))
        cd.tag_configure("user_text", foreground=FG_USER, font=(FONT_FAMILY, FONT_SIZE))
        cd.tag_configure("thought", foreground=FG_THOUGHT, font=(FONT_FAMILY, FONT_SIZE, "italic"))
        cd.tag_configure("thought_label", foreground=FG_THOUGHT, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"))
        cd.tag_configure("action_label", foreground=FG_ACTION, font=(FONT_FAMILY, FONT_SIZE, "bold"))
        cd.tag_configure("action_text", foreground=FG_ACTION, font=(FONT_MONO, FONT_SIZE_SMALL))
        cd.tag_configure("obs_label", foreground=FG_OBSERVATION, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"))
        cd.tag_configure("obs_text", foreground=FG_OBSERVATION, font=(FONT_MONO, FONT_SIZE_SMALL))
        cd.tag_configure("answer_label", foreground=FG_ANSWER, font=(FONT_FAMILY, FONT_SIZE, "bold"))
        cd.tag_configure("answer_text", foreground=FG_ANSWER, font=(FONT_FAMILY, FONT_SIZE))
        cd.tag_configure("error_text", foreground=FG_ERROR, font=(FONT_FAMILY, FONT_SIZE))
        cd.tag_configure("status_text", foreground=FG_SECONDARY, font=(FONT_FAMILY, 9, "italic"))
        cd.tag_configure("system_text", foreground=FG_SECONDARY, font=(FONT_FAMILY, FONT_SIZE))
        cd.tag_configure("separator", foreground=BORDER, font=(FONT_FAMILY, 6))

    # ══════════════════════════════════════════════════════════════
    # CHAT DISPLAY HELPERS
    # ══════════════════════════════════════════════════════════════

    def _append_chat(self, kind: str, text: str, data: dict | None = None) -> None:
        cd = self.chat_display
        cd.configure(state="normal")

        timestamp = datetime.now().strftime("%H:%M")

        if kind == "user":
            cd.insert("end", f"\n  You  [{timestamp}]\n", "user_label")
            cd.insert("end", f"  {text}\n", "user_text")

        elif kind == "thought":
            cd.insert("end", f"  \U0001f4ad Thought\n", "thought_label")
            cd.insert("end", f"  {text}\n", "thought")

        elif kind == "action":
            action_input = data.get("input", "") if data else ""
            cd.insert("end", f"  \U0001f527 Tool Call\n", "action_label")
            cd.insert("end", f"  {text}({action_input})\n", "action_text")

        elif kind == "observation":
            # Truncate long observations for display
            display = text if len(text) < 800 else text[:800] + "\n  ... (truncated)"
            cd.insert("end", f"  \U0001f4cb Observation\n", "obs_label")
            cd.insert("end", f"  {display}\n", "obs_text")

        elif kind == "answer":
            cd.insert("end", f"\n  \u2705 Agent  [{timestamp}]\n", "answer_label")
            cd.insert("end", f"  {text}\n", "answer_text")
            cd.insert("end", "\n" + "\u2500" * 60 + "\n", "separator")

        elif kind == "error":
            cd.insert("end", f"  \u26a0 Error: {text}\n", "error_text")

        elif kind == "status":
            cd.insert("end", f"  \u2022 {text}\n", "status_text")

        elif kind == "system":
            cd.insert("end", f"\n{text}\n", "system_text")
            cd.insert("end", "\u2500" * 60 + "\n", "separator")

        elif kind == "confirm":
            cd.insert("end", f"  \u26a0 {text}\n", "error_text")

        cd.configure(state="disabled")
        cd.see("end")

    # ══════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ══════════════════════════════════════════════════════════════

    def _on_enter(self, event: tk.Event) -> str:
        if not event.state & 0x1:  # Shift not held
            self._send_message()
            return "break"
        return ""

    def _send_message(self) -> None:
        text = self.input_text.get("1.0", "end").strip()
        if not text:
            return
        self.input_text.delete("1.0", "end")
        self._append_chat("user", text)
        self.btn_stop.configure(state="normal")
        self.btn_send.configure(state="disabled")
        self.worker.send_message(text)

    def _send_quick(self, prompt: str) -> None:
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", prompt)
        self._send_message()

    def _stop_agent(self) -> None:
        self.worker.stop()
        self._append_chat("status", "Stopping agent...")
        self.btn_stop.configure(state="disabled")
        self.btn_send.configure(state="normal")

    def _clear_chat(self) -> None:
        self.worker.clear()
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self._append_chat("system",
            "\U0001f916 Chat cleared. Conversation history reset.\n")

    def _open_settings(self) -> None:
        SettingsDialog(self.root, self._on_settings_saved)

    def _on_settings_saved(self, base_url: str, model: str) -> None:
        try:
            self.worker.connect(base_url, model)
            self.lbl_model.configure(text=model)
            self.lbl_endpoint.configure(text=base_url)
            self._update_status_bar()
            self._append_chat("status", f"Connected to {model} at {base_url}")
        except Exception as exc:
            self._append_chat("error", f"Connection failed: {exc}")

    def _update_status_bar(self) -> None:
        self.lbl_workspace.configure(text=f"Workspace: {config.AGENT_WORKSPACE}")

    # ══════════════════════════════════════════════════════════════
    # EVENT POLLING (worker → UI)
    # ══════════════════════════════════════════════════════════════

    def _poll_events(self) -> None:
        """Drain the event queue and update the UI. Runs every 50ms."""
        try:
            while True:
                event: AgentEvent = self.event_queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.root.after(50, self._poll_events)

    def _handle_event(self, event: AgentEvent) -> None:
        if event.kind == "confirm":
            # Show confirmation dialog
            result = messagebox.askyesno("Confirm Action", event.text, parent=self.root)
            self.worker.provide_confirmation(result)
            if result:
                self._append_chat("status", "Approved by user")
            else:
                self._append_chat("status", "Rejected by user")
            return

        self._append_chat(event.kind, event.text, event.data)

        # Update status bar
        if event.kind == "status":
            self.lbl_status.configure(text=event.text)

        # Re-enable send when agent finishes
        if event.kind in ("answer", "error") or \
           (event.kind == "status" and event.text in ("Done", "Stopped by user", "Max iterations reached")):
            self.btn_stop.configure(state="disabled")
            self.btn_send.configure(state="normal")
            if event.kind != "status":
                self.lbl_status.configure(text="Ready")
