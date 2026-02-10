"""Main application loop for BirdLevel editor."""
from __future__ import annotations

import os
import sys
import time

import pygame

from birdlevel.app.input_handler import InputHandler
from birdlevel.app.ui.panels import BottomBar, LeftDock, RightDock, TopBar
from birdlevel.app.ui.theme import Theme
from birdlevel.app.ui.widgets import UIEvent
from birdlevel.assets.tileset_loader import TilesetManager
from birdlevel.editor.commands import CommandStack
from birdlevel.editor.editor_state import EditorState
from birdlevel.editor.tools.base import ToolCategory, ToolManager, ToolType
from birdlevel.editor.tools.entity_tools import EntityPlace, EntitySelect
from birdlevel.editor.tools.intgrid_tools import (
    IntGridBrush,
    IntGridEraser,
    IntGridFloodFill,
    IntGridRectFill,
)
from birdlevel.editor.tools.tile_tools import (
    TileBrush,
    TileEyedropper,
    TileFloodFill,
    TileRandom,
    TileRect,
    TileStamp,
)
from birdlevel.export.json_export import export_full_json
from birdlevel.export.simple_export import export_simple
from birdlevel.project.models import (
    EntityDef,
    FieldDef,
    FieldType,
    IntGridValueDef,
    LayerDef,
    LayerType,
    Level,
    Project,
    TilesetDef,
    World,
)
from birdlevel.project.serialization import load_project, save_project
from birdlevel.render.camera import Camera
from birdlevel.render.grid import draw_grid, draw_level_border
from birdlevel.render.layer_renderer import LayerRenderer
from birdlevel.rules.auto_layer import RuleSolver
from birdlevel.util.file_dialog import ask_yes_no, open_file_dialog, save_file_dialog
from birdlevel.util.paths import create_backup, find_latest_backup, prune_backups


SCREEN_W = 1920
SCREEN_H = 1080
FPS_TARGET = 60
APP_TITLE = "BirdLevel - Game Bird Level Editor"


class App:
    """Main editor application."""

    def __init__(self, project_path: str | None = None):
        self.project_path = project_path
        self.project: Project | None = None
        self.state: EditorState | None = None
        self.running = False

        # Subsystems
        self.tool_manager = ToolManager()
        self.input_handler = InputHandler()
        self.tileset_manager = TilesetManager()
        self.layer_renderer = LayerRenderer(tileset_manager=self.tileset_manager)
        self.rule_solver: RuleSolver | None = None

        # UI
        self.top_bar: TopBar | None = None
        self.bottom_bar: BottomBar | None = None
        self.left_dock: LeftDock | None = None
        self.right_dock: RightDock | None = None

        # Pygame
        self.screen: pygame.Surface | None = None
        self.clock: pygame.time.Clock | None = None
        self.font: pygame.font.Font | None = None
        self.font_small: pygame.font.Font | None = None

        # Dialogs
        self._dialog_active = False
        self._dialog_type: str = ""
        self._dialog_fields: dict = {}
        self._dialog_callback = None
        self._dialog_text_inputs: dict = {}
        self._cursor_blink_timer: float = 0.0
        self._cursor_visible: bool = True

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def init(self) -> None:
        pygame.init()
        pygame.display.set_caption(APP_TITLE)

        # Try fullscreen at 1920x1080, fall back to windowed
        try:
            info = pygame.display.Info()
            if info.current_w >= SCREEN_W and info.current_h >= SCREEN_H:
                self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
            else:
                self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.RESIZABLE)
        except pygame.error:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))

        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("dejavusans,arial,helvetica", Theme.FONT_SIZE)
        self.font_small = pygame.font.SysFont("dejavusans,arial,helvetica", Theme.FONT_SIZE_SMALL)

        # Crash recovery check
        if self.project_path and os.path.exists(self.project_path):
            self._check_crash_recovery(self.project_path)
            self._load_project(self.project_path)
        else:
            self._new_project()

        # Setup subsystems
        self._setup_tools()
        self._setup_ui()
        self._setup_input()
        self._update_viewport()

        self.rule_solver = RuleSolver(self.project.definitions)

        # Center camera on level
        level = self.state.active_level
        if level:
            gs = self.project.grid_size
            cx = level.pixel_width(gs) / 2
            cy = level.pixel_height(gs) / 2
            self.state.camera.center_on(cx, cy)

    def _new_project(self) -> None:
        self.project = Project(name="NewProject")
        self.project.create_default()
        # Add a sample entity definition
        player_entity = EntityDef(
            name="Player",
            width=16,
            height=16,
            color=(80, 220, 120),
            singleton=True,
            grid_locked=True,
            fields=[
                FieldDef(name="health", field_type=FieldType.INT, default_value=100, min_value=0, max_value=999),
                FieldDef(name="name", field_type=FieldType.STRING, default_value="Player"),
            ],
        )
        enemy_entity = EntityDef(
            name="Enemy",
            width=16,
            height=16,
            color=(220, 80, 80),
            singleton=False,
            grid_locked=True,
            fields=[
                FieldDef(name="type", field_type=FieldType.STRING, default_value="basic"),
                FieldDef(name="patrol", field_type=FieldType.BOOL, default_value=True),
            ],
        )
        spawn_entity = EntityDef(
            name="Spawn",
            width=16,
            height=16,
            color=(220, 200, 80),
            singleton=True,
            grid_locked=True,
        )
        self.project.definitions.entities = [player_entity, enemy_entity, spawn_entity]

        # Generate a sample tileset so tile painting works out of the box
        try:
            from birdlevel.assets.generate_sample import generate_sample_tileset
            sample_dir = os.path.join(os.getcwd(), "assets")
            os.makedirs(sample_dir, exist_ok=True)
            sample_path = os.path.join(sample_dir, "sample_tileset.png")
            generate_sample_tileset(sample_path, tile_size=16, cols=8, rows=8)
            tileset_def = TilesetDef(
                name="Sample Tileset",
                image_path=sample_path,
                tile_size=16,
                columns=8,
                rows=8,
            )
            self.project.definitions.tilesets.append(tileset_def)
            # Assign tileset to the Tiles layer
            for ld in self.project.definitions.layers:
                if ld.layer_type == LayerType.TILES:
                    ld.tileset_uid = tileset_def.uid
                    break
            self.tileset_manager.set_base_path(os.getcwd())
            self.tileset_manager.load_tileset(tileset_def)
        except Exception as e:
            print(f"Warning: Could not generate sample tileset: {e}")

        self.state = EditorState(self.project)

    def _check_crash_recovery(self, path: str) -> None:
        """Check for unsaved backup newer than the project file and offer restore."""
        try:
            backup = find_latest_backup(path)
            if backup is None:
                return
            proj_mtime = os.path.getmtime(path)
            back_mtime = os.path.getmtime(backup)
            if back_mtime > proj_mtime:
                if ask_yes_no(
                    "Crash Recovery",
                    f"A backup newer than the saved project was found.\n\n"
                    f"Backup: {os.path.basename(backup)}\n"
                    f"Restore from backup?",
                ):
                    self.project_path = backup
        except Exception as e:
            print(f"Crash recovery check failed: {e}")

    def _load_project(self, path: str) -> None:
        try:
            self.project = load_project(path)
            self.state = EditorState(self.project)
            self.state.set_notification(f"Loaded: {path}")
            # Load tilesets
            if self.project.file_path:
                self.tileset_manager.set_base_path(os.path.dirname(self.project.file_path))
            failed = self.tileset_manager.load_all(self.project.definitions)
            if failed:
                self.state.set_notification(f"Failed tilesets: {', '.join(failed)}", 5.0)
        except Exception as e:
            print(f"Error loading project: {e}")
            self._new_project()
            self.state.set_notification(f"Load failed: {e}", 5.0)

    def _setup_tools(self) -> None:
        self.tool_manager.register(IntGridBrush())
        self.tool_manager.register(IntGridEraser())
        self.tool_manager.register(IntGridRectFill())
        self.tool_manager.register(IntGridFloodFill())
        self.tool_manager.register(TileBrush())
        self.tool_manager.register(TileRect())
        self.tool_manager.register(TileStamp())
        self.tool_manager.register(TileRandom())
        self.tool_manager.register(TileFloodFill())
        self.tool_manager.register(TileEyedropper())
        self.tool_manager.register(EntitySelect())
        self.tool_manager.register(EntityPlace())
        self.tool_manager.set_active(ToolType.INTGRID_BRUSH)

    def _setup_ui(self) -> None:
        self.top_bar = TopBar(SCREEN_W)
        self.top_bar.setup({
            "save": self._on_save,
            "open": self._on_open,
            "save_as": self._on_save_as,
            "undo": self._on_undo,
            "redo": self._on_redo,
            "export": self._on_export,
            "new_level": self._on_new_level,
            "add_layer": self._on_add_layer,
            "resize_level": self._show_resize_level_dialog,
            "import_tileset": self._show_import_tileset_dialog,
        })
        self.bottom_bar = BottomBar(SCREEN_W, SCREEN_H)
        self.left_dock = LeftDock(SCREEN_H)
        self.left_dock.setup({
            "select_level": self._on_select_level,
            "select_layer": self._on_select_layer,
            "select_tool": self._on_select_tool,
            "select_intgrid_value": self._on_select_intgrid_value,
            "toggle_layer_visible": self._on_toggle_layer_visible,
            "toggle_layer_locked": self._on_toggle_layer_locked,
            "move_layer": self._on_move_layer,
            "change_layer_opacity": self._on_change_layer_opacity,
            "delete_layer": self._on_delete_layer,
        })
        self.right_dock = RightDock(SCREEN_W, SCREEN_H)
        self.right_dock.setup({
            "select_tile": self._on_select_tile,
            "select_entity_def": self._on_select_entity_def,
        })

    def _setup_input(self) -> None:
        self.input_handler.set_callbacks({
            "save": self._on_save,
            "open": self._on_open,
            "save_as": self._on_save_as,
            "export": self._on_export,
        })

    def _update_viewport(self) -> None:
        """Update the camera viewport to exclude UI panels."""
        left = Theme.LEFT_PANEL_WIDTH if (self.left_dock and self.left_dock.visible and not self.state.panels_collapsed) else 0
        right = Theme.RIGHT_PANEL_WIDTH if (self.right_dock and self.right_dock.visible and not self.state.panels_collapsed) else 0
        top = Theme.TOP_BAR_HEIGHT
        bottom = Theme.BOTTOM_BAR_HEIGHT
        vw = SCREEN_W - left - right
        vh = SCREEN_H - top - bottom
        self.state.camera.set_viewport(left, top, vw, vh)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        if self.project is None:
            return
        # If no file path yet, prompt with Save As
        if not self.project.file_path:
            self._on_save_as()
            return
        try:
            create_backup(self.project.file_path)
            prune_backups(self.project.file_path)
            path = save_project(self.project)
            self.state.command_stack.mark_clean()
            self.state.needs_save = False
            self.state.autosave_timer = 0.0
            self.state.set_notification(f"Saved: {os.path.basename(path)}")
        except Exception as e:
            self.state.set_notification(f"Save failed: {e}", 5.0)

    def _on_open(self) -> None:
        """Open a project file via file dialog."""
        initial = os.path.dirname(self.project.file_path) if self.project and self.project.file_path else None
        path = open_file_dialog(title="Open BirdLevel Project", initial_dir=initial)
        if path:
            self._load_project(path)
            # Re-setup after loading a new project
            self.rule_solver = RuleSolver(self.project.definitions)
            level = self.state.active_level
            if level:
                gs = self.project.grid_size
                self.state.camera.center_on(level.pixel_width(gs) / 2, level.pixel_height(gs) / 2)
            self.state.command_stack.clear()

    def _on_save_as(self) -> None:
        """Save project to a new file via file dialog."""
        if self.project is None:
            return
        initial = os.path.dirname(self.project.file_path) if self.project.file_path else None
        default = f"{self.project.name}.birdlevel"
        path = save_file_dialog(title="Save BirdLevel Project As", initial_dir=initial, default_name=default)
        if path:
            try:
                self.project.file_path = path
                save_project(self.project, path)
                self.state.command_stack.mark_clean()
                self.state.needs_save = False
                self.state.autosave_timer = 0.0
                self.state.set_notification(f"Saved as: {os.path.basename(path)}")
            except Exception as e:
                self.state.set_notification(f"Save As failed: {e}", 5.0)

    def _on_undo(self) -> None:
        if self.state.command_stack.undo():
            self.state.set_notification("Undo")

    def _on_redo(self) -> None:
        if self.state.command_stack.redo():
            self.state.set_notification("Redo")

    def _on_export(self) -> None:
        if self.project is None:
            return
        try:
            base = os.path.dirname(self.project.file_path) if self.project.file_path else os.getcwd()
            export_dir = os.path.join(base, "export")
            json_path = os.path.join(export_dir, f"{self.project.name}.json")
            export_full_json(self.project, json_path)
            simple_files = export_simple(self.project, os.path.join(export_dir, "simple"),
                                         self.tileset_manager)
            total = 1 + len(simple_files)
            self.state.set_notification(f"Exported {total} files to {export_dir}")
        except Exception as e:
            self.state.set_notification(f"Export failed: {e}", 5.0)

    def _on_new_level(self) -> None:
        world = self.state.active_world
        if world is None:
            return
        idx = len(world.levels)
        level = Level(name=f"Level_{idx}")
        level.ensure_layer_instances(self.project.definitions.layers)
        world.levels.append(level)
        self.state.set_active_level(idx)
        self.state.needs_save = True
        self.state.set_notification(f"Created {level.name}")

    def _on_add_layer(self) -> None:
        self._show_add_layer_dialog()

    def _on_select_level(self, event: UIEvent) -> None:
        idx = event.data
        if isinstance(idx, int):
            self.state.set_active_level(idx)

    def _on_select_layer(self, event: UIEvent) -> None:
        idx = event.data
        if isinstance(idx, int):
            self.state.set_active_layer(idx)
            # Auto-switch tool category
            ld = self.state.active_layer_def
            if ld:
                cat_map = {
                    LayerType.INTGRID: ToolCategory.INTGRID,
                    LayerType.TILES: ToolCategory.TILES,
                    LayerType.ENTITY: ToolCategory.ENTITIES,
                    LayerType.AUTO_LAYER: ToolCategory.TILES,
                }
                cat = cat_map.get(ld.layer_type)
                if cat:
                    self.tool_manager.set_category(cat)

    def _on_select_tool(self, event: UIEvent) -> None:
        tt = event.data
        if isinstance(tt, ToolType):
            self.tool_manager.set_active(tt)

    def _on_select_intgrid_value(self, event: UIEvent) -> None:
        val = event.data
        if isinstance(val, int):
            self.state.intgrid_value = val

    def _on_toggle_layer_visible(self, event: UIEvent) -> None:
        idx = event.data
        if not isinstance(idx, int):
            return
        level = self.state.active_level
        defs = self.project.definitions.layers
        if level and 0 <= idx < len(defs):
            li = level.get_layer_instance(defs[idx].uid)
            if li:
                li.visible = not li.visible
                tag = "visible" if li.visible else "hidden"
                self.state.set_notification(f"Layer {defs[idx].name}: {tag}")

    def _on_toggle_layer_locked(self, event: UIEvent) -> None:
        idx = event.data
        if not isinstance(idx, int):
            return
        level = self.state.active_level
        defs = self.project.definitions.layers
        if level and 0 <= idx < len(defs):
            li = level.get_layer_instance(defs[idx].uid)
            if li:
                li.locked = not li.locked
                tag = "locked" if li.locked else "unlocked"
                self.state.set_notification(f"Layer {defs[idx].name}: {tag}")

    def _on_move_layer(self, event: UIEvent) -> None:
        direction, idx = event.data
        defs = self.project.definitions.layers
        if not (0 <= idx < len(defs)):
            return
        if direction == "up" and idx > 0:
            defs[idx], defs[idx - 1] = defs[idx - 1], defs[idx]
            if self.state.active_layer_idx == idx:
                self.state.set_active_layer(idx - 1)
            elif self.state.active_layer_idx == idx - 1:
                self.state.set_active_layer(idx)
            self.state.needs_save = True
            self.state.set_notification(f"Moved {defs[idx - 1].name} up")
        elif direction == "down" and idx < len(defs) - 1:
            defs[idx], defs[idx + 1] = defs[idx + 1], defs[idx]
            if self.state.active_layer_idx == idx:
                self.state.set_active_layer(idx + 1)
            elif self.state.active_layer_idx == idx + 1:
                self.state.set_active_layer(idx)
            self.state.needs_save = True
            self.state.set_notification(f"Moved {defs[idx + 1].name} down")

    def _on_change_layer_opacity(self, event: UIEvent) -> None:
        delta = event.data
        if not isinstance(delta, (int, float)):
            return
        level = self.state.active_level
        ld = self.state.active_layer_def
        if level is None or ld is None:
            return
        li = level.get_layer_instance(ld.uid)
        if li is None:
            return
        li.opacity = max(0.0, min(1.0, li.opacity + delta))
        pct = int(li.opacity * 100)
        self.state.set_notification(f"Layer {ld.name} opacity: {pct}%")

    def _on_delete_layer(self, event: UIEvent) -> None:
        idx = event.data
        if not isinstance(idx, int):
            return
        defs = self.project.definitions.layers
        if not (0 <= idx < len(defs)):
            return
        if len(defs) <= 1:
            self.state.set_notification("Cannot delete the last layer")
            return
        name = defs[idx].name
        uid = defs[idx].uid
        defs.pop(idx)
        # Remove layer instances from all levels
        for world in self.project.worlds:
            for level in world.levels:
                level.layers = [li for li in level.layers if li.layer_def_uid != uid]
        # Fix active layer index
        if self.state.active_layer_idx >= len(defs):
            self.state.set_active_layer(len(defs) - 1)
        elif self.state.active_layer_idx == idx:
            self.state.set_active_layer(max(0, idx - 1))
        self.state.needs_save = True
        self.state.set_notification(f"Deleted layer: {name}")

    def _on_select_tile(self, event: UIEvent) -> None:
        tid = event.data
        if isinstance(tid, int):
            self.state.selected_tile_id = tid

    def _on_select_entity_def(self, event: UIEvent) -> None:
        uid = event.data
        if isinstance(uid, str):
            self.state.selected_entity_def_uid = uid
            self.tool_manager.set_active(ToolType.ENTITY_PLACE)

    # ------------------------------------------------------------------
    # Dialog system
    # ------------------------------------------------------------------

    def _draw_text_field(self, label: str, key: str, inp_rect: pygame.Rect,
                         active_field: str, label_x: int, label_y: int) -> None:
        """Draw a labeled text input with blinking cursor."""
        lbl = self.font_small.render(label, True, Theme.TEXT)
        self.screen.blit(lbl, (label_x, label_y))
        is_active = (active_field == key)
        pygame.draw.rect(self.screen, Theme.BG_INPUT, inp_rect, border_radius=3)
        border = Theme.BORDER_FOCUS if is_active else Theme.BORDER
        pygame.draw.rect(self.screen, border, inp_rect, 1, border_radius=3)
        val_text = self._dialog_fields.get(key, "")
        val = self.font_small.render(val_text, True, Theme.TEXT)
        self.screen.blit(val, (inp_rect.x + 4, inp_rect.y + 4))
        # Blinking cursor
        if is_active and self._cursor_visible:
            cursor_x = inp_rect.x + 4 + val.get_width() + 1
            pygame.draw.line(self.screen, Theme.TEXT_BRIGHT,
                             (cursor_x, inp_rect.y + 3),
                             (cursor_x, inp_rect.y + inp_rect.h - 3), 1)

    def _open_dialog(self, dialog_type: str, fields: dict) -> None:
        """Open a dialog with cursor blink reset."""
        self._dialog_active = True
        self._dialog_type = dialog_type
        self._dialog_fields = fields
        self._cursor_blink_timer = 0.0
        self._cursor_visible = True

    def _show_add_layer_dialog(self) -> None:
        self._dialog_active = True
        self._dialog_type = "add_layer"
        self._dialog_fields = {
            "name": "NewLayer",
            "type_idx": 0,
        }
        self._dialog_text_inputs = {}
        self._cursor_blink_timer = 0.0
        self._cursor_visible = True

    def _handle_dialog_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        if not self._dialog_active:
            return False

        if self._dialog_type == "add_layer":
            return self._handle_add_layer_dialog_event(event, mx, my)
        elif self._dialog_type == "resize_level":
            return self._handle_resize_level_dialog_event(event, mx, my)
        elif self._dialog_type == "import_tileset":
            return self._handle_import_tileset_dialog_event(event, mx, my)
        return False

    def _handle_add_layer_dialog_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        dialog_rect = pygame.Rect(SCREEN_W // 2 - 200, SCREEN_H // 2 - 120, 400, 240)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._dialog_active = False
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self._dialog_fields["name"] = self._dialog_fields["name"][:-1]
                return True
            elif event.key == pygame.K_RETURN:
                self._create_layer_from_dialog()
                self._dialog_active = False
                return True
            elif event.key == pygame.K_TAB:
                # Cycle layer type
                self._dialog_fields["type_idx"] = (self._dialog_fields["type_idx"] + 1) % 4
                return True
            elif event.unicode and event.unicode.isprintable():
                self._dialog_fields["name"] += event.unicode
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Type selector buttons
            types = ["intgrid", "tiles", "entity", "auto_layer"]
            btn_y = dialog_rect.y + 80
            for i, t in enumerate(types):
                btn_rect = pygame.Rect(dialog_rect.x + 20 + i * 90, btn_y, 85, 28)
                if btn_rect.collidepoint(mx, my):
                    self._dialog_fields["type_idx"] = i
                    return True

            # OK / Cancel buttons
            ok_rect = pygame.Rect(dialog_rect.x + 100, dialog_rect.y + 190, 80, 30)
            cancel_rect = pygame.Rect(dialog_rect.x + 220, dialog_rect.y + 190, 80, 30)
            if ok_rect.collidepoint(mx, my):
                self._create_layer_from_dialog()
                self._dialog_active = False
                return True
            if cancel_rect.collidepoint(mx, my):
                self._dialog_active = False
                return True

        return dialog_rect.collidepoint(mx, my)

    def _create_layer_from_dialog(self) -> None:
        types = [LayerType.INTGRID, LayerType.TILES, LayerType.ENTITY, LayerType.AUTO_LAYER]
        lt = types[self._dialog_fields.get("type_idx", 0)]
        name = self._dialog_fields.get("name", "NewLayer") or "NewLayer"

        ld = LayerDef(
            name=name,
            layer_type=lt,
            grid_size=self.project.grid_size,
        )
        if lt == LayerType.INTGRID:
            ld.intgrid_values = [
                IntGridValueDef(value=1, name="Value1", color=(80, 130, 220)),
                IntGridValueDef(value=2, name="Value2", color=(100, 180, 80)),
            ]

        self.project.definitions.layers.append(ld)
        # Add layer instance to all existing levels
        for world in self.project.worlds:
            for level in world.levels:
                level.ensure_layer_instances(self.project.definitions.layers)

        self.state.set_active_layer(len(self.project.definitions.layers) - 1)
        self.state.needs_save = True
        self.state.set_notification(f"Added layer: {name} [{lt.value}]")

    def _draw_dialog(self) -> None:
        if not self._dialog_active:
            return
        if self._dialog_type == "add_layer":
            self._draw_add_layer_dialog()
        elif self._dialog_type == "resize_level":
            self._draw_resize_level_dialog()
        elif self._dialog_type == "import_tileset":
            self._draw_import_tileset_dialog()

    def _draw_add_layer_dialog(self) -> None:
        # Dim background
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        dialog_rect = pygame.Rect(SCREEN_W // 2 - 200, SCREEN_H // 2 - 120, 400, 240)
        pygame.draw.rect(self.screen, Theme.BG_PANEL, dialog_rect, border_radius=8)
        pygame.draw.rect(self.screen, Theme.BORDER_LIGHT, dialog_rect, 2, border_radius=8)

        # Title
        title = self.font.render("Add New Layer", True, Theme.TEXT_BRIGHT)
        self.screen.blit(title, (dialog_rect.x + 20, dialog_rect.y + 12))

        # Name input with blinking cursor
        name_rect = pygame.Rect(dialog_rect.x + 80, dialog_rect.y + 44, 280, 24)
        self._draw_text_field("Name:", "name", name_rect, "name",
                              dialog_rect.x + 20, dialog_rect.y + 48)

        # Type buttons
        type_label = self.font_small.render("Type:", True, Theme.TEXT)
        self.screen.blit(type_label, (dialog_rect.x + 20, dialog_rect.y + 84))
        types = ["IntGrid", "Tiles", "Entity", "AutoLayer"]
        type_colors = [Theme.LAYER_INTGRID, Theme.LAYER_TILES, Theme.LAYER_ENTITY, Theme.LAYER_AUTO]
        btn_y = dialog_rect.y + 80
        current_idx = self._dialog_fields.get("type_idx", 0)
        for i, (t, c) in enumerate(zip(types, type_colors)):
            btn_rect = pygame.Rect(dialog_rect.x + 80 + i * 75, btn_y, 70, 28)
            bg = Theme.BG_BUTTON_ACTIVE if i == current_idx else Theme.BG_BUTTON
            pygame.draw.rect(self.screen, bg, btn_rect, border_radius=3)
            if i == current_idx:
                pygame.draw.rect(self.screen, c, btn_rect, 2, border_radius=3)
            else:
                pygame.draw.rect(self.screen, Theme.BORDER, btn_rect, 1, border_radius=3)
            lbl = self.font_small.render(t, True, Theme.TEXT_BRIGHT if i == current_idx else Theme.TEXT)
            self.screen.blit(lbl, (btn_rect.x + (btn_rect.w - lbl.get_width()) // 2,
                                   btn_rect.y + (btn_rect.h - lbl.get_height()) // 2))

        # Hint
        hint = self.font_small.render("Tab to cycle type, Enter to confirm, Esc to cancel", True, Theme.TEXT_DIM)
        self.screen.blit(hint, (dialog_rect.x + 20, dialog_rect.y + 130))

        # OK / Cancel
        ok_rect = pygame.Rect(dialog_rect.x + 100, dialog_rect.y + 190, 80, 30)
        cancel_rect = pygame.Rect(dialog_rect.x + 220, dialog_rect.y + 190, 80, 30)
        for rect, label in [(ok_rect, "OK"), (cancel_rect, "Cancel")]:
            pygame.draw.rect(self.screen, Theme.BG_BUTTON, rect, border_radius=4)
            pygame.draw.rect(self.screen, Theme.BORDER_LIGHT, rect, 1, border_radius=4)
            lbl = self.font_small.render(label, True, Theme.TEXT)
            self.screen.blit(lbl, (rect.x + (rect.w - lbl.get_width()) // 2,
                                   rect.y + (rect.h - lbl.get_height()) // 2))

    # ------------------------------------------------------------------
    # Resize Level Dialog
    # ------------------------------------------------------------------

    def _show_resize_level_dialog(self) -> None:
        level = self.state.active_level
        if level is None:
            return
        self._dialog_active = True
        self._dialog_type = "resize_level"
        self._dialog_fields = {
            "width": str(level.width_cells),
            "height": str(level.height_cells),
            "active_field": "width",
        }
        self._cursor_blink_timer = 0.0
        self._cursor_visible = True

    def _handle_resize_level_dialog_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        dialog_rect = pygame.Rect(SCREEN_W // 2 - 180, SCREEN_H // 2 - 100, 360, 200)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._dialog_active = False
            return True

        if event.type == pygame.KEYDOWN:
            af = self._dialog_fields["active_field"]
            if event.key == pygame.K_BACKSPACE:
                self._dialog_fields[af] = self._dialog_fields[af][:-1]
                return True
            elif event.key == pygame.K_TAB:
                self._dialog_fields["active_field"] = "height" if af == "width" else "width"
                return True
            elif event.key == pygame.K_RETURN:
                self._apply_resize_level()
                self._dialog_active = False
                return True
            elif event.unicode and event.unicode.isdigit():
                self._dialog_fields[af] += event.unicode
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Field click detection
            w_rect = pygame.Rect(dialog_rect.x + 100, dialog_rect.y + 44, 220, 24)
            h_rect = pygame.Rect(dialog_rect.x + 100, dialog_rect.y + 78, 220, 24)
            if w_rect.collidepoint(mx, my):
                self._dialog_fields["active_field"] = "width"
                return True
            if h_rect.collidepoint(mx, my):
                self._dialog_fields["active_field"] = "height"
                return True

            ok_rect = pygame.Rect(dialog_rect.x + 80, dialog_rect.y + 155, 80, 30)
            cancel_rect = pygame.Rect(dialog_rect.x + 200, dialog_rect.y + 155, 80, 30)
            if ok_rect.collidepoint(mx, my):
                self._apply_resize_level()
                self._dialog_active = False
                return True
            if cancel_rect.collidepoint(mx, my):
                self._dialog_active = False
                return True

        return dialog_rect.collidepoint(mx, my)

    def _apply_resize_level(self) -> None:
        level = self.state.active_level
        if level is None:
            return
        try:
            new_w = max(1, int(self._dialog_fields.get("width", "1")))
            new_h = max(1, int(self._dialog_fields.get("height", "1")))
        except ValueError:
            self.state.set_notification("Invalid dimensions", 3.0)
            return

        from birdlevel.editor.commands import ResizeLevelCommand
        cmd = ResizeLevelCommand(
            level=level,
            new_cols=new_w,
            new_rows=new_h,
        )
        self.state.command_stack.execute(cmd)
        self.state.needs_save = True
        self.state.set_notification(f"Resized to {new_w}x{new_h}")

    def _draw_resize_level_dialog(self) -> None:
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        dialog_rect = pygame.Rect(SCREEN_W // 2 - 180, SCREEN_H // 2 - 100, 360, 200)
        pygame.draw.rect(self.screen, Theme.BG_PANEL, dialog_rect, border_radius=8)
        pygame.draw.rect(self.screen, Theme.BORDER_LIGHT, dialog_rect, 2, border_radius=8)

        title = self.font.render("Resize Level", True, Theme.TEXT_BRIGHT)
        self.screen.blit(title, (dialog_rect.x + 20, dialog_rect.y + 12))

        af = self._dialog_fields.get("active_field", "width")
        for i, (label, key) in enumerate([("Width:", "width"), ("Height:", "height")]):
            ly = dialog_rect.y + 44 + i * 34
            inp_rect = pygame.Rect(dialog_rect.x + 100, ly, 220, 24)
            self._draw_text_field(label, key, inp_rect, af,
                                  dialog_rect.x + 20, ly + 2)

        hint = self.font_small.render("Tab to switch fields, Enter to confirm", True, Theme.TEXT_DIM)
        self.screen.blit(hint, (dialog_rect.x + 20, dialog_rect.y + 120))

        ok_rect = pygame.Rect(dialog_rect.x + 80, dialog_rect.y + 155, 80, 30)
        cancel_rect = pygame.Rect(dialog_rect.x + 200, dialog_rect.y + 155, 80, 30)
        for rect, label in [(ok_rect, "OK"), (cancel_rect, "Cancel")]:
            pygame.draw.rect(self.screen, Theme.BG_BUTTON, rect, border_radius=4)
            pygame.draw.rect(self.screen, Theme.BORDER_LIGHT, rect, 1, border_radius=4)
            lbl = self.font_small.render(label, True, Theme.TEXT)
            self.screen.blit(lbl, (rect.x + (rect.w - lbl.get_width()) // 2,
                                   rect.y + (rect.h - lbl.get_height()) // 2))

    # ------------------------------------------------------------------
    # Import Tileset Dialog
    # ------------------------------------------------------------------

    def _show_import_tileset_dialog(self) -> None:
        from birdlevel.util.file_dialog import open_file_dialog
        path = open_file_dialog(
            title="Import Tileset Image",
            filetypes=[("PNG Images", "*.png"), ("All Images", "*.png *.jpg *.bmp"), ("All Files", "*.*")],
        )
        if not path:
            return
        self._dialog_active = True
        self._dialog_type = "import_tileset"
        self._dialog_fields = {
            "path": path,
            "name": os.path.splitext(os.path.basename(path))[0],
            "tile_size": str(self.project.grid_size),
            "active_field": "name",
        }
        self._cursor_blink_timer = 0.0
        self._cursor_visible = True

    def _handle_import_tileset_dialog_event(self, event: pygame.event.Event, mx: int, my: int) -> bool:
        dialog_rect = pygame.Rect(SCREEN_W // 2 - 200, SCREEN_H // 2 - 110, 400, 220)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._dialog_active = False
            return True

        if event.type == pygame.KEYDOWN:
            af = self._dialog_fields["active_field"]
            if event.key == pygame.K_BACKSPACE:
                self._dialog_fields[af] = self._dialog_fields[af][:-1]
                return True
            elif event.key == pygame.K_TAB:
                self._dialog_fields["active_field"] = "tile_size" if af == "name" else "name"
                return True
            elif event.key == pygame.K_RETURN:
                self._apply_import_tileset()
                self._dialog_active = False
                return True
            elif event.unicode and event.unicode.isprintable():
                if af == "tile_size" and not event.unicode.isdigit():
                    return True
                self._dialog_fields[af] += event.unicode
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            name_rect = pygame.Rect(dialog_rect.x + 100, dialog_rect.y + 50, 270, 24)
            size_rect = pygame.Rect(dialog_rect.x + 100, dialog_rect.y + 84, 270, 24)
            if name_rect.collidepoint(mx, my):
                self._dialog_fields["active_field"] = "name"
                return True
            if size_rect.collidepoint(mx, my):
                self._dialog_fields["active_field"] = "tile_size"
                return True

            ok_rect = pygame.Rect(dialog_rect.x + 100, dialog_rect.y + 175, 80, 30)
            cancel_rect = pygame.Rect(dialog_rect.x + 220, dialog_rect.y + 175, 80, 30)
            if ok_rect.collidepoint(mx, my):
                self._apply_import_tileset()
                self._dialog_active = False
                return True
            if cancel_rect.collidepoint(mx, my):
                self._dialog_active = False
                return True

        return dialog_rect.collidepoint(mx, my)

    def _apply_import_tileset(self) -> None:
        path = self._dialog_fields.get("path", "")
        name = self._dialog_fields.get("name", "Tileset") or "Tileset"
        try:
            tile_size = max(1, int(self._dialog_fields.get("tile_size", "16")))
        except ValueError:
            tile_size = 16

        if not os.path.exists(path):
            self.state.set_notification(f"File not found: {path}", 3.0)
            return

        try:
            img = pygame.image.load(path).convert_alpha()
            cols = img.get_width() // tile_size
            rows = img.get_height() // tile_size
            if cols < 1 or rows < 1:
                self.state.set_notification("Image too small for tile size", 3.0)
                return

            tdef = TilesetDef(
                name=name,
                image_path=path,
                tile_size=tile_size,
                columns=cols,
                rows=rows,
            )
            self.project.definitions.tilesets.append(tdef)
            self.tileset_manager.load_tileset(tdef)

            # Assign to active tiles layer, or first tiles layer
            active_ld = self.state.active_layer_def
            assigned = False
            if active_ld and active_ld.layer_type == LayerType.TILES:
                active_ld.tileset_uid = tdef.uid
                assigned = True
            if not assigned:
                for ld in self.project.definitions.layers:
                    if ld.layer_type == LayerType.TILES:
                        ld.tileset_uid = tdef.uid
                        break

            self.state.needs_save = True
            self.state.set_notification(f"Imported tileset: {name} ({cols}x{rows} tiles)")
        except Exception as e:
            self.state.set_notification(f"Import failed: {e}", 5.0)

    def _draw_import_tileset_dialog(self) -> None:
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        dialog_rect = pygame.Rect(SCREEN_W // 2 - 200, SCREEN_H // 2 - 110, 400, 220)
        pygame.draw.rect(self.screen, Theme.BG_PANEL, dialog_rect, border_radius=8)
        pygame.draw.rect(self.screen, Theme.BORDER_LIGHT, dialog_rect, 2, border_radius=8)

        title = self.font.render("Import Tileset", True, Theme.TEXT_BRIGHT)
        self.screen.blit(title, (dialog_rect.x + 20, dialog_rect.y + 12))

        # File path (read-only display)
        path_lbl = self.font_small.render("File:", True, Theme.TEXT)
        self.screen.blit(path_lbl, (dialog_rect.x + 20, dialog_rect.y + 38))
        path_text = os.path.basename(self._dialog_fields.get("path", ""))
        pt = self.font_small.render(path_text, True, Theme.TEXT_DIM)
        self.screen.blit(pt, (dialog_rect.x + 100, dialog_rect.y + 38))

        af = self._dialog_fields.get("active_field", "name")
        for i, (label, key) in enumerate([("Name:", "name"), ("Tile Size:", "tile_size")]):
            ly = dialog_rect.y + 50 + i * 34
            inp_rect = pygame.Rect(dialog_rect.x + 100, ly, 270, 24)
            self._draw_text_field(label, key, inp_rect, af,
                                  dialog_rect.x + 20, ly + 2)

        hint = self.font_small.render("Tab to switch fields, Enter to confirm", True, Theme.TEXT_DIM)
        self.screen.blit(hint, (dialog_rect.x + 20, dialog_rect.y + 140))

        ok_rect = pygame.Rect(dialog_rect.x + 100, dialog_rect.y + 175, 80, 30)
        cancel_rect = pygame.Rect(dialog_rect.x + 220, dialog_rect.y + 175, 80, 30)
        for rect, label in [(ok_rect, "OK"), (cancel_rect, "Cancel")]:
            pygame.draw.rect(self.screen, Theme.BG_BUTTON, rect, border_radius=4)
            pygame.draw.rect(self.screen, Theme.BORDER_LIGHT, rect, 1, border_radius=4)
            lbl = self.font_small.render(label, True, Theme.TEXT)
            self.screen.blit(lbl, (rect.x + (rect.w - lbl.get_width()) // 2,
                                   rect.y + (rect.h - lbl.get_height()) // 2))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        self.running = True
        last_time = time.time()

        while self.running:
            now = time.time()
            dt = now - last_time
            last_time = now

            self._process_events()
            self._update(dt)
            self._render()

            self.clock.tick(FPS_TARGET)

        pygame.quit()

    def _process_events(self) -> None:
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.VIDEORESIZE:
                # Handle window resize (not typical for 1920x1080 target)
                pass

            # Dialog takes priority
            if self._dialog_active:
                self._handle_dialog_event(event, mx, my)
                continue

            # UI panels consume events first
            ui_consumed = False
            if self.top_bar and self.top_bar.handle_event(event, mx, my):
                ui_consumed = True
            if not ui_consumed and self.left_dock and not self.state.panels_collapsed:
                if self.left_dock.handle_event(event, mx, my):
                    ui_consumed = True
            if not ui_consumed and self.right_dock and not self.state.panels_collapsed:
                if self.right_dock.handle_event(event, mx, my, state=self.state):
                    # Entity selection still handled here
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self._handle_right_dock_entity_click(mx, my)
                    ui_consumed = True
                # During drag-select, forward motion/release even outside panel
                elif self.right_dock._drag_selecting and event.type in (
                    pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP,
                ):
                    self.right_dock.handle_event(event, mx, my, state=self.state)
                    ui_consumed = True

            # Route to input handler
            self.input_handler.handle_event(event, self.state, self.tool_manager, ui_consumed)

    def _handle_right_dock_entity_click(self, mx: int, my: int) -> None:
        """Handle entity selection clicks in the right dock."""
        ld = self.state.active_layer_def
        if ld is None or ld.layer_type != LayerType.ENTITY:
            return
        rd = self.right_dock
        y = rd.rect.y + 4 + 22
        for edef in self.project.definitions.entities:
            item_rect = pygame.Rect(rd.rect.x + Theme.PANEL_PADDING, y,
                                    rd.rect.w - Theme.PANEL_PADDING * 2, Theme.ITEM_HEIGHT)
            if item_rect.collidepoint(mx, my):
                self.state.selected_entity_def_uid = edef.uid
                self.tool_manager.set_active(ToolType.ENTITY_PLACE)
                self.state.set_notification(f"Selected entity: {edef.name}")
                return
            y += Theme.ITEM_HEIGHT

    def _update(self, dt: float) -> None:
        self.state.update_timers(dt)
        self._update_viewport()

        # Cursor blink for dialog text inputs
        if self._dialog_active:
            self._cursor_blink_timer += dt
            if self._cursor_blink_timer >= 0.5:
                self._cursor_blink_timer -= 0.5
                self._cursor_visible = not self._cursor_visible

        # Update tool button states
        if self.left_dock:
            self.left_dock.rebuild(self.state)
            # Sync tool button toggles with active tool
            active_tool = self.tool_manager.active_tool
            if active_tool:
                active_tt = active_tool.tool_type
                for kind, idx, ar, extra in self.left_dock._hit_rects:
                    if kind == "tool" and idx < len(self.left_dock._tool_buttons):
                        self.left_dock._tool_buttons[idx].toggled = (extra == active_tt)

            # Update hover using hit rects (absolute coords)
            mx, my = pygame.mouse.get_pos()
            self.left_dock.update_hover(mx, my)

        # Autosave check
        if (self.state.needs_save and
                self.state.autosave_timer >= self.state.autosave_interval and
                self.project.file_path):
            self._on_save()
            self.state.set_notification("Autosaved")

        # Status text
        tool = self.tool_manager.active_tool
        if tool:
            self.state.status_text = f"Tool: {tool.name}"
            ld = self.state.active_layer_def
            if ld:
                self.state.status_text += f"  |  Layer: {ld.name}"
        else:
            self.state.status_text = "No tool selected"

    def _render(self) -> None:
        self.screen.fill(Theme.BG_CANVAS)

        level = self.state.active_level
        if level:
            gs = self.project.grid_size

            # Draw level background
            sx1, sy1 = self.state.camera.world_to_screen(0, 0)
            sx2, sy2 = self.state.camera.world_to_screen(
                level.pixel_width(gs), level.pixel_height(gs))
            bg_rect = pygame.Rect(int(sx1), int(sy1), int(sx2 - sx1), int(sy2 - sy1))
            clip = self.screen.get_clip()
            self.screen.set_clip(self.state.camera.viewport)
            pygame.draw.rect(self.screen, level.bg_color, bg_rect)
            self.screen.set_clip(clip)

            # Draw layers (bottom to top)
            active_ld = self.state.active_layer_def
            for ld in reversed(self.project.definitions.layers):
                li = level.get_layer_instance(ld.uid)
                if li is None:
                    continue
                # When not showing all layers, skip non-active
                if not self.state.show_all_layers and ld != active_ld:
                    continue
                # Dim inactive layers for visual focus
                saved_opacity = li.opacity
                if self.state.show_all_layers and ld != active_ld:
                    li.opacity = saved_opacity * 0.35
                self.layer_renderer.draw_layer(
                    self.screen, self.state.camera, level, ld, li,
                    self.project.definitions, self.font_small)
                li.opacity = saved_opacity

            # Grid overlay
            if self.state.show_grid:
                draw_grid(self.screen, self.state.camera, gs,
                          level.pixel_width(gs), level.pixel_height(gs))

            # Level border
            draw_level_border(self.screen, self.state.camera,
                              level.pixel_width(gs), level.pixel_height(gs))

            # Tool overlay
            tool = self.tool_manager.active_tool
            if tool:
                old_clip = self.screen.get_clip()
                self.screen.set_clip(self.state.camera.viewport)
                tool.draw_overlay(self.screen, self.state)
                self.screen.set_clip(old_clip)

        # UI panels
        if self.top_bar:
            self.top_bar.draw(self.screen, self.font,
                              self.project.name, self.state.command_stack.is_dirty)

        if not self.state.panels_collapsed:
            if self.left_dock:
                self.left_dock.draw(self.screen, self.font, self.font_small, self.state)
            if self.right_dock:
                self.right_dock.draw(self.screen, self.font, self.font_small,
                                     self.state, self.tileset_manager)

        if self.bottom_bar:
            self.bottom_bar.draw(self.screen, self.font_small, self.state)

        # Dialog
        self._draw_dialog()

        pygame.display.flip()


def main() -> None:
    """Entry point."""
    project_path = None
    if len(sys.argv) > 1:
        project_path = sys.argv[1]

    app = App(project_path=project_path)
    app.init()
    app.run()


if __name__ == "__main__":
    main()
