#!/usr/bin/env python3
"""Gemma Agent — Windows Desktop Application.

Launch the graphical agent interface:
    python desktop_app.py
    python desktop_app.py --workspace ./my-project
"""

from __future__ import annotations

import sys
import os
import argparse
import tkinter as tk

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Register tools before anything else
import tools.file_ops       # noqa: F401
import tools.shell          # noqa: F401
import tools.code_exec      # noqa: F401
import tools.web_search     # noqa: F401
# import tools.knowledge    # Uncomment if chromadb + sentence-transformers installed

import config
from ui.main_window import MainWindow
import sandbox
sandbox.GUI_MODE = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemma Agent Desktop")
    parser.add_argument("--workspace", default=None, help="Restrict file access to this directory")
    parser.add_argument("--model", default=None, help="Override model name")
    parser.add_argument("--base-url", default=None, help="Override Gemma API base URL")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.workspace:
        config.AGENT_WORKSPACE = os.path.abspath(args.workspace)
    if args.model:
        config.GEMMA_MODEL = args.model
    if args.base_url:
        config.GEMMA_BASE_URL = args.base_url

    root = tk.Tk()
    root.title("Gemma Agent")

    # Set app icon (use a built-in bitmap as fallback)
    try:
        root.iconbitmap(default="")
    except tk.TclError:
        pass

    # High DPI support on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
