"""Full JSON export for runtime consumption."""
from __future__ import annotations

import json
import os
from typing import Any

from birdlevel.project.models import Project
from birdlevel.project.serialization import project_to_dict


def export_full_json(project: Project, output_path: str) -> str:
    """Export the full project as a single runtime-friendly JSON file."""
    data = project_to_dict(project)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return output_path


def export_separate_levels(project: Project, output_dir: str) -> list[str]:
    """Export project with separate level files.

    Creates:
      - <output_dir>/project.json  (definitions + level references)
      - <output_dir>/levels/<level_uid>.json  (per-level data)
    """
    os.makedirs(output_dir, exist_ok=True)
    levels_dir = os.path.join(output_dir, "levels")
    os.makedirs(levels_dir, exist_ok=True)

    files: list[str] = []

    # Build project dict without inline level data
    data = project_to_dict(project)
    for world_data in data.get("project", {}).get("worlds", []):
        level_refs = []
        for level_data in world_data.get("levels", []):
            uid = level_data.get("uid", "unknown")
            level_path = os.path.join(levels_dir, f"{uid}.json")
            with open(level_path, "w", encoding="utf-8") as f:
                json.dump(level_data, f, indent=2, ensure_ascii=False)
            files.append(level_path)
            level_refs.append({"uid": uid, "name": level_data.get("name", ""), "file": f"levels/{uid}.json"})
        world_data["levels"] = level_refs

    project_path = os.path.join(output_dir, "project.json")
    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    files.insert(0, project_path)

    return files
