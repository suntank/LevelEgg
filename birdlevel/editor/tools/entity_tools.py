"""Entity editing tools: place, select/move."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from birdlevel.editor.commands import MoveEntityCommand, PlaceEntityCommand, RemoveEntityCommand
from birdlevel.editor.tools.base import Tool, ToolCategory, ToolType
from birdlevel.project.models import EntityInstance, LayerType

if TYPE_CHECKING:
    from birdlevel.editor.editor_state import EditorState


class EntityPlace(Tool):
    """Place entity instances from the selected entity definition."""

    def __init__(self):
        super().__init__(ToolType.ENTITY_PLACE, ToolCategory.ENTITIES)

    def on_press(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        if button != 1:
            return
        ld = state.active_layer_def
        li = state.active_layer_instance
        level = state.active_level
        if ld is None or li is None or level is None:
            return
        if ld.layer_type != LayerType.ENTITY:
            return
        if state.selected_entity_def_uid is None:
            return

        edef = state.project.definitions.entity_by_uid(state.selected_entity_def_uid)
        if edef is None:
            return

        gs = ld.grid_size
        if edef.grid_locked:
            gx = int(wx // gs) * gs
            gy = int(wy // gs) * gs
        else:
            gx = int(wx)
            gy = int(wy)

        # Clamp to level bounds
        pw = level.pixel_width(gs)
        ph = level.pixel_height(gs)
        gx = max(0, min(pw - edef.width, gx))
        gy = max(0, min(ph - edef.height, gy))

        # Singleton check
        if edef.singleton and li.entities:
            existing = [e for e in li.entities if e.def_uid == edef.uid]
            if existing:
                # Move existing instead of placing new
                ent = existing[0]
                cmd = MoveEntityCommand(entity=ent, new_x=gx, new_y=gy)
                state.command_stack.execute(cmd)
                state.selected_entity_instance = ent
                state.needs_save = True
                return

        # Create new entity
        ent = EntityInstance(
            def_uid=edef.uid,
            x=gx,
            y=gy,
            width=edef.width,
            height=edef.height,
            fields={fd.name: fd.default_value for fd in edef.fields if fd.default_value is not None},
        )
        cmd = PlaceEntityCommand(layer_inst=li, entity=ent)
        state.command_stack.execute(cmd)
        state.selected_entity_instance = ent
        state.needs_save = True

    def on_drag(self, state: EditorState, wx: float, wy: float) -> None:
        pass

    def on_release(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        pass

    def draw_overlay(self, surface: pygame.Surface, state: EditorState) -> None:
        if state.selected_entity_def_uid is None:
            return
        edef = state.project.definitions.entity_by_uid(state.selected_entity_def_uid)
        if edef is None:
            return
        ld = state.active_layer_def
        if ld is None:
            return
        gs = ld.grid_size
        wx, wy = state.hover_wx, state.hover_wy
        if edef.grid_locked:
            wx = int(wx // gs) * gs
            wy = int(wy // gs) * gs
        sx, sy = state.camera.world_to_screen(wx, wy)
        sw = int(edef.width * state.camera.zoom)
        sh = int(edef.height * state.camera.zoom)
        ghost = pygame.Surface((max(1, sw), max(1, sh)), pygame.SRCALPHA)
        ghost.fill((*edef.color, 80))
        surface.blit(ghost, (int(sx), int(sy)))
        pygame.draw.rect(surface, edef.color, (int(sx), int(sy), sw, sh), 1)


class EntitySelect(Tool):
    """Select and move entity instances."""

    def __init__(self):
        super().__init__(ToolType.ENTITY_SELECT, ToolCategory.ENTITIES)
        self._dragging = False
        self._drag_entity: EntityInstance | None = None
        self._drag_offset_x: float = 0
        self._drag_offset_y: float = 0
        self._drag_start_x: int = 0
        self._drag_start_y: int = 0

    def on_press(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        if button == 1:
            self._try_select(state, wx, wy)
        elif button == 3:
            # Right-click to delete
            self._try_delete(state, wx, wy)

    def on_drag(self, state: EditorState, wx: float, wy: float) -> None:
        if not self._dragging or self._drag_entity is None:
            return
        ld = state.active_layer_def
        if ld is None:
            return
        edef = state.project.definitions.entity_by_uid(self._drag_entity.def_uid)
        gs = ld.grid_size
        new_x = int(wx - self._drag_offset_x)
        new_y = int(wy - self._drag_offset_y)
        if edef and edef.grid_locked:
            new_x = int(new_x // gs) * gs
            new_y = int(new_y // gs) * gs
        self._drag_entity.x = new_x
        self._drag_entity.y = new_y

    def on_release(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        if button != 1 or not self._dragging:
            return
        self._dragging = False
        if self._drag_entity is None:
            return
        # Create move command if position changed
        if (self._drag_entity.x != self._drag_start_x or
                self._drag_entity.y != self._drag_start_y):
            # Revert to start, then let command apply
            final_x = self._drag_entity.x
            final_y = self._drag_entity.y
            self._drag_entity.x = self._drag_start_x
            self._drag_entity.y = self._drag_start_y
            cmd = MoveEntityCommand(
                entity=self._drag_entity,
                new_x=final_x,
                new_y=final_y,
            )
            state.command_stack.execute(cmd)
            state.needs_save = True
        self._drag_entity = None

    def _try_select(self, state: EditorState, wx: float, wy: float) -> None:
        li = state.active_layer_instance
        if li is None or li.entities is None:
            state.selected_entity_instance = None
            return
        # Find topmost entity under cursor (reverse order = on top)
        for ent in reversed(li.entities):
            if (ent.x <= wx < ent.x + ent.width and
                    ent.y <= wy < ent.y + ent.height):
                state.selected_entity_instance = ent
                self._dragging = True
                self._drag_entity = ent
                self._drag_offset_x = wx - ent.x
                self._drag_offset_y = wy - ent.y
                self._drag_start_x = ent.x
                self._drag_start_y = ent.y
                return
        state.selected_entity_instance = None

    def _try_delete(self, state: EditorState, wx: float, wy: float) -> None:
        li = state.active_layer_instance
        if li is None or li.entities is None:
            return
        for ent in reversed(li.entities):
            if (ent.x <= wx < ent.x + ent.width and
                    ent.y <= wy < ent.y + ent.height):
                cmd = RemoveEntityCommand(layer_inst=li, entity=ent)
                state.command_stack.execute(cmd)
                if state.selected_entity_instance == ent:
                    state.selected_entity_instance = None
                state.needs_save = True
                return

    def draw_overlay(self, surface: pygame.Surface, state: EditorState) -> None:
        ent = state.selected_entity_instance
        if ent is None:
            return
        sx, sy = state.camera.world_to_screen(ent.x, ent.y)
        sw = int(ent.width * state.camera.zoom)
        sh = int(ent.height * state.camera.zoom)
        pygame.draw.rect(surface, (255, 255, 0), (int(sx) - 1, int(sy) - 1, sw + 2, sh + 2), 2)
