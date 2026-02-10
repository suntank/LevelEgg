"""IntGrid editing tools: brush, eraser, rectangle fill, flood fill."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from birdlevel.editor.commands import FloodFillIntGridCommand, PaintIntGridCommand
from birdlevel.editor.tools.base import Tool, ToolCategory, ToolType
from birdlevel.project.models import LayerType

if TYPE_CHECKING:
    from birdlevel.editor.editor_state import EditorState


class IntGridBrush(Tool):
    """Paint intgrid values one cell at a time."""

    def __init__(self):
        super().__init__(ToolType.INTGRID_BRUSH, ToolCategory.INTGRID)
        self._painting = False
        self._painted_cells: list[tuple[int, int, int]] = []
        self._old_values: list[int] = []
        self._visited: set[tuple[int, int]] = set()

    def on_press(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        if button != 1:
            return
        ld = state.active_layer_def
        li = state.active_layer_instance
        level = state.active_level
        if ld is None or li is None or level is None:
            return
        if ld.layer_type != LayerType.INTGRID:
            return
        self._painting = True
        self._painted_cells.clear()
        self._visited.clear()
        self._paint_cell(state, wx, wy)

    def on_drag(self, state: EditorState, wx: float, wy: float) -> None:
        if self._painting:
            self._paint_cell(state, wx, wy)

    def on_release(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        if button != 1 or not self._painting:
            return
        self._painting = False
        if self._painted_cells:
            li = state.active_layer_instance
            level = state.active_level
            if li and level:
                cmd = PaintIntGridCommand(
                    layer_inst=li,
                    cols=level.width_cells,
                    cells=list(self._painted_cells),
                )
                # Values already applied directly during drag; store old values for undo
                cmd.old_values = list(self._old_values)
                state.command_stack.undo_stack.append(cmd)
                state.command_stack.redo_stack.clear()
                state.command_stack._dirty = True
                state.needs_save = True
        self._painted_cells.clear()
        self._old_values.clear()
        self._visited.clear()

    def _paint_cell(self, state: EditorState, wx: float, wy: float) -> None:
        ld = state.active_layer_def
        li = state.active_layer_instance
        level = state.active_level
        if ld is None or li is None or level is None:
            return
        gs = ld.grid_size
        gx = int(wx // gs) if wx >= 0 else int(wx // gs)
        gy = int(wy // gs) if wy >= 0 else int(wy // gs)
        if gx < 0 or gx >= level.width_cells or gy < 0 or gy >= level.height_cells:
            return
        if (gx, gy) in self._visited:
            return
        self._visited.add((gx, gy))
        old_val = li.get_intgrid_value(gx, gy, level.width_cells)
        self._old_values.append(old_val)
        li.set_intgrid_value(gx, gy, level.width_cells, state.intgrid_value)
        self._painted_cells.append((gx, gy, state.intgrid_value))

    def draw_overlay(self, surface: pygame.Surface, state: EditorState) -> None:
        ld = state.active_layer_def
        level = state.active_level
        if ld is None or level is None:
            return
        gs = ld.grid_size
        gx, gy = state.hover_gx, state.hover_gy
        if 0 <= gx < level.width_cells and 0 <= gy < level.height_cells:
            sx, sy = state.camera.world_to_screen(gx * gs, gy * gs)
            scaled = max(1, int(gs * state.camera.zoom))
            highlight = pygame.Surface((scaled, scaled), pygame.SRCALPHA)
            highlight.fill((255, 255, 255, 80))
            surface.blit(highlight, (int(sx), int(sy)))


class IntGridEraser(Tool):
    """Erase intgrid values (paint 0)."""

    def __init__(self):
        super().__init__(ToolType.INTGRID_ERASER, ToolCategory.INTGRID)
        self._painting = False
        self._painted_cells: list[tuple[int, int, int]] = []
        self._old_values: list[int] = []
        self._visited: set[tuple[int, int]] = set()

    def on_press(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        if button != 1:
            return
        self._painting = True
        self._painted_cells.clear()
        self._old_values.clear()
        self._visited.clear()
        self._erase_cell(state, wx, wy)

    def on_drag(self, state: EditorState, wx: float, wy: float) -> None:
        if self._painting:
            self._erase_cell(state, wx, wy)

    def on_release(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        if button != 1 or not self._painting:
            return
        self._painting = False
        if self._painted_cells:
            li = state.active_layer_instance
            level = state.active_level
            if li and level:
                cmd = PaintIntGridCommand(
                    layer_inst=li,
                    cols=level.width_cells,
                    cells=list(self._painted_cells),
                )
                cmd.old_values = list(self._old_values)
                state.command_stack.undo_stack.append(cmd)
                state.command_stack.redo_stack.clear()
                state.command_stack._dirty = True
                state.needs_save = True
        self._painted_cells.clear()
        self._old_values.clear()
        self._visited.clear()

    def _erase_cell(self, state: EditorState, wx: float, wy: float) -> None:
        ld = state.active_layer_def
        li = state.active_layer_instance
        level = state.active_level
        if ld is None or li is None or level is None:
            return
        gs = ld.grid_size
        gx = int(wx // gs) if wx >= 0 else int(wx // gs)
        gy = int(wy // gs) if wy >= 0 else int(wy // gs)
        if gx < 0 or gx >= level.width_cells or gy < 0 or gy >= level.height_cells:
            return
        if (gx, gy) in self._visited:
            return
        self._visited.add((gx, gy))
        old_val = li.get_intgrid_value(gx, gy, level.width_cells)
        self._old_values.append(old_val)
        li.set_intgrid_value(gx, gy, level.width_cells, 0)
        self._painted_cells.append((gx, gy, 0))

    def draw_overlay(self, surface: pygame.Surface, state: EditorState) -> None:
        ld = state.active_layer_def
        level = state.active_level
        if ld is None or level is None:
            return
        gs = ld.grid_size
        gx, gy = state.hover_gx, state.hover_gy
        if 0 <= gx < level.width_cells and 0 <= gy < level.height_cells:
            sx, sy = state.camera.world_to_screen(gx * gs, gy * gs)
            scaled = max(1, int(gs * state.camera.zoom))
            highlight = pygame.Surface((scaled, scaled), pygame.SRCALPHA)
            highlight.fill((255, 80, 80, 80))
            surface.blit(highlight, (int(sx), int(sy)))


class IntGridRectFill(Tool):
    """Fill a rectangle region with an intgrid value."""

    def __init__(self):
        super().__init__(ToolType.INTGRID_RECT_FILL, ToolCategory.INTGRID)
        self._dragging = False
        self._start_gx: int = 0
        self._start_gy: int = 0
        self._end_gx: int = 0
        self._end_gy: int = 0

    def on_press(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        if button != 1:
            return
        ld = state.active_layer_def
        if ld is None:
            return
        gs = ld.grid_size
        self._start_gx = int(wx // gs)
        self._start_gy = int(wy // gs)
        self._end_gx = self._start_gx
        self._end_gy = self._start_gy
        self._dragging = True

    def on_drag(self, state: EditorState, wx: float, wy: float) -> None:
        if not self._dragging:
            return
        ld = state.active_layer_def
        if ld is None:
            return
        gs = ld.grid_size
        self._end_gx = int(wx // gs)
        self._end_gy = int(wy // gs)

    def on_release(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        if button != 1 or not self._dragging:
            return
        self._dragging = False
        li = state.active_layer_instance
        level = state.active_level
        if li is None or level is None:
            return

        x1 = max(0, min(self._start_gx, self._end_gx))
        y1 = max(0, min(self._start_gy, self._end_gy))
        x2 = min(level.width_cells - 1, max(self._start_gx, self._end_gx))
        y2 = min(level.height_cells - 1, max(self._start_gy, self._end_gy))

        cells = []
        old_values = []
        for gy in range(y1, y2 + 1):
            for gx in range(x1, x2 + 1):
                old_val = li.get_intgrid_value(gx, gy, level.width_cells)
                old_values.append(old_val)
                cells.append((gx, gy, state.intgrid_value))

        cmd = PaintIntGridCommand(layer_inst=li, cols=level.width_cells, cells=cells)
        cmd.old_values = old_values
        cmd.execute()
        state.command_stack.undo_stack.append(cmd)
        state.command_stack.redo_stack.clear()
        state.command_stack._dirty = True
        state.needs_save = True

    def draw_overlay(self, surface: pygame.Surface, state: EditorState) -> None:
        if not self._dragging:
            return
        ld = state.active_layer_def
        if ld is None:
            return
        gs = ld.grid_size
        x1 = min(self._start_gx, self._end_gx) * gs
        y1 = min(self._start_gy, self._end_gy) * gs
        x2 = (max(self._start_gx, self._end_gx) + 1) * gs
        y2 = (max(self._start_gy, self._end_gy) + 1) * gs
        sx1, sy1 = state.camera.world_to_screen(x1, y1)
        sx2, sy2 = state.camera.world_to_screen(x2, y2)
        rect = pygame.Rect(int(sx1), int(sy1), int(sx2 - sx1), int(sy2 - sy1))
        sel_surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        sel_surf.fill((100, 200, 255, 60))
        surface.blit(sel_surf, rect.topleft)
        pygame.draw.rect(surface, (100, 200, 255), rect, 2)


class IntGridFloodFill(Tool):
    """Flood fill intgrid cells."""

    def __init__(self):
        super().__init__(ToolType.INTGRID_FLOOD_FILL, ToolCategory.INTGRID)

    def on_press(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        if button != 1:
            return
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

        cmd = FloodFillIntGridCommand(
            layer_inst=li,
            cols=level.width_cells,
            rows=level.height_cells,
            start_x=gx,
            start_y=gy,
            fill_value=state.intgrid_value,
        )
        state.command_stack.execute(cmd)
        state.needs_save = True

    def on_drag(self, state: EditorState, wx: float, wy: float) -> None:
        pass

    def on_release(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        pass

    def draw_overlay(self, surface: pygame.Surface, state: EditorState) -> None:
        ld = state.active_layer_def
        level = state.active_level
        if ld is None or level is None:
            return
        gs = ld.grid_size
        gx, gy = state.hover_gx, state.hover_gy
        if 0 <= gx < level.width_cells and 0 <= gy < level.height_cells:
            sx, sy = state.camera.world_to_screen(gx * gs, gy * gs)
            scaled = max(1, int(gs * state.camera.zoom))
            highlight = pygame.Surface((scaled, scaled), pygame.SRCALPHA)
            highlight.fill((100, 255, 100, 80))
            surface.blit(highlight, (int(sx), int(sy)))
