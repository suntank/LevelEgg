"""Input routing: keyboard shortcuts, mouse events, tool dispatching."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame

from birdlevel.editor.commands import (
    PaintIntGridCommand,
    PaintTileCommand,
    RemoveEntityCommand,
)
from birdlevel.editor.tools.base import ToolCategory, ToolType
from birdlevel.project.models import LayerType

if TYPE_CHECKING:
    from birdlevel.editor.editor_state import EditorState
    from birdlevel.editor.tools.base import ToolManager


class InputHandler:
    """Routes raw pygame events to the editor state, camera, tools, and UI."""

    def __init__(self):
        self._panning = False
        self._pan_start: tuple[int, int] = (0, 0)
        self._callbacks: dict[str, Callable] = {}
        # Right-click erase state
        self._erasing = False
        self._erase_cells: list[tuple[int, int, int]] = []
        self._erase_old_values: list[int] = []
        self._erase_visited: set[tuple[int, int]] = set()

    def set_callbacks(self, callbacks: dict[str, Callable]) -> None:
        """Expected keys: save, open, save_as, export."""
        self._callbacks = callbacks

    def handle_event(
        self,
        event: pygame.event.Event,
        state: EditorState,
        tool_manager: ToolManager,
        ui_consumed: bool = False,
    ) -> None:
        """Process a single pygame event."""

        mx, my = pygame.mouse.get_pos()

        if event.type == pygame.KEYDOWN:
            self._handle_key(event, state, tool_manager)
            return

        # Middle mouse pan
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            self._panning = True
            self._pan_start = (mx, my)
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self._panning = False
            return

        if event.type == pygame.MOUSEMOTION and self._panning:
            dx = mx - self._pan_start[0]
            dy = my - self._pan_start[1]
            state.camera.pan(dx, dy)
            self._pan_start = (mx, my)
            return

        # Mouse wheel zoom
        if event.type == pygame.MOUSEWHEEL:
            if not ui_consumed:
                factor = 1.1 if event.y > 0 else 0.9
                state.camera.zoom_at(mx, my, factor)
            return

        # Update hover position
        if event.type == pygame.MOUSEMOTION:
            wx, wy = state.camera.screen_to_world(mx, my)
            state.hover_wx = wx
            state.hover_wy = wy
            ld = state.active_layer_def
            gs = ld.grid_size if ld else state.project.grid_size
            state.hover_gx = int(wx // gs) if wx >= 0 else int(wx // gs)
            state.hover_gy = int(wy // gs) if wy >= 0 else int(wy // gs)

        # Tool events (only if not consumed by UI and in viewport)
        if ui_consumed:
            return

        if not state.camera.viewport.collidepoint(mx, my):
            return

        tool = tool_manager.active_tool
        if tool is None:
            return

        # Block editing on locked layers
        li = state.active_layer_instance
        if li and li.locked and event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            return

        wx, wy = state.camera.screen_to_world(mx, my)

        # Universal right-click erase
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._start_erase(state, wx, wy)
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self._finish_erase(state)
            return
        if event.type == pygame.MOUSEMOTION and self._erasing and pygame.mouse.get_pressed()[2]:
            self._erase_at(state, wx, wy)
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            tool.on_press(state, wx, wy, event.button)
        elif event.type == pygame.MOUSEBUTTONUP:
            tool.on_release(state, wx, wy, event.button)
        elif event.type == pygame.MOUSEMOTION:
            if pygame.mouse.get_pressed()[0]:
                tool.on_drag(state, wx, wy)
            else:
                tool.on_hover(state, wx, wy)

    # ------------------------------------------------------------------
    # Universal right-click erase
    # ------------------------------------------------------------------

    def _start_erase(self, state: EditorState, wx: float, wy: float) -> None:
        ld = state.active_layer_def
        li = state.active_layer_instance
        level = state.active_level
        if ld is None or li is None or level is None:
            return

        if ld.layer_type == LayerType.ENTITY:
            self._erase_entity_at(state, wx, wy)
            return

        self._erasing = True
        self._erase_cells.clear()
        self._erase_old_values.clear()
        self._erase_visited.clear()
        self._erase_at(state, wx, wy)

    def _erase_at(self, state: EditorState, wx: float, wy: float) -> None:
        ld = state.active_layer_def
        li = state.active_layer_instance
        level = state.active_level
        if ld is None or li is None or level is None:
            return
        gs = ld.grid_size
        gx = int(wx // gs)
        gy = int(wy // gs)
        if gx < 0 or gx >= level.width_cells or gy < 0 or gy >= level.height_cells:
            return
        if (gx, gy) in self._erase_visited:
            return
        self._erase_visited.add((gx, gy))

        if ld.layer_type == LayerType.INTGRID:
            old_val = li.get_intgrid_value(gx, gy, level.width_cells)
            self._erase_old_values.append(old_val)
            li.set_intgrid_value(gx, gy, level.width_cells, 0)
            self._erase_cells.append((gx, gy, 0))
        elif ld.layer_type in (LayerType.TILES, LayerType.AUTO_LAYER):
            old_val = li.get_tile(gx, gy, level.width_cells)
            self._erase_old_values.append(old_val)
            li.set_tile(gx, gy, level.width_cells, -1)
            self._erase_cells.append((gx, gy, -1))

    def _finish_erase(self, state: EditorState) -> None:
        if not self._erasing:
            return
        self._erasing = False
        li = state.active_layer_instance
        level = state.active_level
        ld = state.active_layer_def
        if not self._erase_cells or li is None or level is None or ld is None:
            self._erase_cells.clear()
            self._erase_old_values.clear()
            self._erase_visited.clear()
            return

        if ld.layer_type == LayerType.INTGRID:
            cmd = PaintIntGridCommand(
                layer_inst=li, cols=level.width_cells,
                cells=list(self._erase_cells),
            )
            cmd.old_values = list(self._erase_old_values)
        elif ld.layer_type in (LayerType.TILES, LayerType.AUTO_LAYER):
            cmd = PaintTileCommand(
                layer_inst=li, cols=level.width_cells,
                cells=list(self._erase_cells),
            )
            cmd.old_values = list(self._erase_old_values)
        else:
            self._erase_cells.clear()
            self._erase_old_values.clear()
            self._erase_visited.clear()
            return

        state.command_stack.undo_stack.append(cmd)
        state.command_stack.redo_stack.clear()
        state.command_stack._dirty = True
        state.needs_save = True
        self._erase_cells.clear()
        self._erase_old_values.clear()
        self._erase_visited.clear()

    def _erase_entity_at(self, state: EditorState, wx: float, wy: float) -> None:
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

    def _handle_key(self, event: pygame.event.Event, state: EditorState,
                    tool_manager: ToolManager) -> None:
        mods = pygame.key.get_mods()
        ctrl = mods & pygame.KMOD_CTRL

        shift = mods & pygame.KMOD_SHIFT

        if ctrl and event.key == pygame.K_o:
            cb = self._callbacks.get("open")
            if cb:
                cb()
            return

        if ctrl and shift and event.key == pygame.K_s:
            cb = self._callbacks.get("save_as")
            if cb:
                cb()
            return

        if ctrl and event.key == pygame.K_s:
            cb = self._callbacks.get("save")
            if cb:
                cb()
            return

        if ctrl and event.key == pygame.K_e:
            cb = self._callbacks.get("export")
            if cb:
                cb()
            return

        if ctrl and event.key == pygame.K_z:
            if shift:
                if state.command_stack.redo():
                    state.set_notification("Redo")
            else:
                if state.command_stack.undo():
                    state.set_notification("Undo")
            return

        if ctrl and event.key == pygame.K_y:
            if state.command_stack.redo():
                state.set_notification("Redo")
            return

        # Tool category switching (number keys)
        if event.key == pygame.K_1:
            tool_manager.set_category(ToolCategory.INTGRID)
            for i, ld in enumerate(state.project.definitions.layers):
                if ld.layer_type.value == "intgrid":
                    state.set_active_layer(i)
                    break
            state.set_notification("IntGrid tools")
            return

        if event.key == pygame.K_2:
            tool_manager.set_category(ToolCategory.TILES)
            for i, ld in enumerate(state.project.definitions.layers):
                if ld.layer_type.value == "tiles":
                    state.set_active_layer(i)
                    break
            state.set_notification("Tile tools")
            return

        if event.key == pygame.K_3:
            tool_manager.set_category(ToolCategory.ENTITIES)
            for i, ld in enumerate(state.project.definitions.layers):
                if ld.layer_type.value == "entity":
                    state.set_active_layer(i)
                    break
            state.set_notification("Entity tools")
            return

        # Tool shortcuts (context-sensitive per active category)
        cat = tool_manager.active_category
        tool_map: dict[int, ToolType | None] = {}

        if cat == ToolCategory.INTGRID:
            tool_map = {
                pygame.K_b: ToolType.INTGRID_BRUSH,
                pygame.K_e: ToolType.INTGRID_ERASER,
                pygame.K_r: ToolType.INTGRID_RECT_FILL,
                pygame.K_f: ToolType.INTGRID_FLOOD_FILL,
            }
        elif cat == ToolCategory.TILES:
            tool_map = {
                pygame.K_b: ToolType.TILE_BRUSH,
                pygame.K_r: ToolType.TILE_RECT,
                pygame.K_t: ToolType.TILE_STAMP,
                pygame.K_q: ToolType.TILE_RANDOM,
                pygame.K_f: ToolType.TILE_FLOOD_FILL,
                pygame.K_i: ToolType.TILE_EYEDROPPER,
            }
        elif cat == ToolCategory.ENTITIES:
            tool_map = {
                pygame.K_b: ToolType.ENTITY_PLACE,
                pygame.K_e: ToolType.ENTITY_SELECT,
            }

        tt = tool_map.get(event.key)
        if tt is not None:
            tool_manager.set_active(tt)
            state.set_notification(f"Tool: {tool_manager.active_tool.name}")
            return

        # Toggle grid
        if event.key == pygame.K_g:
            state.show_grid = not state.show_grid
            state.set_notification("Grid " + ("ON" if state.show_grid else "OFF"))
            return

        # Toggle show all layers vs active only
        if event.key == pygame.K_a and not ctrl:
            state.show_all_layers = not state.show_all_layers
            tag = "All layers" if state.show_all_layers else "Active layer only"
            state.set_notification(tag)
            return

        # Home: fit camera to level
        if event.key == pygame.K_h:
            level = state.active_level
            if level:
                gs = state.project.grid_size
                state.camera.center_on(level.pixel_width(gs) / 2,
                                       level.pixel_height(gs) / 2)
                state.camera.zoom = 1.0
                state.set_notification("Camera reset")
            return

        # Delete selected entity
        if event.key == pygame.K_DELETE:
            ent = state.selected_entity_instance
            li = state.active_layer_instance
            if ent and li and li.entities:
                from birdlevel.editor.commands import RemoveEntityCommand
                cmd = RemoveEntityCommand(layer_inst=li, entity=ent)
                state.command_stack.execute(cmd)
                state.selected_entity_instance = None
                state.needs_save = True
                state.set_notification("Entity deleted")
            return

        # Toggle panels
        if event.key == pygame.K_TAB:
            state.panels_collapsed = not state.panels_collapsed
            return
