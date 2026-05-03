"""Settings dialog for configuring the agent."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog

from ui.theme import *
import config


class SettingsDialog(tk.Toplevel):
    """Modal dialog for agent configuration."""

    def __init__(self, parent: tk.Tk, on_save: callable):
        super().__init__(parent)
        self.on_save = on_save

        self.title("Gemma Agent — Settings")
        self.configure(bg=BG_PRIMARY)
        self.geometry("520x560")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._center(parent)

    def _center(self, parent: tk.Tk) -> None:
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        main = tk.Frame(self, bg=BG_PRIMARY, padx=24, pady=20)
        main.pack(fill="both", expand=True)

        # Title
        tk.Label(main, text="Agent Settings", font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                 fg=FG_HEADING, bg=BG_PRIMARY).pack(anchor="w", pady=(0, 16))

        # ── Connection ──
        self._section(main, "Connection")

        self.var_base_url = tk.StringVar(value=config.GEMMA_BASE_URL)
        self._field(main, "API Base URL:", self.var_base_url)

        self.var_model = tk.StringVar(value=config.GEMMA_MODEL)
        self._field(main, "Model Name:", self.var_model)

        # ── Agent Behavior ──
        self._section(main, "Agent Behavior")

        self.var_max_iter = tk.IntVar(value=config.AGENT_MAX_ITERATIONS)
        self._field(main, "Max Iterations:", self.var_max_iter, width=8)

        self.var_temperature = tk.DoubleVar(value=config.AGENT_TEMPERATURE)
        self._field(main, "Temperature:", self.var_temperature, width=8)

        self.var_max_tokens = tk.IntVar(value=config.AGENT_MAX_TOKENS)
        self._field(main, "Max Tokens:", self.var_max_tokens, width=8)

        self.var_context_budget = tk.IntVar(value=config.AGENT_CONTEXT_BUDGET)
        self._field(main, "Context Budget:", self.var_context_budget, width=8)

        # ── Safety ──
        self._section(main, "Safety")

        self.var_confirm = tk.BooleanVar(value=config.AGENT_CONFIRM_WRITES)
        cb = tk.Checkbutton(main, text="Confirm destructive actions (writes, deletes, installs)",
                            variable=self.var_confirm, fg=FG_PRIMARY, bg=BG_PRIMARY,
                            selectcolor=BG_INPUT, activebackground=BG_PRIMARY,
                            activeforeground=FG_PRIMARY, font=(FONT_FAMILY, FONT_SIZE))
        cb.pack(anchor="w", pady=(2, 4))

        # Workspace
        ws_frame = tk.Frame(main, bg=BG_PRIMARY)
        ws_frame.pack(fill="x", pady=(4, 4))
        tk.Label(ws_frame, text="Workspace:", fg=FG_SECONDARY, bg=BG_PRIMARY,
                 font=(FONT_FAMILY, FONT_SIZE), width=14, anchor="w").pack(side="left")
        self.var_workspace = tk.StringVar(value=config.AGENT_WORKSPACE)
        entry = tk.Entry(ws_frame, textvariable=self.var_workspace, bg=BG_INPUT,
                         fg=FG_PRIMARY, insertbackground=FG_PRIMARY,
                         font=(FONT_FAMILY, FONT_SIZE), relief="flat", bd=0)
        entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))
        tk.Button(ws_frame, text="Browse", command=self._browse_workspace,
                  bg=BG_HOVER, fg=FG_PRIMARY, relief="flat", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                  padx=10, cursor="hand2").pack(side="right")

        # ── Buttons ──
        btn_frame = tk.Frame(main, bg=BG_PRIMARY)
        btn_frame.pack(fill="x", pady=(20, 0))

        tk.Button(btn_frame, text="Cancel", command=self.destroy,
                  bg=BG_HOVER, fg=FG_PRIMARY, relief="flat",
                  font=(FONT_FAMILY, FONT_SIZE), padx=20, pady=6,
                  cursor="hand2").pack(side="right", padx=(8, 0))

        tk.Button(btn_frame, text="Save & Connect", command=self._save,
                  bg=BG_BUTTON, fg=FG_BUTTON, relief="flat",
                  font=(FONT_FAMILY, FONT_SIZE, "bold"), padx=20, pady=6,
                  cursor="hand2").pack(side="right")

    def _section(self, parent: tk.Frame, title: str) -> None:
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(12, 8))
        tk.Label(parent, text=title, fg=FG_HEADING, bg=BG_PRIMARY,
                 font=(FONT_FAMILY, FONT_SIZE, "bold")).pack(anchor="w", pady=(0, 6))

    def _field(self, parent: tk.Frame, label: str, var: tk.Variable, width: int = 0) -> None:
        row = tk.Frame(parent, bg=BG_PRIMARY)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, fg=FG_SECONDARY, bg=BG_PRIMARY,
                 font=(FONT_FAMILY, FONT_SIZE), width=14, anchor="w").pack(side="left")
        entry = tk.Entry(row, textvariable=var, bg=BG_INPUT, fg=FG_PRIMARY,
                         insertbackground=FG_PRIMARY, font=(FONT_FAMILY, FONT_SIZE),
                         relief="flat", bd=0)
        if width:
            entry.configure(width=width)
            entry.pack(side="left", ipady=4)
        else:
            entry.pack(side="left", fill="x", expand=True, ipady=4)

    def _browse_workspace(self) -> None:
        path = filedialog.askdirectory(initialdir=self.var_workspace.get())
        if path:
            self.var_workspace.set(path)

    def _save(self) -> None:
        config.GEMMA_BASE_URL = self.var_base_url.get().strip()
        config.GEMMA_MODEL = self.var_model.get().strip()
        config.AGENT_MAX_ITERATIONS = self.var_max_iter.get()
        config.AGENT_TEMPERATURE = self.var_temperature.get()
        config.AGENT_MAX_TOKENS = self.var_max_tokens.get()
        config.AGENT_CONTEXT_BUDGET = self.var_context_budget.get()
        config.AGENT_CONFIRM_WRITES = self.var_confirm.get()
        config.AGENT_WORKSPACE = self.var_workspace.get().strip()

        self.on_save(config.GEMMA_BASE_URL, config.GEMMA_MODEL)
        self.destroy()
