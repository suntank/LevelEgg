"""Super Simple Export: per-layer PNGs, composite PNG, entities JSON, IntGrid CSV/PNG."""
from __future__ import annotations

import csv
import json
import os
from typing import Any

import pygame

from birdlevel.project.models import (
    Definitions,
    LayerDef,
    LayerInstance,
    LayerType,
    Level,
    Project,
)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def export_simple(
    project: Project,
    output_dir: str,
    tileset_manager: Any = None,
) -> list[str]:
    """Run the Super Simple Export pipeline.

    Outputs per level:
      - One PNG per tile/auto-layer (rendered)
      - Composite PNG (all visible layers)
      - IntGrid CSV per IntGrid layer
      - IntGrid PNG per IntGrid layer
      - Entities JSON per entity layer

    Returns list of created files.
    """
    files: list[str] = []
    defs = project.definitions
    gs = project.grid_size

    for world in project.worlds:
        for level in world.levels:
            level_dir = os.path.join(output_dir, level.name)
            _ensure_dir(level_dir)

            pw = level.pixel_width(gs)
            ph = level.pixel_height(gs)
            composite = pygame.Surface((pw, ph), pygame.SRCALPHA)
            composite.fill((0, 0, 0, 0))

            for ld in defs.layers:
                li = level.get_layer_instance(ld.uid)
                if li is None:
                    continue

                if ld.layer_type == LayerType.INTGRID:
                    # IntGrid CSV
                    csv_path = os.path.join(level_dir, f"{ld.name}_intgrid.csv")
                    _export_intgrid_csv(li, level, ld, csv_path)
                    files.append(csv_path)

                    # IntGrid PNG
                    png_path = os.path.join(level_dir, f"{ld.name}_intgrid.png")
                    surf = _render_intgrid(li, level, ld, gs)
                    pygame.image.save(surf, png_path)
                    files.append(png_path)
                    composite.blit(surf, (0, 0))

                elif ld.layer_type in (LayerType.TILES, LayerType.AUTO_LAYER):
                    png_path = os.path.join(level_dir, f"{ld.name}_tiles.png")
                    surf = _render_tile_layer(li, level, ld, gs, defs, tileset_manager)
                    pygame.image.save(surf, png_path)
                    files.append(png_path)
                    composite.blit(surf, (0, 0))

                elif ld.layer_type == LayerType.ENTITY:
                    json_path = os.path.join(level_dir, f"{ld.name}_entities.json")
                    _export_entities_json(li, defs, json_path)
                    files.append(json_path)

            # Composite PNG
            comp_path = os.path.join(level_dir, "composite.png")
            pygame.image.save(composite, comp_path)
            files.append(comp_path)

    return files


def _export_intgrid_csv(
    li: LayerInstance, level: Level, ld: LayerDef, path: str
) -> None:
    cols = level.width_cells
    rows = level.height_cells
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for gy in range(rows):
            row = []
            for gx in range(cols):
                row.append(li.get_intgrid_value(gx, gy, cols))
            writer.writerow(row)


def _render_intgrid(
    li: LayerInstance, level: Level, ld: LayerDef, gs: int
) -> pygame.Surface:
    cols = level.width_cells
    rows = level.height_cells
    surf = pygame.Surface((cols * gs, rows * gs), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))

    color_map: dict[int, tuple[int, int, int]] = {}
    for vd in ld.intgrid_values:
        color_map[vd.value] = vd.color

    for gy in range(rows):
        for gx in range(cols):
            val = li.get_intgrid_value(gx, gy, cols)
            if val == 0:
                continue
            color = color_map.get(val, (128, 128, 128))
            pygame.draw.rect(surf, (*color, 200), (gx * gs, gy * gs, gs, gs))
    return surf


def _render_tile_layer(
    li: LayerInstance, level: Level, ld: LayerDef, gs: int,
    defs: Definitions, tileset_manager: Any
) -> pygame.Surface:
    cols = level.width_cells
    rows = level.height_cells
    surf = pygame.Surface((cols * gs, rows * gs), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))

    if li.tiles is None or ld.tileset_uid is None:
        return surf

    for gy in range(rows):
        for gx in range(cols):
            tid = li.get_tile(gx, gy, cols)
            if tid < 0:
                continue
            if tileset_manager:
                tile_surf = tileset_manager.get_tile(ld.tileset_uid, tid)
                if tile_surf:
                    surf.blit(tile_surf, (gx * gs, gy * gs))
                    continue
            # Fallback: colored placeholder
            pygame.draw.rect(surf, (180, 120, 200, 180), (gx * gs, gy * gs, gs, gs))
    return surf


def _export_entities_json(
    li: LayerInstance, defs: Definitions, path: str
) -> None:
    if li.entities is None:
        entities_data: list[dict] = []
    else:
        entities_data = []
        for ent in li.entities:
            edef = defs.entity_by_uid(ent.def_uid)
            entities_data.append({
                "uid": ent.uid,
                "type": edef.name if edef else ent.def_uid,
                "x": ent.x,
                "y": ent.y,
                "width": ent.width,
                "height": ent.height,
                "fields": ent.fields,
            })
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"entities": entities_data}, f, indent=2, ensure_ascii=False)
