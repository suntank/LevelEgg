"""Path and backup utilities."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path


def backup_dir(project_path: str) -> str:
    """Return the .backups/ directory next to the project file."""
    d = os.path.join(os.path.dirname(os.path.abspath(project_path)), ".backups")
    os.makedirs(d, exist_ok=True)
    return d


def create_backup(project_path: str) -> str | None:
    """Copy current project file into .backups/ with timestamp."""
    if not os.path.exists(project_path):
        return None
    bdir = backup_dir(project_path)
    ts = time.strftime("%Y%m%d_%H%M%S")
    base = os.path.basename(project_path)
    name, ext = os.path.splitext(base)
    backup_name = f"{name}_{ts}{ext}"
    dest = os.path.join(bdir, backup_name)
    shutil.copy2(project_path, dest)
    return dest


def find_latest_backup(project_path: str) -> str | None:
    """Find the most recent backup file, if any."""
    bdir = backup_dir(project_path)
    if not os.path.isdir(bdir):
        return None
    backups = sorted(
        [os.path.join(bdir, f) for f in os.listdir(bdir) if not f.startswith(".")],
        key=os.path.getmtime,
        reverse=True,
    )
    return backups[0] if backups else None


def prune_backups(project_path: str, keep: int = 20) -> None:
    """Remove oldest backups, keeping at most `keep`."""
    bdir = backup_dir(project_path)
    if not os.path.isdir(bdir):
        return
    backups = sorted(
        [os.path.join(bdir, f) for f in os.listdir(bdir) if not f.startswith(".")],
        key=os.path.getmtime,
        reverse=True,
    )
    for old in backups[keep:]:
        os.unlink(old)
