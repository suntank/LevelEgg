"""File dialog utilities using tkinter as a fallback."""
from __future__ import annotations

import os
from typing import Optional


def open_file_dialog(
    title: str = "Open Project",
    filetypes: list[tuple[str, str]] | None = None,
    initial_dir: str | None = None,
) -> Optional[str]:
    """Show a file open dialog. Returns path or None if cancelled."""
    if filetypes is None:
        filetypes = [("BirdLevel Project", "*.birdlevel"), ("JSON Files", "*.json"), ("All Files", "*.*")]
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title=title,
            filetypes=filetypes,
            initialdir=initial_dir or os.getcwd(),
        )
        root.destroy()
        return path if path else None
    except Exception:
        return None


def save_file_dialog(
    title: str = "Save Project",
    filetypes: list[tuple[str, str]] | None = None,
    initial_dir: str | None = None,
    default_name: str = "project.birdlevel",
) -> Optional[str]:
    """Show a file save dialog. Returns path or None if cancelled."""
    if filetypes is None:
        filetypes = [("BirdLevel Project", "*.birdlevel"), ("JSON Files", "*.json"), ("All Files", "*.*")]
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.asksaveasfilename(
            title=title,
            filetypes=filetypes,
            initialdir=initial_dir or os.getcwd(),
            defaultextension=".birdlevel",
            initialfile=default_name,
        )
        root.destroy()
        return path if path else None
    except Exception:
        return None


def ask_yes_no(title: str = "Confirm", message: str = "") -> bool:
    """Show a yes/no dialog. Returns True for yes."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        result = messagebox.askyesno(title, message)
        root.destroy()
        return result
    except Exception:
        return False
