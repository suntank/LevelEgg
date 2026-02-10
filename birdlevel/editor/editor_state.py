"""Editor state: tracks selection, current level, active layer, etc.

Separate from the project data model so UI/editor concerns don't pollute the data.
"""
from __future__ import annotations

from typing import Any

from birdlevel.editor.commands import CommandStack
from birdlevel.project.models import (
    EntityInstance,
    LayerDef,
    LayerInstance,
    Level,
    Project,
    World,
)
from birdlevel.render.camera import Camera


class EditorState:
    """Mutable editor session state."""

    def __init__(self, project: Project):
        self.project = project
        self.camera = Camera()
        self.command_stack = CommandStack()

        # Current selection
        self._active_world_idx: int = 0
        self._active_level_idx: int = 0
        self._active_layer_idx: int = 0

        # IntGrid selected value
        self.intgrid_value: int = 1

        # Tile selection
        self.selected_tile_id: int = 0
        self.tile_stamp: list[list[int]] | None = None  # 2D array of tile IDs
        self.random_tiles: list[int] = []
        self.random_mode: bool = False

        # Entity selection
        self.selected_entity_def_uid: str | None = None
        self.selected_entity_instance: EntityInstance | None = None

        # UI toggles
        self.show_grid: bool = True
        self.show_all_layers: bool = True
        self.panels_collapsed: bool = False

        # Hover position in world coords
        self.hover_wx: float = 0.0
        self.hover_wy: float = 0.0
        self.hover_gx: int = 0
        self.hover_gy: int = 0

        # Status / notifications
        self.status_text: str = "Ready"
        self.notification: str = ""
        self.notification_timer: float = 0.0

        # Dirty flag for autosave
        self.needs_save: bool = False
        self.autosave_timer: float = 0.0
        self.autosave_interval: float = 120.0  # seconds

    # -----------------------------------------------------------------------
    # Active world / level / layer accessors
    # -----------------------------------------------------------------------

    @property
    def active_world(self) -> World | None:
        worlds = self.project.worlds
        if 0 <= self._active_world_idx < len(worlds):
            return worlds[self._active_world_idx]
        return worlds[0] if worlds else None

    @property
    def active_level(self) -> Level | None:
        w = self.active_world
        if w is None:
            return None
        if 0 <= self._active_level_idx < len(w.levels):
            return w.levels[self._active_level_idx]
        return w.levels[0] if w.levels else None

    @property
    def active_layer_def(self) -> LayerDef | None:
        defs = self.project.definitions.layers
        if 0 <= self._active_layer_idx < len(defs):
            return defs[self._active_layer_idx]
        return defs[0] if defs else None

    @property
    def active_layer_instance(self) -> LayerInstance | None:
        level = self.active_level
        ld = self.active_layer_def
        if level is None or ld is None:
            return None
        return level.get_layer_instance(ld.uid)

    def set_active_world(self, idx: int) -> None:
        self._active_world_idx = idx
        self._active_level_idx = 0

    def set_active_level(self, idx: int) -> None:
        self._active_level_idx = idx

    def set_active_layer(self, idx: int) -> None:
        self._active_layer_idx = idx

    @property
    def active_world_idx(self) -> int:
        return self._active_world_idx

    @property
    def active_level_idx(self) -> int:
        return self._active_level_idx

    @property
    def active_layer_idx(self) -> int:
        return self._active_layer_idx

    def set_notification(self, text: str, duration: float = 3.0) -> None:
        self.notification = text
        self.notification_timer = duration

    def update_timers(self, dt: float) -> None:
        if self.notification_timer > 0:
            self.notification_timer -= dt
            if self.notification_timer <= 0:
                self.notification = ""
        self.autosave_timer += dt
