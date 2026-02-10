"""High-level UI panels: top bar, left dock, right dock, bottom bar."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING, Callable

import pygame

from birdlevel.app.ui.theme import Theme
from birdlevel.app.ui.widgets import (
    Button,
    Checkbox,
    ColorSwatch,
    DropdownSelect,
    Label,
    ListItem,
    NumberInput,
    Panel,
    TextInput,
    UIEvent,
    Widget,
)
from birdlevel.project.models import (
    EntityDef,
    FieldType,
    IntGridValueDef,
    LayerDef,
    LayerType,
    Level,
    World,
)

if TYPE_CHECKING:
    from birdlevel.editor.editor_state import EditorState


# ---------------------------------------------------------------------------
# Top bar
# ---------------------------------------------------------------------------

class TopBar:
    """Top menu bar with project name, save, undo/redo, export."""

    def __init__(self, screen_w: int):
        self.rect = pygame.Rect(0, 0, screen_w, Theme.TOP_BAR_HEIGHT)
        self.buttons: list[Button] = []
        self._callbacks: dict[str, Callable] = {}

    def setup(self, callbacks: dict[str, Callable]) -> None:
        self._callbacks = callbacks
        bx = Theme.PANEL_PADDING
        bw = 70
        bh = Theme.TOP_BAR_HEIGHT - 8
        gap = 4

        for label, key in [("Open", "open"), ("Save", "save"), ("Save As", "save_as"),
                           ("Undo", "undo"), ("Redo", "redo"),
                           ("Export", "export"), ("New Level", "new_level"),
                           ("Add Layer", "add_layer"), ("Resize", "resize_level"),
                           ("Tileset", "import_tileset")]:
            btn = Button(bx, 4, bw, bh, label=label,
                         on_click=lambda e, k=key: self._callbacks.get(k, lambda: None)())
            self.buttons.append(btn)
            bx += bw + gap

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        for btn in self.buttons:
            btn.update_hover(mx, my)
            if btn.handle_event(event, mx, my):
                return True
        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             project_name: str, is_dirty: bool) -> None:
        pygame.draw.rect(surface, Theme.BG_HEADER, self.rect)
        pygame.draw.line(surface, Theme.BORDER, (0, self.rect.bottom - 1),
                         (self.rect.right, self.rect.bottom - 1))

        for btn in self.buttons:
            btn.draw(surface, font)

        # Project name + dirty indicator
        name_text = project_name + (" *" if is_dirty else "")
        name_lbl = font.render(name_text, True, Theme.TEXT_ACCENT)
        surface.blit(name_lbl, (self.rect.right - name_lbl.get_width() - 12,
                                (self.rect.h - name_lbl.get_height()) // 2))


# ---------------------------------------------------------------------------
# Bottom bar
# ---------------------------------------------------------------------------

class BottomBar:
    """Status bar at the bottom."""

    def __init__(self, screen_w: int, screen_h: int):
        self.rect = pygame.Rect(0, screen_h - Theme.BOTTOM_BAR_HEIGHT,
                                screen_w, Theme.BOTTOM_BAR_HEIGHT)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             state: EditorState) -> None:
        pygame.draw.rect(surface, Theme.BG_HEADER, self.rect)
        pygame.draw.line(surface, Theme.BORDER, (self.rect.x, self.rect.y),
                         (self.rect.right, self.rect.y))

        # Coordinates
        coord_text = f"Grid: ({state.hover_gx}, {state.hover_gy})  World: ({state.hover_wx:.0f}, {state.hover_wy:.0f})  Zoom: {state.camera.zoom:.1f}x"
        coord_lbl = font.render(coord_text, True, Theme.TEXT_DIM)
        surface.blit(coord_lbl, (self.rect.x + 8, self.rect.y + 5))

        # Status
        status_lbl = font.render(state.status_text, True, Theme.TEXT)
        surface.blit(status_lbl, (self.rect.x + 400, self.rect.y + 5))

        # Notification
        if state.notification:
            notif_lbl = font.render(state.notification, True, Theme.TEXT_SUCCESS)
            surface.blit(notif_lbl, (self.rect.right - notif_lbl.get_width() - 12,
                                     self.rect.y + 5))

        # Autosave indicator
        if state.needs_save:
            save_lbl = font.render("Unsaved", True, Theme.TEXT_WARNING)
            surface.blit(save_lbl, (self.rect.right - save_lbl.get_width() - 150,
                                    self.rect.y + 5))


# ---------------------------------------------------------------------------
# Left dock: world tree + layer stack + tool palette
# ---------------------------------------------------------------------------

class LeftDock:
    """Left panel with world/level tree, layer stack, and tool palette."""

    SECTION_HEADER_H = 20
    SWATCH_ROW_H = 22

    def __init__(self, screen_h: int):
        top = Theme.TOP_BAR_HEIGHT
        h = screen_h - top - Theme.BOTTOM_BAR_HEIGHT
        self.rect = pygame.Rect(0, top, Theme.LEFT_PANEL_WIDTH, h)
        self.visible = True

        # World/Level tree items
        self._level_items: list[ListItem] = []
        self._layer_items: list[ListItem] = []
        self._tool_buttons: list[Button] = []
        self._intgrid_swatches: list[tuple[ColorSwatch, Label]] = []

        # Layout rects computed once by _layout(), used by draw and handle_event
        # Each entry: (kind, index, abs_rect, extra_data)
        self._hit_rects: list[tuple[str, int, pygame.Rect, Any]] = []

        self._on_select_level: Callable | None = None
        self._on_select_layer: Callable | None = None
        self._on_select_tool: Callable | None = None
        self._on_select_intgrid_value: Callable | None = None
        self._on_toggle_layer_visible: Callable | None = None
        self._on_toggle_layer_locked: Callable | None = None
        self._on_move_layer: Callable | None = None
        self._on_change_layer_opacity: Callable | None = None
        self._on_delete_layer: Callable | None = None

    def setup(self, callbacks: dict[str, Callable]) -> None:
        self._on_select_level = callbacks.get("select_level")
        self._on_select_layer = callbacks.get("select_layer")
        self._on_select_tool = callbacks.get("select_tool")
        self._on_select_intgrid_value = callbacks.get("select_intgrid_value")
        self._on_toggle_layer_visible = callbacks.get("toggle_layer_visible")
        self._on_toggle_layer_locked = callbacks.get("toggle_layer_locked")
        self._on_move_layer = callbacks.get("move_layer")
        self._on_change_layer_opacity = callbacks.get("change_layer_opacity")
        self._on_delete_layer = callbacks.get("delete_layer")

    def rebuild(self, state: EditorState) -> None:
        """Rebuild the list items and compute layout rects."""
        self._level_items.clear()
        self._layer_items.clear()
        self._tool_buttons.clear()
        self._intgrid_swatches.clear()
        self._hit_rects.clear()

        w = self.rect.w - Theme.PANEL_PADDING * 2
        px = self.rect.x + Theme.PANEL_PADDING
        y = self.rect.y + 4

        # ---- Levels section ----
        y += self.SECTION_HEADER_H
        world = state.active_world
        if world:
            for i, level in enumerate(world.levels):
                item = ListItem(0, 0, w, text=level.name, data=i)
                item.selected = (i == state.active_level_idx)
                self._level_items.append(item)
                self._hit_rects.append(("level", i, pygame.Rect(px, y, w, Theme.ITEM_HEIGHT), None))
                y += Theme.ITEM_HEIGHT

        y += 8

        # ---- Layers section ----
        y += self.SECTION_HEADER_H
        layer_type_colors = {
            LayerType.INTGRID: Theme.LAYER_INTGRID,
            LayerType.TILES: Theme.LAYER_TILES,
            LayerType.ENTITY: Theme.LAYER_ENTITY,
            LayerType.AUTO_LAYER: Theme.LAYER_AUTO,
        }
        level = state.active_level
        for i, ld in enumerate(state.project.definitions.layers):
            color = layer_type_colors.get(ld.layer_type, Theme.TEXT_DIM)
            li = level.get_layer_instance(ld.uid) if level else None
            item = ListItem(
                0, 0, w, text=f"{ld.name} [{ld.layer_type.value}]", data=i,
                indicator_color=color,
            )
            item.selected = (i == state.active_layer_idx)
            self._layer_items.append(item)
            self._hit_rects.append(("layer", i, pygame.Rect(px, y, w, Theme.ITEM_HEIGHT),
                                    {"visible": li.visible if li else True,
                                     "locked": li.locked if li else False,
                                     "opacity": li.opacity if li else 1.0}))
            y += Theme.ITEM_HEIGHT

        # Active layer opacity row
        if level and state.active_layer_def:
            ali = level.get_layer_instance(state.active_layer_def.uid)
            if ali:
                self._hit_rects.append(("opacity_row", 0, pygame.Rect(px, y, w, 20),
                                        {"opacity": ali.opacity}))
                y += 24

        y += 8

        # ---- Tool buttons ----
        y += self.SECTION_HEADER_H
        from birdlevel.editor.tools.base import ToolType
        active_ld = state.active_layer_def
        tool_list = self._get_tool_list(active_ld)
        bx = px
        bw = 52
        for idx, (label, tt) in enumerate(tool_list):
            btn = Button(0, 0, bw, Theme.BUTTON_HEIGHT, label=label, toggle=True)
            self._tool_buttons.append(btn)
            self._hit_rects.append(("tool", idx, pygame.Rect(bx, y, bw, Theme.BUTTON_HEIGHT), tt))
            bx += bw + 2
            if bx + bw > self.rect.right - Theme.PANEL_PADDING:
                bx = px
                y += Theme.BUTTON_HEIGHT + 2

        y += Theme.BUTTON_HEIGHT + 8

        # ---- IntGrid value palette ----
        if active_ld and active_ld.layer_type == LayerType.INTGRID:
            y += self.SECTION_HEADER_H
            for vd in active_ld.intgrid_values:
                swatch = ColorSwatch(0, 0, size=18, color=vd.color)
                swatch.selected = (vd.value == state.intgrid_value)
                lbl = Label(0, 0, text=f"{vd.value}: {vd.name}", color=Theme.TEXT)
                self._intgrid_swatches.append((swatch, lbl))
                self._hit_rects.append(("intgrid_val", vd.value, pygame.Rect(px, y, w, 20), None))
                y += self.SWATCH_ROW_H

    @staticmethod
    def _get_tool_list(active_ld) -> list:
        from birdlevel.editor.tools.base import ToolType
        if active_ld is None:
            return []
        tool_map = {
            LayerType.INTGRID: [
                ("Brush", ToolType.INTGRID_BRUSH),
                ("Eraser", ToolType.INTGRID_ERASER),
                ("Rect", ToolType.INTGRID_RECT_FILL),
                ("Fill", ToolType.INTGRID_FLOOD_FILL),
            ],
            LayerType.TILES: [
                ("Brush", ToolType.TILE_BRUSH),
                ("Rect", ToolType.TILE_RECT),
                ("Fill", ToolType.TILE_FLOOD_FILL),
                ("Stamp", ToolType.TILE_STAMP),
                ("Random", ToolType.TILE_RANDOM),
                ("Pick", ToolType.TILE_EYEDROPPER),
            ],
            LayerType.ENTITY: [
                ("Select", ToolType.ENTITY_SELECT),
                ("Place", ToolType.ENTITY_PLACE),
            ],
        }
        return tool_map.get(active_ld.layer_type, [])

    def handle_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        if not self.visible:
            return False
        if not self.rect.collidepoint(mx, my):
            return False

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL)

        for kind, idx, ar, extra in self._hit_rects:
            if not ar.collidepoint(mx, my):
                continue

            if kind == "layer":
                # Check sub-buttons: visibility eye, lock, up, down, delete
                right_edge = ar.right
                btn_w = 18
                btn_h = 18
                btn_y = ar.y + (ar.h - btn_h) // 2

                # Buttons from right: [X] [down] [up] [lock] [eye]
                del_rect = pygame.Rect(right_edge - btn_w - 2, btn_y, btn_w, btn_h)
                down_rect = pygame.Rect(del_rect.x - btn_w - 2, btn_y, btn_w, btn_h)
                up_rect = pygame.Rect(down_rect.x - btn_w - 2, btn_y, btn_w, btn_h)
                lock_rect = pygame.Rect(up_rect.x - btn_w - 2, btn_y, btn_w, btn_h)
                eye_rect = pygame.Rect(lock_rect.x - btn_w - 2, btn_y, btn_w, btn_h)

                if del_rect.collidepoint(mx, my):
                    if self._on_delete_layer:
                        self._on_delete_layer(UIEvent(None, idx))
                    return True
                if eye_rect.collidepoint(mx, my):
                    if self._on_toggle_layer_visible:
                        self._on_toggle_layer_visible(UIEvent(None, idx))
                    return True
                if lock_rect.collidepoint(mx, my):
                    if self._on_toggle_layer_locked:
                        self._on_toggle_layer_locked(UIEvent(None, idx))
                    return True
                if up_rect.collidepoint(mx, my):
                    if self._on_move_layer:
                        self._on_move_layer(UIEvent(None, ("up", idx)))
                    return True
                if down_rect.collidepoint(mx, my):
                    if self._on_move_layer:
                        self._on_move_layer(UIEvent(None, ("down", idx)))
                    return True

                # Otherwise select layer
                if self._on_select_layer:
                    self._on_select_layer(UIEvent(None, idx))
                return True

            if kind == "opacity_row":
                # [-] and [+] buttons for opacity
                btn_w = 22
                btn_h = 18
                btn_y = ar.y + 1
                plus_rect = pygame.Rect(ar.right - btn_w - 2, btn_y, btn_w, btn_h)
                minus_rect = pygame.Rect(plus_rect.x - btn_w - 4, btn_y, btn_w, btn_h)
                if plus_rect.collidepoint(mx, my):
                    if self._on_change_layer_opacity:
                        self._on_change_layer_opacity(UIEvent(None, 0.1))
                    return True
                if minus_rect.collidepoint(mx, my):
                    if self._on_change_layer_opacity:
                        self._on_change_layer_opacity(UIEvent(None, -0.1))
                    return True
                return True

            if kind == "level":
                if self._on_select_level:
                    self._on_select_level(UIEvent(None, idx))
                return True

            if kind == "tool":
                if self._on_select_tool:
                    self._on_select_tool(UIEvent(None, extra))
                return True

            if kind == "intgrid_val":
                if self._on_select_intgrid_value:
                    self._on_select_intgrid_value(UIEvent(None, idx))
                return True

        return True  # Consume click in panel

    def update_hover(self, mx: int, my: int) -> None:
        """Update hover state for all items using hit rects."""
        for item in self._level_items:
            item._hovered = False
        for item in self._layer_items:
            item._hovered = False
        for btn in self._tool_buttons:
            btn._hovered = False

        for kind, idx, ar, extra in self._hit_rects:
            if ar.collidepoint(mx, my):
                if kind == "level" and idx < len(self._level_items):
                    self._level_items[idx]._hovered = True
                elif kind == "layer" and idx < len(self._layer_items):
                    self._layer_items[idx]._hovered = True
                elif kind == "tool" and idx < len(self._tool_buttons):
                    self._tool_buttons[idx]._hovered = True

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             font_small: pygame.font.Font, state: EditorState) -> None:
        if not self.visible:
            return
        pygame.draw.rect(surface, Theme.BG_PANEL, self.rect)
        pygame.draw.line(surface, Theme.BORDER, (self.rect.right - 1, self.rect.y),
                         (self.rect.right - 1, self.rect.bottom))

        clip = surface.get_clip()
        surface.set_clip(self.rect)

        px = self.rect.x + Theme.PANEL_PADDING
        w = self.rect.w - Theme.PANEL_PADDING * 2
        y = self.rect.y + 4

        # ---- LEVELS ----
        hdr = font.render("LEVELS", True, Theme.TEXT_ACCENT)
        surface.blit(hdr, (px, y))
        y += self.SECTION_HEADER_H
        for item in self._level_items:
            ar = pygame.Rect(px, y, w, Theme.ITEM_HEIGHT)
            if item.selected:
                pygame.draw.rect(surface, Theme.BG_SELECTED, ar)
            elif item._hovered:
                pygame.draw.rect(surface, Theme.BG_HOVER, ar)
            lbl = font_small.render(item.text, True, Theme.TEXT_BRIGHT if item.selected else Theme.TEXT)
            surface.blit(lbl, (ar.x + Theme.PANEL_PADDING, ar.y + 4))
            y += Theme.ITEM_HEIGHT

        y += 8

        # ---- LAYERS ----
        hdr = font.render("LAYERS", True, Theme.TEXT_ACCENT)
        surface.blit(hdr, (px, y))
        y += self.SECTION_HEADER_H
        level = state.active_level
        for i, item in enumerate(self._layer_items):
            ar = pygame.Rect(px, y, w, Theme.ITEM_HEIGHT)
            if item.selected:
                pygame.draw.rect(surface, Theme.BG_SELECTED, ar)
            elif item._hovered:
                pygame.draw.rect(surface, Theme.BG_HOVER, ar)
            text_x = ar.x + Theme.PANEL_PADDING
            if item.indicator_color:
                ind_rect = pygame.Rect(ar.x + 4, ar.y + 6, 12, 14)
                pygame.draw.rect(surface, item.indicator_color, ind_rect, border_radius=2)
                text_x = ar.x + 22
            lbl = font_small.render(item.text, True, Theme.TEXT_BRIGHT if item.selected else Theme.TEXT)
            surface.blit(lbl, (text_x, ar.y + 4))

            # Layer control buttons (right side): eye, lock, up, down, delete
            btn_w = 18
            btn_h = 18
            btn_y = ar.y + (ar.h - btn_h) // 2
            right_edge = ar.right
            ld_idx = item.data if hasattr(item, 'data') else i
            ld_list = state.project.definitions.layers
            li = level.get_layer_instance(ld_list[ld_idx].uid) if level and ld_idx < len(ld_list) else None

            # Delete X
            del_rect = pygame.Rect(right_edge - btn_w - 2, btn_y, btn_w, btn_h)
            self._draw_mini_btn(surface, font_small, del_rect, "X", Theme.TEXT_ERROR)
            # Down arrow
            down_rect = pygame.Rect(del_rect.x - btn_w - 2, btn_y, btn_w, btn_h)
            self._draw_mini_btn(surface, font_small, down_rect, "\u25bc", Theme.TEXT_DIM)
            # Up arrow
            up_rect = pygame.Rect(down_rect.x - btn_w - 2, btn_y, btn_w, btn_h)
            self._draw_mini_btn(surface, font_small, up_rect, "\u25b2", Theme.TEXT_DIM)
            # Lock
            lock_rect = pygame.Rect(up_rect.x - btn_w - 2, btn_y, btn_w, btn_h)
            locked = li.locked if li else False
            lock_color = Theme.TEXT_WARNING if locked else Theme.TEXT_DIM
            self._draw_mini_btn(surface, font_small, lock_rect, "L", lock_color)
            # Visibility eye
            eye_rect = pygame.Rect(lock_rect.x - btn_w - 2, btn_y, btn_w, btn_h)
            vis = li.visible if li else True
            eye_color = Theme.TEXT_BRIGHT if vis else Theme.TEXT_DIM
            self._draw_mini_btn(surface, font_small, eye_rect, "E", eye_color)

            y += Theme.ITEM_HEIGHT

        # Active layer opacity row
        if level and state.active_layer_def:
            ali = level.get_layer_instance(state.active_layer_def.uid)
            if ali:
                opacity_pct = int(ali.opacity * 100)
                olbl = font_small.render(f"Opacity: {opacity_pct}%", True, Theme.TEXT_DIM)
                surface.blit(olbl, (px, y + 2))
                btn_w = 22
                btn_h = 18
                btn_y2 = y + 1
                plus_rect = pygame.Rect(px + w - btn_w - 2, btn_y2, btn_w, btn_h)
                minus_rect = pygame.Rect(plus_rect.x - btn_w - 4, btn_y2, btn_w, btn_h)
                self._draw_mini_btn(surface, font_small, plus_rect, "+", Theme.TEXT_SUCCESS)
                self._draw_mini_btn(surface, font_small, minus_rect, "-", Theme.TEXT_WARNING)
                y += 24

        y += 8

        # ---- TOOLS ----
        hdr = font.render("TOOLS", True, Theme.TEXT_ACCENT)
        surface.blit(hdr, (px, y))
        y += self.SECTION_HEADER_H
        bx = px
        for btn in self._tool_buttons:
            ar = pygame.Rect(bx, y, btn.rect.w, btn.rect.h)
            bg = Theme.BG_BUTTON_ACTIVE if btn.toggled else (Theme.BG_BUTTON_HOVER if btn._hovered else Theme.BG_BUTTON)
            pygame.draw.rect(surface, bg, ar, border_radius=3)
            pygame.draw.rect(surface, Theme.BORDER_LIGHT, ar, 1, border_radius=3)
            blbl = font_small.render(btn.label, True, Theme.TEXT_BRIGHT if btn.toggled else Theme.TEXT)
            surface.blit(blbl, (ar.x + (ar.w - blbl.get_width()) // 2,
                                ar.y + (ar.h - blbl.get_height()) // 2))
            bx += btn.rect.w + 2
            if bx + btn.rect.w > self.rect.right - Theme.PANEL_PADDING:
                bx = px
                y += Theme.BUTTON_HEIGHT + 2

        y += Theme.BUTTON_HEIGHT + 8

        # ---- VALUES (IntGrid palette) ----
        active_ld = state.active_layer_def
        if active_ld and active_ld.layer_type == LayerType.INTGRID:
            hdr = font.render("VALUES", True, Theme.TEXT_ACCENT)
            surface.blit(hdr, (px, y))
            y += self.SECTION_HEADER_H
            for swatch, lbl in self._intgrid_swatches:
                sx = px
                swatch_rect = pygame.Rect(sx, y, 18, 18)
                pygame.draw.rect(surface, swatch.color, swatch_rect, border_radius=2)
                if swatch.selected:
                    pygame.draw.rect(surface, Theme.BORDER_FOCUS, swatch_rect, 2, border_radius=2)
                else:
                    pygame.draw.rect(surface, Theme.BORDER, swatch_rect, 1, border_radius=2)
                vlbl = font_small.render(lbl.text, True, Theme.TEXT)
                surface.blit(vlbl, (sx + 24, y + 1))
                y += self.SWATCH_ROW_H

        surface.set_clip(clip)

    @staticmethod
    def _draw_mini_btn(surface: pygame.Surface, font: pygame.font.Font,
                       rect: pygame.Rect, text: str, color: tuple) -> None:
        pygame.draw.rect(surface, Theme.BG_BUTTON, rect, border_radius=2)
        pygame.draw.rect(surface, Theme.BORDER, rect, 1, border_radius=2)
        lbl = font.render(text, True, color)
        surface.blit(lbl, (rect.x + (rect.w - lbl.get_width()) // 2,
                           rect.y + (rect.h - lbl.get_height()) // 2))


# ---------------------------------------------------------------------------
# Right dock: property inspector + tile picker + entity list
# ---------------------------------------------------------------------------

class RightDock:
    """Right panel: properties, tile picker, entity definitions."""

    def __init__(self, screen_w: int, screen_h: int):
        top = Theme.TOP_BAR_HEIGHT
        h = screen_h - top - Theme.BOTTOM_BAR_HEIGHT
        x = screen_w - Theme.RIGHT_PANEL_WIDTH
        self.rect = pygame.Rect(x, top, Theme.RIGHT_PANEL_WIDTH, h)
        self.visible = True
        self._tile_scroll_y: int = 0
        self._entity_items: list[ListItem] = []
        self._on_select_tile: Callable | None = None
        self._on_select_entity_def: Callable | None = None

        # Tile grid layout cache (set during draw, used by click handling)
        self._tile_grid_ox: int = 0
        self._tile_grid_oy: int = 0
        self._tile_display_size: int = 0
        self._tile_grid_cols: int = 0
        self._tile_grid_rows: int = 0

        # Drag selection state for stamp
        self._drag_selecting: bool = False
        self._drag_start_col: int = 0
        self._drag_start_row: int = 0
        self._drag_end_col: int = 0
        self._drag_end_row: int = 0

    def setup(self, callbacks: dict[str, Callable]) -> None:
        self._on_select_tile = callbacks.get("select_tile")
        self._on_select_entity_def = callbacks.get("select_entity_def")

    def _pixel_to_tile(self, mx: int, my: int) -> tuple[int, int] | None:
        """Convert screen pixel to tile grid col, row. Returns None if outside grid."""
        if self._tile_display_size == 0 or self._tile_grid_cols == 0:
            return None
        rel_x = mx - self._tile_grid_ox
        rel_y = my - self._tile_grid_oy
        if rel_x < 0 or rel_y < 0:
            return None
        col = rel_x // self._tile_display_size
        row = rel_y // self._tile_display_size
        if col >= self._tile_grid_cols or row >= self._tile_grid_rows:
            return None
        return int(col), int(row)

    def handle_event(self, event: pygame.event.Event, mx: int, my: int,
                     state: EditorState | None = None) -> bool:
        if not self.visible:
            return False
        if not self.rect.collidepoint(mx, my):
            # Finish drag if mouse leaves panel
            if self._drag_selecting and event.type == pygame.MOUSEBUTTONUP:
                self._finish_drag_select(state)
            return False
        if event.type == pygame.MOUSEWHEEL:
            self._tile_scroll_y = max(0, self._tile_scroll_y - event.y * Theme.SCROLL_SPEED)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event, mx, my, state)
        if event.type == pygame.MOUSEMOTION and self._drag_selecting:
            self._handle_drag_motion(mx, my)
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._drag_selecting:
            self._finish_drag_select(state)
            return True
        return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)

    def _handle_click(self, event: pygame.event.Event, mx: int, my: int,
                      state: EditorState | None) -> bool:
        if state is None:
            return True
        ld = state.active_layer_def
        if ld is None:
            return True

        if ld.layer_type == LayerType.TILES:
            pos = self._pixel_to_tile(mx, my)
            if pos is None:
                return True
            col, row = pos
            mods = pygame.key.get_mods()

            # Shift+click: toggle tile in random pool
            if mods & pygame.KMOD_SHIFT:
                tid = row * self._tile_grid_cols + col
                if tid in state.random_tiles:
                    state.random_tiles.remove(tid)
                    state.set_notification(f"Removed tile #{tid} from random pool ({len(state.random_tiles)} tiles)")
                else:
                    state.random_tiles.append(tid)
                    state.set_notification(f"Added tile #{tid} to random pool ({len(state.random_tiles)} tiles)")
                return True

            # Normal click: start drag selection (for stamp) or single select
            self._drag_selecting = True
            self._drag_start_col = col
            self._drag_start_row = row
            self._drag_end_col = col
            self._drag_end_row = row
            return True

        elif ld.layer_type == LayerType.ENTITY:
            # Entity selection handled by main.py _handle_right_dock_click
            return True

        return True

    def _handle_drag_motion(self, mx: int, my: int) -> None:
        pos = self._pixel_to_tile(mx, my)
        if pos is not None:
            self._drag_end_col, self._drag_end_row = pos

    def _finish_drag_select(self, state: EditorState | None) -> None:
        if not self._drag_selecting:
            return
        self._drag_selecting = False
        if state is None:
            return

        c1 = min(self._drag_start_col, self._drag_end_col)
        c2 = max(self._drag_start_col, self._drag_end_col)
        r1 = min(self._drag_start_row, self._drag_end_row)
        r2 = max(self._drag_start_row, self._drag_end_row)
        cols = self._tile_grid_cols

        if c1 == c2 and r1 == r2:
            # Single tile click: select tile and clear stamp
            tid = r1 * cols + c1
            state.selected_tile_id = tid
            state.tile_stamp = None
            state.set_notification(f"Selected tile #{tid}")
        else:
            # Multi-tile selection: build stamp
            stamp: list[list[int]] = []
            for row in range(r1, r2 + 1):
                stamp_row: list[int] = []
                for col in range(c1, c2 + 1):
                    stamp_row.append(row * cols + col)
                stamp.append(stamp_row)
            state.tile_stamp = stamp
            w = c2 - c1 + 1
            h = r2 - r1 + 1
            state.set_notification(f"Stamp selected: {w}x{h} tiles")

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             font_small: pygame.font.Font, state: EditorState,
             tileset_manager: object | None = None) -> None:
        if not self.visible:
            return
        pygame.draw.rect(surface, Theme.BG_PANEL, self.rect)
        pygame.draw.line(surface, Theme.BORDER, (self.rect.x, self.rect.y),
                         (self.rect.x, self.rect.bottom))

        clip = surface.get_clip()
        surface.set_clip(self.rect)

        y = self.rect.y + 4
        active_ld = state.active_layer_def
        level = state.active_level

        if active_ld and active_ld.layer_type == LayerType.TILES:
            self._draw_tile_picker(surface, font, font_small, state, tileset_manager, y)
        elif active_ld and active_ld.layer_type == LayerType.ENTITY:
            self._draw_entity_list(surface, font, font_small, state, y)
        elif active_ld and active_ld.layer_type == LayerType.INTGRID:
            self._draw_intgrid_info(surface, font, font_small, state, y)

        # Properties section at bottom
        if state.selected_entity_instance:
            self._draw_entity_properties(surface, font, font_small, state)

        surface.set_clip(clip)

    def _draw_tile_picker(self, surface: pygame.Surface, font: pygame.font.Font,
                          font_small: pygame.font.Font, state: EditorState,
                          tileset_manager: object | None, start_y: int) -> None:
        hdr = font.render("TILE PICKER", True, Theme.TEXT_ACCENT)
        surface.blit(hdr, (self.rect.x + Theme.PANEL_PADDING, start_y))
        y = start_y + 22

        ld = state.active_layer_def
        if ld is None or ld.tileset_uid is None:
            info = font_small.render("No tileset assigned", True, Theme.TEXT_DIM)
            surface.blit(info, (self.rect.x + Theme.PANEL_PADDING, y))
            return

        if tileset_manager is None:
            return

        from birdlevel.assets.tileset_loader import TilesetManager
        if not isinstance(tileset_manager, TilesetManager):
            return

        ts_uid = ld.tileset_uid
        cols, rows = tileset_manager.get_dimensions(ts_uid)
        if cols == 0:
            info = font_small.render("Tileset not loaded", True, Theme.TEXT_WARNING)
            surface.blit(info, (self.rect.x + Theme.PANEL_PADDING, y))
            return

        tile_display_size = max(8, min(32, (self.rect.w - Theme.PANEL_PADDING * 2) // cols))

        # Status text
        info_parts = [f"Sel: #{state.selected_tile_id}"]
        if state.tile_stamp:
            sh = len(state.tile_stamp)
            sw = len(state.tile_stamp[0]) if sh > 0 else 0
            info_parts.append(f"Stamp: {sw}x{sh}")
        if state.random_tiles:
            info_parts.append(f"Rnd: {len(state.random_tiles)}")
        sel_lbl = font_small.render("  |  ".join(info_parts), True, Theme.TEXT)
        surface.blit(sel_lbl, (self.rect.x + Theme.PANEL_PADDING, y))
        y += 18

        # Hint line
        hint = font_small.render("Drag=stamp  Shift+click=random", True, Theme.TEXT_DIM)
        surface.blit(hint, (self.rect.x + Theme.PANEL_PADDING, y))
        y += 14

        # Cache layout for click handling
        ox = self.rect.x + Theme.PANEL_PADDING
        oy = y - self._tile_scroll_y
        self._tile_grid_ox = ox
        self._tile_grid_oy = oy
        self._tile_display_size = tile_display_size
        self._tile_grid_cols = cols
        self._tile_grid_rows = rows

        # Stamp selection bounds (for highlight)
        stamp_c1 = stamp_c2 = stamp_r1 = stamp_r2 = -1
        if state.tile_stamp and len(state.tile_stamp) > 0:
            # Reverse-engineer selection bounds from stamp contents
            first_tid = state.tile_stamp[0][0]
            stamp_r1 = first_tid // cols
            stamp_c1 = first_tid % cols
            stamp_r2 = stamp_r1 + len(state.tile_stamp) - 1
            stamp_c2 = stamp_c1 + len(state.tile_stamp[0]) - 1

        # Drag selection bounds (override stamp highlight during drag)
        if self._drag_selecting:
            stamp_c1 = min(self._drag_start_col, self._drag_end_col)
            stamp_c2 = max(self._drag_start_col, self._drag_end_col)
            stamp_r1 = min(self._drag_start_row, self._drag_end_row)
            stamp_r2 = max(self._drag_start_row, self._drag_end_row)

        # Draw tile grid
        for row in range(rows):
            for col in range(cols):
                tid = row * cols + col
                tx = ox + col * tile_display_size
                ty = oy + row * tile_display_size
                if ty + tile_display_size < self.rect.y or ty > self.rect.bottom:
                    continue
                tile_surf = tileset_manager.get_tile(ts_uid, tid)
                if tile_surf:
                    scaled = pygame.transform.scale(tile_surf, (tile_display_size, tile_display_size))
                    surface.blit(scaled, (tx, ty))
                else:
                    pygame.draw.rect(surface, Theme.BG_INPUT,
                                     (tx, ty, tile_display_size, tile_display_size))

                # Highlight: random pool tiles (green border)
                if tid in state.random_tiles:
                    pygame.draw.rect(surface, Theme.TEXT_SUCCESS,
                                     (tx, ty, tile_display_size, tile_display_size), 2)

                # Highlight: selected single tile (accent border)
                if tid == state.selected_tile_id and stamp_c1 == -1:
                    pygame.draw.rect(surface, Theme.ACCENT,
                                     (tx, ty, tile_display_size, tile_display_size), 2)

        # Draw stamp/drag selection rectangle overlay
        if stamp_c1 >= 0:
            sx = ox + stamp_c1 * tile_display_size
            sy = oy + stamp_r1 * tile_display_size
            sw = (stamp_c2 - stamp_c1 + 1) * tile_display_size
            sh = (stamp_r2 - stamp_r1 + 1) * tile_display_size
            sel_overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
            sel_overlay.fill((130, 170, 255, 40))
            surface.blit(sel_overlay, (sx, sy))
            pygame.draw.rect(surface, Theme.ACCENT,
                             (sx, sy, sw, sh), 2)

    def _draw_entity_list(self, surface: pygame.Surface, font: pygame.font.Font,
                          font_small: pygame.font.Font, state: EditorState,
                          start_y: int) -> None:
        hdr = font.render("ENTITIES", True, Theme.TEXT_ACCENT)
        surface.blit(hdr, (self.rect.x + Theme.PANEL_PADDING, start_y))
        y = start_y + 22

        for edef in state.project.definitions.entities:
            item_rect = pygame.Rect(self.rect.x + Theme.PANEL_PADDING, y,
                                    self.rect.w - Theme.PANEL_PADDING * 2, Theme.ITEM_HEIGHT)
            selected = (state.selected_entity_def_uid == edef.uid)
            if selected:
                pygame.draw.rect(surface, Theme.BG_SELECTED, item_rect)

            # Color indicator
            ind = pygame.Rect(item_rect.x + 2, item_rect.y + 5, 14, 14)
            pygame.draw.rect(surface, edef.color, ind, border_radius=2)

            lbl = font_small.render(edef.name, True, Theme.TEXT_BRIGHT if selected else Theme.TEXT)
            surface.blit(lbl, (item_rect.x + 20, item_rect.y + 4))
            y += Theme.ITEM_HEIGHT

    def _draw_intgrid_info(self, surface: pygame.Surface, font: pygame.font.Font,
                           font_small: pygame.font.Font, state: EditorState,
                           start_y: int) -> None:
        hdr = font.render("INTGRID INFO", True, Theme.TEXT_ACCENT)
        surface.blit(hdr, (self.rect.x + Theme.PANEL_PADDING, start_y))
        y = start_y + 22

        info_lines = [
            f"Selected value: {state.intgrid_value}",
            f"Grid cursor: ({state.hover_gx}, {state.hover_gy})",
        ]
        level = state.active_level
        ld = state.active_layer_def
        if level and ld:
            info_lines.append(f"Level: {level.width_cells}x{level.height_cells}")
            info_lines.append(f"Grid size: {ld.grid_size}px")

        for line in info_lines:
            lbl = font_small.render(line, True, Theme.TEXT)
            surface.blit(lbl, (self.rect.x + Theme.PANEL_PADDING, y))
            y += 18

    def _draw_entity_properties(self, surface: pygame.Surface, font: pygame.font.Font,
                                font_small: pygame.font.Font, state: EditorState) -> None:
        ent = state.selected_entity_instance
        if ent is None:
            return

        edef = state.project.definitions.entity_by_uid(ent.def_uid)
        y = self.rect.y + self.rect.h // 2

        hdr = font.render("PROPERTIES", True, Theme.TEXT_ACCENT)
        surface.blit(hdr, (self.rect.x + Theme.PANEL_PADDING, y))
        y += 22

        props = [
            f"Entity: {edef.name if edef else '?'}",
            f"Position: ({ent.x}, {ent.y})",
            f"Size: {ent.width}x{ent.height}",
        ]
        for p in props:
            lbl = font_small.render(p, True, Theme.TEXT)
            surface.blit(lbl, (self.rect.x + Theme.PANEL_PADDING, y))
            y += 18

        # Fields
        if ent.fields:
            for key, val in ent.fields.items():
                field_text = f"{key}: {val}"
                flbl = font_small.render(field_text, True, Theme.TEXT_DIM)
                surface.blit(flbl, (self.rect.x + Theme.PANEL_PADDING, y))
                y += 18
