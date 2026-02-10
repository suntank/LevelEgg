"""Layer rendering for the editor canvas."""
from __future__ import annotations

import pygame

from birdlevel.assets.tileset_loader import TilesetManager
from birdlevel.project.models import (
    Definitions,
    LayerDef,
    LayerInstance,
    LayerType,
    Level,
)
from birdlevel.render.camera import Camera


class LayerRenderer:
    """Renders layer instances onto the editor canvas."""

    def __init__(self, tileset_manager: TilesetManager | None = None):
        self.tileset_manager = tileset_manager
        # Cache for tileset surfaces keyed by tileset uid
        self.tileset_surfaces: dict[str, pygame.Surface] = {}
        # Cache for individual tile surfaces: (tileset_uid, tile_id) -> Surface
        self.tile_cache: dict[tuple[str, int], pygame.Surface] = {}

    def load_tileset_surface(self, uid: str, path: str, tile_size: int,
                              spacing: int = 0, margin: int = 0) -> bool:
        """Load a tileset image and cache tile sub-surfaces."""
        try:
            img = pygame.image.load(path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return False
        self.tileset_surfaces[uid] = img
        # Slice into tiles
        cols = (img.get_width() - margin + spacing) // (tile_size + spacing)
        rows = (img.get_height() - margin + spacing) // (tile_size + spacing)
        for row in range(rows):
            for col in range(cols):
                x = margin + col * (tile_size + spacing)
                y = margin + row * (tile_size + spacing)
                tile_id = row * cols + col
                rect = pygame.Rect(x, y, tile_size, tile_size)
                self.tile_cache[(uid, tile_id)] = img.subsurface(rect).copy()
        return True

    def get_tile_surface(self, tileset_uid: str, tile_id: int) -> pygame.Surface | None:
        # Prefer TilesetManager if available
        if self.tileset_manager is not None:
            surf = self.tileset_manager.get_tile(tileset_uid, tile_id)
            if surf is not None:
                return surf
        return self.tile_cache.get((tileset_uid, tile_id))

    def draw_intgrid_layer(
        self,
        surface: pygame.Surface,
        camera: Camera,
        level: Level,
        layer_def: LayerDef,
        layer_inst: LayerInstance,
    ) -> None:
        """Draw an IntGrid layer as colored cells."""
        if layer_inst.intgrid is None:
            return
        gs = layer_def.grid_size
        cols = level.width_cells
        rows = level.height_cells

        # Build color map from definition
        color_map: dict[int, tuple[int, int, int]] = {}
        for vd in layer_def.intgrid_values:
            color_map[vd.value] = vd.color

        vr = camera.visible_world_rect()
        start_col = max(0, vr.x // gs)
        start_row = max(0, vr.y // gs)
        end_col = min(cols, (vr.x + vr.w) // gs + 2)
        end_row = min(rows, (vr.y + vr.h) // gs + 2)

        clip = surface.get_clip()
        surface.set_clip(camera.viewport)

        for gy in range(start_row, end_row):
            for gx in range(start_col, end_col):
                val = layer_inst.get_intgrid_value(gx, gy, cols)
                if val == 0:
                    continue
                color = color_map.get(val, (128, 128, 128))
                sx, sy = camera.world_to_screen(gx * gs, gy * gs)
                scaled = int(gs * camera.zoom)
                if scaled < 1:
                    scaled = 1
                alpha_color = (*color, int(180 * layer_inst.opacity))
                cell_surf = pygame.Surface((scaled, scaled), pygame.SRCALPHA)
                cell_surf.fill(alpha_color)
                surface.blit(cell_surf, (int(sx), int(sy)))

        surface.set_clip(clip)

    def draw_tile_layer(
        self,
        surface: pygame.Surface,
        camera: Camera,
        level: Level,
        layer_def: LayerDef,
        layer_inst: LayerInstance,
        defs: Definitions,
    ) -> None:
        """Draw a tile layer."""
        if layer_inst.tiles is None:
            return
        ts_uid = layer_def.tileset_uid
        if ts_uid is None:
            return
        gs = layer_def.grid_size
        cols = level.width_cells
        rows = level.height_cells

        vr = camera.visible_world_rect()
        start_col = max(0, vr.x // gs)
        start_row = max(0, vr.y // gs)
        end_col = min(cols, (vr.x + vr.w) // gs + 2)
        end_row = min(rows, (vr.y + vr.h) // gs + 2)

        clip = surface.get_clip()
        surface.set_clip(camera.viewport)

        scaled = max(1, int(gs * camera.zoom))

        for gy in range(start_row, end_row):
            for gx in range(start_col, end_col):
                tid = layer_inst.get_tile(gx, gy, cols)
                if tid < 0:
                    continue
                tile_surf = self.get_tile_surface(ts_uid, tid)
                if tile_surf is None:
                    # Draw placeholder
                    sx, sy = camera.world_to_screen(gx * gs, gy * gs)
                    placeholder = pygame.Surface((scaled, scaled), pygame.SRCALPHA)
                    placeholder.fill((180, 120, 200, int(180 * layer_inst.opacity)))
                    surface.blit(placeholder, (int(sx), int(sy)))
                    continue
                sx, sy = camera.world_to_screen(gx * gs, gy * gs)
                if scaled != gs:
                    tile_surf = pygame.transform.scale(tile_surf, (scaled, scaled))
                if layer_inst.opacity < 1.0:
                    tile_surf = tile_surf.copy()
                    tile_surf.set_alpha(int(255 * layer_inst.opacity))
                surface.blit(tile_surf, (int(sx), int(sy)))

        surface.set_clip(clip)

    def draw_entity_layer(
        self,
        surface: pygame.Surface,
        camera: Camera,
        level: Level,
        layer_def: LayerDef,
        layer_inst: LayerInstance,
        defs: Definitions,
        font: pygame.font.Font | None = None,
    ) -> None:
        """Draw entity instances."""
        if layer_inst.entities is None:
            return

        clip = surface.get_clip()
        surface.set_clip(camera.viewport)

        for ent in layer_inst.entities:
            edef = defs.entity_by_uid(ent.def_uid)
            color = edef.color if edef else (255, 100, 100)
            sx, sy = camera.world_to_screen(ent.x, ent.y)
            sw = int(ent.width * camera.zoom)
            sh = int(ent.height * camera.zoom)
            if sw < 2:
                sw = 2
            if sh < 2:
                sh = 2

            # Fill
            ent_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
            ent_surf.fill((*color, int(140 * layer_inst.opacity)))
            surface.blit(ent_surf, (int(sx), int(sy)))
            # Border
            pygame.draw.rect(surface, color, (int(sx), int(sy), sw, sh), 2)

            # Label
            if font and camera.zoom >= 0.5:
                name = edef.name if edef else "?"
                label = font.render(name, True, (255, 255, 255))
                surface.blit(label, (int(sx) + 2, int(sy) + 2))

        surface.set_clip(clip)

    def draw_layer(
        self,
        surface: pygame.Surface,
        camera: Camera,
        level: Level,
        layer_def: LayerDef,
        layer_inst: LayerInstance,
        defs: Definitions,
        font: pygame.font.Font | None = None,
    ) -> None:
        """Draw a single layer based on its type."""
        if not layer_inst.visible:
            return
        if layer_def.layer_type == LayerType.INTGRID:
            self.draw_intgrid_layer(surface, camera, level, layer_def, layer_inst)
        elif layer_def.layer_type in (LayerType.TILES, LayerType.AUTO_LAYER):
            self.draw_tile_layer(surface, camera, level, layer_def, layer_inst, defs)
        elif layer_def.layer_type == LayerType.ENTITY:
            self.draw_entity_layer(surface, camera, level, layer_def, layer_inst, defs, font)
