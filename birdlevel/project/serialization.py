"""JSON serialization and deserialization for BirdLevel projects."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from birdlevel.project.models import (
    AutoRuleDef,
    Definitions,
    EntityDef,
    EntityInstance,
    EnumDef,
    EnumValue,
    FieldDef,
    FieldType,
    IntGridValueDef,
    LayerDef,
    LayerInstance,
    LayerType,
    LayoutMode,
    Level,
    Project,
    RuleCell,
    RuleCellReq,
    TileInstance,
    TilesetDef,
    World,
)

FORMAT_VERSION = 1


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _color_to_list(c: tuple[int, int, int]) -> list[int]:
    return list(c)


def _list_to_color(lst: list[int] | None) -> tuple[int, int, int]:
    if lst and len(lst) >= 3:
        return (lst[0], lst[1], lst[2])
    return (128, 128, 128)


# ---------------------------------------------------------------------------
# To dict
# ---------------------------------------------------------------------------

def tileset_def_to_dict(t: TilesetDef) -> dict:
    return {
        "uid": t.uid,
        "name": t.name,
        "image_path": t.image_path,
        "tile_size": t.tile_size,
        "spacing": t.spacing,
        "margin": t.margin,
        "columns": t.columns,
        "rows": t.rows,
    }


def enum_value_to_dict(v: EnumValue) -> dict:
    return {"name": v.name, "color": _color_to_list(v.color)}


def enum_def_to_dict(e: EnumDef) -> dict:
    return {
        "uid": e.uid,
        "name": e.name,
        "values": [enum_value_to_dict(v) for v in e.values],
    }


def field_def_to_dict(f: FieldDef) -> dict:
    d: dict[str, Any] = {
        "name": f.name,
        "field_type": f.field_type.value,
    }
    if f.default_value is not None:
        d["default_value"] = f.default_value
    if f.min_value is not None:
        d["min_value"] = f.min_value
    if f.max_value is not None:
        d["max_value"] = f.max_value
    if f.enum_uid is not None:
        d["enum_uid"] = f.enum_uid
    if f.array_element_type is not None:
        d["array_element_type"] = f.array_element_type.value
    return d


def entity_def_to_dict(e: EntityDef) -> dict:
    return {
        "uid": e.uid,
        "name": e.name,
        "width": e.width,
        "height": e.height,
        "color": _color_to_list(e.color),
        "fields": [field_def_to_dict(f) for f in e.fields],
        "singleton": e.singleton,
        "grid_locked": e.grid_locked,
        "resizable": e.resizable,
    }


def intgrid_value_def_to_dict(v: IntGridValueDef) -> dict:
    return {"value": v.value, "name": v.name, "color": _color_to_list(v.color)}


def layer_def_to_dict(ld: LayerDef) -> dict:
    d: dict[str, Any] = {
        "uid": ld.uid,
        "name": ld.name,
        "layer_type": ld.layer_type.value,
        "grid_size": ld.grid_size,
        "opacity": ld.opacity,
    }
    if ld.tileset_uid is not None:
        d["tileset_uid"] = ld.tileset_uid
    if ld.entity_tags:
        d["entity_tags"] = ld.entity_tags
    if ld.intgrid_values:
        d["intgrid_values"] = [intgrid_value_def_to_dict(v) for v in ld.intgrid_values]
    if ld.source_layer_uid is not None:
        d["source_layer_uid"] = ld.source_layer_uid
    return d


def rule_cell_to_dict(rc: RuleCell) -> dict:
    return {
        "dx": rc.dx,
        "dy": rc.dy,
        "requirement": rc.requirement.value,
        "values": rc.values,
    }


def auto_rule_def_to_dict(r: AutoRuleDef) -> dict:
    return {
        "uid": r.uid,
        "name": r.name,
        "source_layer_uid": r.source_layer_uid,
        "source_values": r.source_values,
        "pattern": [rule_cell_to_dict(c) for c in r.pattern],
        "output_tiles": r.output_tiles,
        "output_weights": r.output_weights,
        "priority": r.priority,
        "allow_rotation": r.allow_rotation,
        "allow_mirror": r.allow_mirror,
    }


def definitions_to_dict(defs: Definitions) -> dict:
    return {
        "tilesets": [tileset_def_to_dict(t) for t in defs.tilesets],
        "enums": [enum_def_to_dict(e) for e in defs.enums],
        "entities": [entity_def_to_dict(e) for e in defs.entities],
        "layers": [layer_def_to_dict(l) for l in defs.layers],
        "auto_rules": [auto_rule_def_to_dict(r) for r in defs.auto_rules],
    }


def tile_instance_to_dict(ti: TileInstance) -> dict:
    return {"tile_id": ti.tile_id, "flip_x": ti.flip_x, "flip_y": ti.flip_y}


def entity_instance_to_dict(ei: EntityInstance) -> dict:
    return {
        "uid": ei.uid,
        "def_uid": ei.def_uid,
        "x": ei.x,
        "y": ei.y,
        "width": ei.width,
        "height": ei.height,
        "fields": ei.fields,
    }


def layer_instance_to_dict(li: LayerInstance) -> dict:
    d: dict[str, Any] = {
        "layer_def_uid": li.layer_def_uid,
        "visible": li.visible,
        "locked": li.locked,
        "opacity": li.opacity,
    }
    if li.intgrid is not None:
        d["intgrid"] = li.intgrid
    if li.tiles is not None:
        d["tiles"] = li.tiles
    if li.tile_stacks is not None:
        stacks: dict[str, list[dict]] = {}
        for key, stack in li.tile_stacks.items():
            stacks[key] = [tile_instance_to_dict(ti) for ti in stack]
        d["tile_stacks"] = stacks
    if li.entities is not None:
        d["entities"] = [entity_instance_to_dict(e) for e in li.entities]
    return d


def level_to_dict(level: Level) -> dict:
    return {
        "uid": level.uid,
        "name": level.name,
        "world_x": level.world_x,
        "world_y": level.world_y,
        "width_cells": level.width_cells,
        "height_cells": level.height_cells,
        "bg_color": _color_to_list(level.bg_color),
        "layers": [layer_instance_to_dict(li) for li in level.layers],
    }


def world_to_dict(world: World) -> dict:
    return {
        "uid": world.uid,
        "name": world.name,
        "layout": world.layout.value,
        "levels": [level_to_dict(l) for l in world.levels],
    }


def project_to_dict(project: Project) -> dict:
    return {
        "format_version": project.format_version,
        "project": {
            "name": project.name,
            "grid_size": project.grid_size,
            "separate_level_files": project.separate_level_files,
            "definitions": definitions_to_dict(project.definitions),
            "worlds": [world_to_dict(w) for w in project.worlds],
        },
    }


# ---------------------------------------------------------------------------
# From dict
# ---------------------------------------------------------------------------

def tileset_def_from_dict(d: dict) -> TilesetDef:
    return TilesetDef(
        uid=d.get("uid", ""),
        name=d.get("name", ""),
        image_path=d.get("image_path", ""),
        tile_size=d.get("tile_size", 16),
        spacing=d.get("spacing", 0),
        margin=d.get("margin", 0),
        columns=d.get("columns", 0),
        rows=d.get("rows", 0),
    )


def enum_value_from_dict(d: dict) -> EnumValue:
    return EnumValue(name=d.get("name", ""), color=_list_to_color(d.get("color")))


def enum_def_from_dict(d: dict) -> EnumDef:
    return EnumDef(
        uid=d.get("uid", ""),
        name=d.get("name", ""),
        values=[enum_value_from_dict(v) for v in d.get("values", [])],
    )


def field_def_from_dict(d: dict) -> FieldDef:
    ft = FieldType(d.get("field_type", "int"))
    aet = None
    if "array_element_type" in d:
        aet = FieldType(d["array_element_type"])
    return FieldDef(
        name=d.get("name", ""),
        field_type=ft,
        default_value=d.get("default_value"),
        min_value=d.get("min_value"),
        max_value=d.get("max_value"),
        enum_uid=d.get("enum_uid"),
        array_element_type=aet,
    )


def entity_def_from_dict(d: dict) -> EntityDef:
    return EntityDef(
        uid=d.get("uid", ""),
        name=d.get("name", ""),
        width=d.get("width", 16),
        height=d.get("height", 16),
        color=_list_to_color(d.get("color")),
        fields=[field_def_from_dict(f) for f in d.get("fields", [])],
        singleton=d.get("singleton", False),
        grid_locked=d.get("grid_locked", True),
        resizable=d.get("resizable", False),
    )


def intgrid_value_def_from_dict(d: dict) -> IntGridValueDef:
    return IntGridValueDef(
        value=d.get("value", 1),
        name=d.get("name", ""),
        color=_list_to_color(d.get("color")),
    )


def layer_def_from_dict(d: dict) -> LayerDef:
    return LayerDef(
        uid=d.get("uid", ""),
        name=d.get("name", ""),
        layer_type=LayerType(d.get("layer_type", "tiles")),
        grid_size=d.get("grid_size", 16),
        tileset_uid=d.get("tileset_uid"),
        entity_tags=d.get("entity_tags", []),
        intgrid_values=[intgrid_value_def_from_dict(v) for v in d.get("intgrid_values", [])],
        opacity=d.get("opacity", 1.0),
        source_layer_uid=d.get("source_layer_uid"),
    )


def rule_cell_from_dict(d: dict) -> RuleCell:
    return RuleCell(
        dx=d.get("dx", 0),
        dy=d.get("dy", 0),
        requirement=RuleCellReq(d.get("requirement", "any")),
        values=d.get("values", []),
    )


def auto_rule_def_from_dict(d: dict) -> AutoRuleDef:
    return AutoRuleDef(
        uid=d.get("uid", ""),
        name=d.get("name", ""),
        source_layer_uid=d.get("source_layer_uid", ""),
        source_values=d.get("source_values", []),
        pattern=[rule_cell_from_dict(c) for c in d.get("pattern", [])],
        output_tiles=d.get("output_tiles", []),
        output_weights=d.get("output_weights", []),
        priority=d.get("priority", 0),
        allow_rotation=d.get("allow_rotation", False),
        allow_mirror=d.get("allow_mirror", False),
    )


def definitions_from_dict(d: dict) -> Definitions:
    return Definitions(
        tilesets=[tileset_def_from_dict(t) for t in d.get("tilesets", [])],
        enums=[enum_def_from_dict(e) for e in d.get("enums", [])],
        entities=[entity_def_from_dict(e) for e in d.get("entities", [])],
        layers=[layer_def_from_dict(l) for l in d.get("layers", [])],
        auto_rules=[auto_rule_def_from_dict(r) for r in d.get("auto_rules", [])],
    )


def tile_instance_from_dict(d: dict) -> TileInstance:
    return TileInstance(
        tile_id=d.get("tile_id", 0),
        flip_x=d.get("flip_x", False),
        flip_y=d.get("flip_y", False),
    )


def entity_instance_from_dict(d: dict) -> EntityInstance:
    return EntityInstance(
        uid=d.get("uid", ""),
        def_uid=d.get("def_uid", ""),
        x=d.get("x", 0),
        y=d.get("y", 0),
        width=d.get("width", 16),
        height=d.get("height", 16),
        fields=d.get("fields", {}),
    )


def layer_instance_from_dict(d: dict) -> LayerInstance:
    tile_stacks = None
    if "tile_stacks" in d:
        tile_stacks = {}
        for key, stack_list in d["tile_stacks"].items():
            tile_stacks[key] = [tile_instance_from_dict(ti) for ti in stack_list]
    entities = None
    if "entities" in d:
        entities = [entity_instance_from_dict(e) for e in d["entities"]]
    return LayerInstance(
        layer_def_uid=d.get("layer_def_uid", ""),
        intgrid=d.get("intgrid"),
        tiles=d.get("tiles"),
        tile_stacks=tile_stacks,
        entities=entities,
        visible=d.get("visible", True),
        locked=d.get("locked", False),
        opacity=d.get("opacity", 1.0),
    )


def level_from_dict(d: dict) -> Level:
    return Level(
        uid=d.get("uid", ""),
        name=d.get("name", ""),
        world_x=d.get("world_x", 0),
        world_y=d.get("world_y", 0),
        width_cells=d.get("width_cells", 30),
        height_cells=d.get("height_cells", 20),
        bg_color=_list_to_color(d.get("bg_color")),
        layers=[layer_instance_from_dict(li) for li in d.get("layers", [])],
    )


def world_from_dict(d: dict) -> World:
    return World(
        uid=d.get("uid", ""),
        name=d.get("name", ""),
        layout=LayoutMode(d.get("layout", "free")),
        levels=[level_from_dict(l) for l in d.get("levels", [])],
    )


def project_from_dict(d: dict) -> Project:
    pd = d.get("project", d)
    return Project(
        format_version=d.get("format_version", 1),
        name=pd.get("name", "Untitled"),
        grid_size=pd.get("grid_size", 16),
        definitions=definitions_from_dict(pd.get("definitions", {})),
        worlds=[world_from_dict(w) for w in pd.get("worlds", [])],
        separate_level_files=pd.get("separate_level_files", False),
    )


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def save_project(project: Project, file_path: str | None = None) -> str:
    """Save project to JSON atomically. Returns the path saved to."""
    path = file_path or project.file_path
    if path is None:
        path = os.path.join(os.getcwd(), f"{project.name}.birdlevel")
    project.file_path = path

    data = project_to_dict(project)
    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    # Atomic write: temp file -> fsync -> rename
    dir_path = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json_str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return path


def load_project(file_path: str) -> Project:
    """Load project from JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    project = project_from_dict(data)
    project.file_path = file_path
    return project
