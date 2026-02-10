"""Auto-layer rule solver: generates tile layers from IntGrid data."""
from __future__ import annotations

import random
from typing import Any

from birdlevel.project.models import (
    AutoRuleDef,
    Definitions,
    LayerDef,
    LayerInstance,
    LayerType,
    Level,
    RuleCell,
    RuleCellReq,
)


class RuleSolver:
    """Evaluates auto-layer rules against IntGrid data to produce tile output."""

    def __init__(self, definitions: Definitions):
        self.definitions = definitions

    def solve_all(self, level: Level) -> None:
        """Run all auto-layer rules for the given level."""
        for ld in self.definitions.layers:
            if ld.layer_type != LayerType.AUTO_LAYER:
                continue
            if ld.source_layer_uid is None:
                continue
            self._solve_layer(level, ld)

    def solve_dirty(self, level: Level, dirty_cells: set[tuple[int, int]],
                    padding: int = 1) -> None:
        """Incrementally re-solve only around dirty cells."""
        if not dirty_cells:
            return
        # Expand dirty region by padding
        expanded: set[tuple[int, int]] = set()
        for cx, cy in dirty_cells:
            for dx in range(-padding, padding + 1):
                for dy in range(-padding, padding + 1):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < level.width_cells and 0 <= ny < level.height_cells:
                        expanded.add((nx, ny))

        for ld in self.definitions.layers:
            if ld.layer_type != LayerType.AUTO_LAYER:
                continue
            if ld.source_layer_uid is None:
                continue
            self._solve_layer_partial(level, ld, expanded)

    def _solve_layer(self, level: Level, auto_ld: LayerDef) -> None:
        """Full solve for one auto-layer."""
        li = level.get_layer_instance(auto_ld.uid)
        if li is None:
            return
        li.ensure_tiles(level.width_cells, level.height_cells)

        source_li = level.get_layer_instance(auto_ld.source_layer_uid)
        if source_li is None or source_li.intgrid is None:
            return

        # Get applicable rules
        rules = [r for r in self.definitions.auto_rules
                 if r.source_layer_uid == auto_ld.source_layer_uid]
        rules.sort(key=lambda r: r.priority, reverse=True)

        cols = level.width_cells
        rows = level.height_cells

        # Clear auto tiles
        li.tiles = [-1] * (cols * rows)

        for gy in range(rows):
            for gx in range(cols):
                tile_id = self._evaluate_cell(gx, gy, cols, rows, source_li, rules)
                if tile_id >= 0:
                    li.set_tile(gx, gy, cols, tile_id)

    def _solve_layer_partial(self, level: Level, auto_ld: LayerDef,
                             cells: set[tuple[int, int]]) -> None:
        """Partial solve for specific cells."""
        li = level.get_layer_instance(auto_ld.uid)
        if li is None:
            return
        li.ensure_tiles(level.width_cells, level.height_cells)

        source_li = level.get_layer_instance(auto_ld.source_layer_uid)
        if source_li is None or source_li.intgrid is None:
            return

        rules = [r for r in self.definitions.auto_rules
                 if r.source_layer_uid == auto_ld.source_layer_uid]
        rules.sort(key=lambda r: r.priority, reverse=True)

        cols = level.width_cells
        rows = level.height_cells

        for gx, gy in cells:
            tile_id = self._evaluate_cell(gx, gy, cols, rows, source_li, rules)
            li.set_tile(gx, gy, cols, tile_id if tile_id >= 0 else -1)

    def _evaluate_cell(self, gx: int, gy: int, cols: int, rows: int,
                       source_li: LayerInstance, rules: list[AutoRuleDef]) -> int:
        """Find the first matching rule for a cell and return its output tile."""
        center_val = source_li.get_intgrid_value(gx, gy, cols)

        for rule in rules:
            if rule.source_values and center_val not in rule.source_values:
                continue

            variants = self._get_pattern_variants(rule)
            for pattern in variants:
                if self._pattern_matches(gx, gy, cols, rows, source_li, pattern):
                    return self._pick_output_tile(rule)

        return -1

    def _pattern_matches(self, gx: int, gy: int, cols: int, rows: int,
                         source_li: LayerInstance, pattern: list[RuleCell]) -> bool:
        """Check if a pattern matches at the given position."""
        for cell in pattern:
            nx = gx + cell.dx
            ny = gy + cell.dy
            if cell.requirement == RuleCellReq.ANY:
                continue
            if nx < 0 or nx >= cols or ny < 0 or ny >= rows:
                val = 0  # Out of bounds treated as empty
            else:
                val = source_li.get_intgrid_value(nx, ny, cols)
            if cell.requirement == RuleCellReq.MUST_MATCH:
                if val not in cell.values:
                    return False
            elif cell.requirement == RuleCellReq.MUST_NOT_MATCH:
                if val in cell.values:
                    return False
        return True

    def _pick_output_tile(self, rule: AutoRuleDef) -> int:
        """Pick an output tile, possibly weighted random."""
        if not rule.output_tiles:
            return -1
        if len(rule.output_tiles) == 1:
            return rule.output_tiles[0]
        if rule.output_weights and len(rule.output_weights) == len(rule.output_tiles):
            return random.choices(rule.output_tiles, weights=rule.output_weights, k=1)[0]
        return random.choice(rule.output_tiles)

    def _get_pattern_variants(self, rule: AutoRuleDef) -> list[list[RuleCell]]:
        """Generate rotated/mirrored pattern variants if allowed."""
        variants = [rule.pattern]
        if rule.allow_rotation:
            for _ in range(3):
                rotated = self._rotate_pattern_90(variants[-1])
                variants.append(rotated)
        if rule.allow_mirror:
            mirrored = []
            for pat in list(variants):
                mirrored.append(self._mirror_pattern_x(pat))
            variants.extend(mirrored)
        return variants

    @staticmethod
    def _rotate_pattern_90(pattern: list[RuleCell]) -> list[RuleCell]:
        """Rotate pattern 90 degrees clockwise."""
        return [
            RuleCell(dx=-c.dy, dy=c.dx, requirement=c.requirement, values=list(c.values))
            for c in pattern
        ]

    @staticmethod
    def _mirror_pattern_x(pattern: list[RuleCell]) -> list[RuleCell]:
        """Mirror pattern along X axis."""
        return [
            RuleCell(dx=-c.dx, dy=c.dy, requirement=c.requirement, values=list(c.values))
            for c in pattern
        ]
