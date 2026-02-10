"""Tileset loading and caching."""
from __future__ import annotations

import os

import pygame

from birdlevel.project.models import Definitions, TilesetDef


class TilesetManager:
    """Loads, caches, and provides access to tileset images and tile sub-surfaces."""

    def __init__(self):
        # tileset_uid -> full surface
        self.surfaces: dict[str, pygame.Surface] = {}
        # (tileset_uid, tile_id) -> tile surface
        self.tile_cache: dict[tuple[str, int], pygame.Surface] = {}
        # tileset_uid -> (columns, rows)
        self.dimensions: dict[str, tuple[int, int]] = {}
        self.base_path: str = ""

    def set_base_path(self, path: str) -> None:
        """Set the base directory for resolving relative tileset paths."""
        self.base_path = path

    def resolve_path(self, image_path: str) -> str:
        if os.path.isabs(image_path):
            return image_path
        return os.path.join(self.base_path, image_path)

    def load_tileset(self, tdef: TilesetDef) -> bool:
        """Load a tileset image and slice it into tiles."""
        path = self.resolve_path(tdef.image_path)
        if not os.path.exists(path):
            return False
        try:
            img = pygame.image.load(path).convert_alpha()
        except pygame.error:
            return False

        self.surfaces[tdef.uid] = img
        ts = tdef.tile_size
        sp = tdef.spacing
        mg = tdef.margin
        cols = max(1, (img.get_width() - mg + sp) // (ts + sp))
        rows = max(1, (img.get_height() - mg + sp) // (ts + sp))
        tdef.columns = cols
        tdef.rows = rows
        self.dimensions[tdef.uid] = (cols, rows)

        # Clear old cache for this tileset
        keys_to_remove = [k for k in self.tile_cache if k[0] == tdef.uid]
        for k in keys_to_remove:
            del self.tile_cache[k]

        for row in range(rows):
            for col in range(cols):
                x = mg + col * (ts + sp)
                y = mg + row * (ts + sp)
                tile_id = row * cols + col
                rect = pygame.Rect(x, y, ts, ts)
                if rect.right <= img.get_width() and rect.bottom <= img.get_height():
                    self.tile_cache[(tdef.uid, tile_id)] = img.subsurface(rect).copy()
        return True

    def load_all(self, defs: Definitions) -> list[str]:
        """Load all tilesets from definitions. Returns list of failed tileset names."""
        failed = []
        for tdef in defs.tilesets:
            if not self.load_tileset(tdef):
                failed.append(tdef.name)
        return failed

    def get_tile(self, tileset_uid: str, tile_id: int) -> pygame.Surface | None:
        return self.tile_cache.get((tileset_uid, tile_id))

    def get_surface(self, tileset_uid: str) -> pygame.Surface | None:
        return self.surfaces.get(tileset_uid)

    def get_dimensions(self, tileset_uid: str) -> tuple[int, int]:
        return self.dimensions.get(tileset_uid, (0, 0))

    def total_tiles(self, tileset_uid: str) -> int:
        cols, rows = self.get_dimensions(tileset_uid)
        return cols * rows

    def reload_tileset(self, tdef: TilesetDef) -> bool:
        """Reload a single tileset (for hot-reload)."""
        return self.load_tileset(tdef)
