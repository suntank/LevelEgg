"""Command-based undo/redo system.

Every edit is wrapped in a Command object that knows how to apply and revert itself.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from birdlevel.project.models import (
    EntityInstance,
    LayerInstance,
    Level,
    Project,
)


class Command(ABC):
    """Base class for undoable commands."""

    @abstractmethod
    def execute(self) -> None:
        ...

    @abstractmethod
    def undo(self) -> None:
        ...

    def description(self) -> str:
        return self.__class__.__name__


class CommandStack:
    """Manages undo/redo history."""

    def __init__(self, max_history: int = 200):
        self.undo_stack: list[Command] = []
        self.redo_stack: list[Command] = []
        self.max_history = max_history
        self._dirty = False

    def execute(self, cmd: Command) -> None:
        cmd.execute()
        self.undo_stack.append(cmd)
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)
        self._dirty = True

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        cmd = self.undo_stack.pop()
        cmd.undo()
        self.redo_stack.append(cmd)
        self._dirty = True
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        cmd = self.redo_stack.pop()
        cmd.execute()
        self.undo_stack.append(cmd)
        self._dirty = True
        return True

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._dirty = False

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    @property
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0


# ---------------------------------------------------------------------------
# Concrete commands
# ---------------------------------------------------------------------------

@dataclass
class PaintIntGridCommand(Command):
    """Paint a set of intgrid cells."""
    layer_inst: LayerInstance
    cols: int
    cells: list[tuple[int, int, int]]  # (x, y, new_value)
    old_values: list[int] = field(default_factory=list)

    def execute(self) -> None:
        self.old_values.clear()
        for x, y, new_val in self.cells:
            idx = y * self.cols + x
            if self.layer_inst.intgrid and 0 <= idx < len(self.layer_inst.intgrid):
                self.old_values.append(self.layer_inst.intgrid[idx])
                self.layer_inst.intgrid[idx] = new_val
            else:
                self.old_values.append(0)

    def undo(self) -> None:
        for i, (x, y, _) in enumerate(self.cells):
            idx = y * self.cols + x
            if self.layer_inst.intgrid and 0 <= idx < len(self.layer_inst.intgrid):
                self.layer_inst.intgrid[idx] = self.old_values[i]

    def description(self) -> str:
        return f"Paint IntGrid ({len(self.cells)} cells)"


@dataclass
class PaintTileCommand(Command):
    """Paint a set of tiles."""
    layer_inst: LayerInstance
    cols: int
    cells: list[tuple[int, int, int]]  # (x, y, tile_id)
    old_values: list[int] = field(default_factory=list)

    def execute(self) -> None:
        self.old_values.clear()
        for x, y, tile_id in self.cells:
            idx = y * self.cols + x
            if self.layer_inst.tiles and 0 <= idx < len(self.layer_inst.tiles):
                self.old_values.append(self.layer_inst.tiles[idx])
                self.layer_inst.tiles[idx] = tile_id
            else:
                self.old_values.append(-1)

    def undo(self) -> None:
        for i, (x, y, _) in enumerate(self.cells):
            idx = y * self.cols + x
            if self.layer_inst.tiles and 0 <= idx < len(self.layer_inst.tiles):
                self.layer_inst.tiles[idx] = self.old_values[i]

    def description(self) -> str:
        return f"Paint Tiles ({len(self.cells)} cells)"


@dataclass
class PlaceEntityCommand(Command):
    """Place an entity instance."""
    layer_inst: LayerInstance
    entity: EntityInstance

    def execute(self) -> None:
        if self.layer_inst.entities is None:
            self.layer_inst.entities = []
        self.layer_inst.entities.append(self.entity)

    def undo(self) -> None:
        if self.layer_inst.entities and self.entity in self.layer_inst.entities:
            self.layer_inst.entities.remove(self.entity)

    def description(self) -> str:
        return f"Place Entity {self.entity.def_uid}"


@dataclass
class RemoveEntityCommand(Command):
    """Remove an entity instance."""
    layer_inst: LayerInstance
    entity: EntityInstance
    _index: int = -1

    def execute(self) -> None:
        if self.layer_inst.entities and self.entity in self.layer_inst.entities:
            self._index = self.layer_inst.entities.index(self.entity)
            self.layer_inst.entities.remove(self.entity)

    def undo(self) -> None:
        if self.layer_inst.entities is not None:
            if 0 <= self._index <= len(self.layer_inst.entities):
                self.layer_inst.entities.insert(self._index, self.entity)
            else:
                self.layer_inst.entities.append(self.entity)

    def description(self) -> str:
        return f"Remove Entity {self.entity.def_uid}"


@dataclass
class MoveEntityCommand(Command):
    """Move an entity to a new position."""
    entity: EntityInstance
    new_x: int
    new_y: int
    old_x: int = 0
    old_y: int = 0

    def execute(self) -> None:
        self.old_x = self.entity.x
        self.old_y = self.entity.y
        self.entity.x = self.new_x
        self.entity.y = self.new_y

    def undo(self) -> None:
        self.entity.x = self.old_x
        self.entity.y = self.old_y

    def description(self) -> str:
        return f"Move Entity to ({self.new_x}, {self.new_y})"


@dataclass
class ResizeEntityCommand(Command):
    """Resize an entity."""
    entity: EntityInstance
    new_w: int
    new_h: int
    old_w: int = 0
    old_h: int = 0

    def execute(self) -> None:
        self.old_w = self.entity.width
        self.old_h = self.entity.height
        self.entity.width = self.new_w
        self.entity.height = self.new_h

    def undo(self) -> None:
        self.entity.width = self.old_w
        self.entity.height = self.old_h


@dataclass
class EditEntityFieldCommand(Command):
    """Change a field value on an entity."""
    entity: EntityInstance
    field_name: str
    new_value: Any
    old_value: Any = None

    def execute(self) -> None:
        self.old_value = self.entity.fields.get(self.field_name)
        self.entity.fields[self.field_name] = self.new_value

    def undo(self) -> None:
        if self.old_value is None:
            self.entity.fields.pop(self.field_name, None)
        else:
            self.entity.fields[self.field_name] = self.old_value


@dataclass
class ResizeLevelCommand(Command):
    """Resize a level, adjusting layer data."""
    level: Level
    new_cols: int
    new_rows: int
    old_cols: int = 0
    old_rows: int = 0
    old_layer_data: list[dict] = field(default_factory=list)

    def execute(self) -> None:
        self.old_cols = self.level.width_cells
        self.old_rows = self.level.height_cells
        # Snapshot layer data
        self.old_layer_data.clear()
        for li in self.level.layers:
            snapshot: dict[str, Any] = {}
            if li.intgrid is not None:
                snapshot["intgrid"] = li.intgrid.copy()
            if li.tiles is not None:
                snapshot["tiles"] = li.tiles.copy()
            self.old_layer_data.append(snapshot)

        # Resize
        oc, or_ = self.old_cols, self.old_rows
        nc, nr = self.new_cols, self.new_rows
        for li in self.level.layers:
            if li.intgrid is not None:
                new_grid = [0] * (nc * nr)
                for y in range(min(or_, nr)):
                    for x in range(min(oc, nc)):
                        new_grid[y * nc + x] = li.intgrid[y * oc + x]
                li.intgrid = new_grid
            if li.tiles is not None:
                new_tiles = [-1] * (nc * nr)
                for y in range(min(or_, nr)):
                    for x in range(min(oc, nc)):
                        new_tiles[y * nc + x] = li.tiles[y * oc + x]
                li.tiles = new_tiles
        self.level.width_cells = nc
        self.level.height_cells = nr

    def undo(self) -> None:
        self.level.width_cells = self.old_cols
        self.level.height_cells = self.old_rows
        for i, li in enumerate(self.level.layers):
            if i < len(self.old_layer_data):
                snap = self.old_layer_data[i]
                if "intgrid" in snap:
                    li.intgrid = snap["intgrid"]
                if "tiles" in snap:
                    li.tiles = snap["tiles"]


@dataclass
class FloodFillTileCommand(Command):
    """Flood fill tile values."""
    layer_inst: LayerInstance
    cols: int
    rows: int
    start_x: int
    start_y: int
    fill_tile_id: int
    filled_cells: list[tuple[int, int, int]] = field(default_factory=list)

    def execute(self) -> None:
        if self.layer_inst.tiles is None:
            return
        target = self.layer_inst.get_tile(self.start_x, self.start_y, self.cols)
        if target == self.fill_tile_id:
            return
        self.filled_cells.clear()
        visited = set()
        stack = [(self.start_x, self.start_y)]
        while stack:
            x, y = stack.pop()
            if (x, y) in visited:
                continue
            if x < 0 or x >= self.cols or y < 0 or y >= self.rows:
                continue
            val = self.layer_inst.get_tile(x, y, self.cols)
            if val != target:
                continue
            visited.add((x, y))
            self.filled_cells.append((x, y, val))
            self.layer_inst.set_tile(x, y, self.cols, self.fill_tile_id)
            stack.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    def undo(self) -> None:
        for x, y, old_val in self.filled_cells:
            self.layer_inst.set_tile(x, y, self.cols, old_val)


@dataclass
class FloodFillIntGridCommand(Command):
    """Flood fill intgrid values."""
    layer_inst: LayerInstance
    cols: int
    rows: int
    start_x: int
    start_y: int
    fill_value: int
    filled_cells: list[tuple[int, int, int]] = field(default_factory=list)

    def execute(self) -> None:
        if self.layer_inst.intgrid is None:
            return
        target = self.layer_inst.get_intgrid_value(self.start_x, self.start_y, self.cols)
        if target == self.fill_value:
            return
        self.filled_cells.clear()
        visited = set()
        stack = [(self.start_x, self.start_y)]
        while stack:
            x, y = stack.pop()
            if (x, y) in visited:
                continue
            if x < 0 or x >= self.cols or y < 0 or y >= self.rows:
                continue
            val = self.layer_inst.get_intgrid_value(x, y, self.cols)
            if val != target:
                continue
            visited.add((x, y))
            self.filled_cells.append((x, y, val))
            self.layer_inst.set_intgrid_value(x, y, self.cols, self.fill_value)
            stack.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    def undo(self) -> None:
        for x, y, old_val in self.filled_cells:
            self.layer_inst.set_intgrid_value(x, y, self.cols, old_val)
