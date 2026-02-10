"""Schema migration system for upgrading old project files."""
from __future__ import annotations

from typing import Any

CURRENT_VERSION = 1

# Registry of migration functions: version -> function(data) -> data
_MIGRATIONS: dict[int, callable] = {}


def register_migration(from_version: int):
    """Decorator to register a migration function."""
    def decorator(fn):
        _MIGRATIONS[from_version] = fn
        return fn
    return decorator


def migrate(data: dict) -> dict:
    """Apply all necessary migrations to bring data to current version."""
    version = data.get("format_version", 0)
    while version < CURRENT_VERSION:
        fn = _MIGRATIONS.get(version)
        if fn is None:
            raise ValueError(
                f"No migration found for format_version {version}. "
                f"Cannot upgrade to version {CURRENT_VERSION}."
            )
        data = fn(data)
        version = data.get("format_version", version + 1)
    return data


def needs_migration(data: dict) -> bool:
    """Check if the data needs migration."""
    return data.get("format_version", 0) < CURRENT_VERSION


# ---------------------------------------------------------------------------
# Example migration (placeholder for future use)
# ---------------------------------------------------------------------------

# @register_migration(from_version=0)
# def _migrate_v0_to_v1(data: dict) -> dict:
#     """Migrate from version 0 to version 1."""
#     # Add any structural changes needed
#     data["format_version"] = 1
#     project = data.get("project", data)
#     if "separate_level_files" not in project:
#         project["separate_level_files"] = False
#     return data
