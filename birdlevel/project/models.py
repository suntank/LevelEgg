"""Core data model for BirdLevel projects.

Pure data classes representing the project structure.
Definitions are reusable templates; instances reference them by stable IDs.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LayerType(Enum):
    INTGRID = "intgrid"
    TILES = "tiles"
    ENTITY = "entity"
    AUTO_LAYER = "auto_layer"


class LayoutMode(Enum):
    FREE = "free"
    LINEAR = "linear"
    GRIDVANIA = "gridvania"


class FieldType(Enum):
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"
    ENUM = "enum"
    ARRAY = "array"
    OPTIONAL = "optional"
    POINT = "point"
    RECT = "rect"


class RuleCellReq(Enum):
    ANY = "any"
    MUST_MATCH = "must_match"
    MUST_NOT_MATCH = "must_not_match"


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------

@dataclass
class TilesetDef:
    uid: str = field(default_factory=_uid)
    name: str = "Untitled Tileset"
    image_path: str = ""
    tile_size: int = 16
    spacing: int = 0
    margin: int = 0
    columns: int = 0
    rows: int = 0


@dataclass
class EnumValue:
    name: str = ""
    color: tuple[int, int, int] = (200, 200, 200)


@dataclass
class EnumDef:
    uid: str = field(default_factory=_uid)
    name: str = "Untitled Enum"
    values: list[EnumValue] = field(default_factory=list)


@dataclass
class FieldDef:
    name: str = ""
    field_type: FieldType = FieldType.INT
    default_value: Any = None
    min_value: float | None = None
    max_value: float | None = None
    enum_uid: str | None = None
    array_element_type: FieldType | None = None


@dataclass
class EntityDef:
    uid: str = field(default_factory=_uid)
    name: str = "Untitled Entity"
    width: int = 16
    height: int = 16
    color: tuple[int, int, int] = (255, 100, 100)
    fields: list[FieldDef] = field(default_factory=list)
    singleton: bool = False
    grid_locked: bool = True
    resizable: bool = False


@dataclass
class IntGridValueDef:
    value: int = 1
    name: str = ""
    color: tuple[int, int, int] = (100, 100, 255)


@dataclass
class LayerDef:
    uid: str = field(default_factory=_uid)
    name: str = "Untitled Layer"
    layer_type: LayerType = LayerType.TILES
    grid_size: int = 16
    tileset_uid: str | None = None
    entity_tags: list[str] = field(default_factory=list)
    intgrid_values: list[IntGridValueDef] = field(default_factory=list)
    opacity: float = 1.0
    # For auto-layers: reference to source intgrid layer
    source_layer_uid: str | None = None


@dataclass
class RuleCell:
    dx: int = 0
    dy: int = 0
    requirement: RuleCellReq = RuleCellReq.ANY
    values: list[int] = field(default_factory=list)


@dataclass
class AutoRuleDef:
    uid: str = field(default_factory=_uid)
    name: str = "Untitled Rule"
    source_layer_uid: str = ""
    source_values: list[int] = field(default_factory=list)
    pattern: list[RuleCell] = field(default_factory=list)
    output_tiles: list[int] = field(default_factory=list)
    output_weights: list[float] = field(default_factory=list)
    priority: int = 0
    allow_rotation: bool = False
    allow_mirror: bool = False


# ---------------------------------------------------------------------------
# Definitions container
# ---------------------------------------------------------------------------

@dataclass
class Definitions:
    tilesets: list[TilesetDef] = field(default_factory=list)
    enums: list[EnumDef] = field(default_factory=list)
    entities: list[EntityDef] = field(default_factory=list)
    layers: list[LayerDef] = field(default_factory=list)
    auto_rules: list[AutoRuleDef] = field(default_factory=list)

    def tileset_by_uid(self, uid: str) -> TilesetDef | None:
        for t in self.tilesets:
            if t.uid == uid:
                return t
        return None

    def layer_by_uid(self, uid: str) -> LayerDef | None:
        for l in self.layers:
            if l.uid == uid:
                return l
        return None

    def entity_by_uid(self, uid: str) -> EntityDef | None:
        for e in self.entities:
            if e.uid == uid:
                return e
        return None

    def enum_by_uid(self, uid: str) -> EnumDef | None:
        for e in self.enums:
            if e.uid == uid:
                return e
        return None


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

@dataclass
class TileInstance:
    tile_id: int = 0
    flip_x: bool = False
    flip_y: bool = False


@dataclass
class EntityInstance:
    uid: str = field(default_factory=_uid)
    def_uid: str = ""
    x: int = 0
    y: int = 0
    width: int = 16
    height: int = 16
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class LayerInstance:
    layer_def_uid: str = ""
    # IntGrid data: flat list, row-major, size = cols * rows
    intgrid: list[int] | None = None
    # Tile data: flat list of tile IDs (-1 = empty), row-major
    tiles: list[int] | None = None
    # Stacked tiles: sparse dict of (x,y) -> list[TileInstance]
    tile_stacks: dict[str, list[TileInstance]] | None = None
    # Entity instances
    entities: list[EntityInstance] | None = None
    # Auto-layer computed tiles (not saved, regenerated)
    auto_tiles: list[int] | None = None
    # Per-instance overrides
    visible: bool = True
    locked: bool = False
    opacity: float = 1.0

    def ensure_intgrid(self, cols: int, rows: int) -> None:
        if self.intgrid is None:
            self.intgrid = [0] * (cols * rows)
        elif len(self.intgrid) < cols * rows:
            self.intgrid.extend([0] * (cols * rows - len(self.intgrid)))

    def ensure_tiles(self, cols: int, rows: int) -> None:
        if self.tiles is None:
            self.tiles = [-1] * (cols * rows)
        elif len(self.tiles) < cols * rows:
            self.tiles.extend([-1] * (cols * rows - len(self.tiles)))

    def ensure_entities(self) -> None:
        if self.entities is None:
            self.entities = []

    def get_intgrid_value(self, x: int, y: int, cols: int) -> int:
        if self.intgrid is None:
            return 0
        idx = y * cols + x
        if 0 <= idx < len(self.intgrid):
            return self.intgrid[idx]
        return 0

    def set_intgrid_value(self, x: int, y: int, cols: int, value: int) -> None:
        if self.intgrid is None:
            return
        idx = y * cols + x
        if 0 <= idx < len(self.intgrid):
            self.intgrid[idx] = value

    def get_tile(self, x: int, y: int, cols: int) -> int:
        if self.tiles is None:
            return -1
        idx = y * cols + x
        if 0 <= idx < len(self.tiles):
            return self.tiles[idx]
        return -1

    def set_tile(self, x: int, y: int, cols: int, tile_id: int) -> None:
        if self.tiles is None:
            return
        idx = y * cols + x
        if 0 <= idx < len(self.tiles):
            self.tiles[idx] = tile_id


@dataclass
class Level:
    uid: str = field(default_factory=_uid)
    name: str = "Untitled Level"
    world_x: int = 0
    world_y: int = 0
    width_cells: int = 30
    height_cells: int = 20
    layers: list[LayerInstance] = field(default_factory=list)
    bg_color: tuple[int, int, int] = (40, 40, 60)

    def cols(self, grid_size: int = 16) -> int:
        return self.width_cells

    def rows(self, grid_size: int = 16) -> int:
        return self.height_cells

    def pixel_width(self, grid_size: int = 16) -> int:
        return self.width_cells * grid_size

    def pixel_height(self, grid_size: int = 16) -> int:
        return self.height_cells * grid_size

    def get_layer_instance(self, layer_def_uid: str) -> LayerInstance | None:
        for li in self.layers:
            if li.layer_def_uid == layer_def_uid:
                return li
        return None

    def ensure_layer_instances(self, layer_defs: list[LayerDef]) -> None:
        existing = {li.layer_def_uid for li in self.layers}
        for ld in layer_defs:
            if ld.uid not in existing:
                li = LayerInstance(layer_def_uid=ld.uid)
                cols = self.width_cells
                rows = self.height_cells
                if ld.layer_type == LayerType.INTGRID:
                    li.ensure_intgrid(cols, rows)
                elif ld.layer_type == LayerType.TILES:
                    li.ensure_tiles(cols, rows)
                elif ld.layer_type == LayerType.ENTITY:
                    li.ensure_entities()
                elif ld.layer_type == LayerType.AUTO_LAYER:
                    li.ensure_tiles(cols, rows)
                self.layers.append(li)


@dataclass
class World:
    uid: str = field(default_factory=_uid)
    name: str = "World"
    layout: LayoutMode = LayoutMode.FREE
    levels: list[Level] = field(default_factory=list)


@dataclass
class Project:
    format_version: int = 1
    name: str = "Untitled Project"
    grid_size: int = 16
    definitions: Definitions = field(default_factory=Definitions)
    worlds: list[World] = field(default_factory=list)
    file_path: str | None = None
    separate_level_files: bool = False

    def active_world(self) -> World | None:
        if self.worlds:
            return self.worlds[0]
        return None

    def create_default(self) -> None:
        """Set up a fresh project with one world and one level."""
        world = World(name="Main World")
        level = Level(name="Level_0")
        # Create default IntGrid layer
        intgrid_layer = LayerDef(
            name="IntGrid",
            layer_type=LayerType.INTGRID,
            grid_size=self.grid_size,
            intgrid_values=[
                IntGridValueDef(value=1, name="Wall", color=(80, 130, 220)),
                IntGridValueDef(value=2, name="Ground", color=(100, 180, 80)),
                IntGridValueDef(value=3, name="Hazard", color=(220, 80, 80)),
            ],
        )
        # Create default Tile layer
        tile_layer = LayerDef(
            name="Tiles",
            layer_type=LayerType.TILES,
            grid_size=self.grid_size,
        )
        # Create default Entity layer
        entity_layer = LayerDef(
            name="Entities",
            layer_type=LayerType.ENTITY,
            grid_size=self.grid_size,
        )
        self.definitions.layers = [intgrid_layer, tile_layer, entity_layer]
        level.ensure_layer_instances(self.definitions.layers)
        world.levels.append(level)
        self.worlds.append(world)
