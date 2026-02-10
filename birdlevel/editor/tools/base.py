"""Base tool interface and tool manager."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from birdlevel.editor.editor_state import EditorState


class ToolCategory(Enum):
    INTGRID = auto()
    TILES = auto()
    ENTITIES = auto()


class ToolType(Enum):
    INTGRID_BRUSH = auto()
    INTGRID_ERASER = auto()
    INTGRID_RECT_FILL = auto()
    INTGRID_FLOOD_FILL = auto()
    TILE_BRUSH = auto()
    TILE_RECT = auto()
    TILE_STAMP = auto()
    TILE_RANDOM = auto()
    TILE_FLOOD_FILL = auto()
    TILE_EYEDROPPER = auto()
    ENTITY_PLACE = auto()
    ENTITY_SELECT = auto()


class Tool(ABC):
    """Base class for all editor tools."""

    def __init__(self, tool_type: ToolType, category: ToolCategory):
        self.tool_type = tool_type
        self.category = category
        self.active = False

    @abstractmethod
    def on_press(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        ...

    @abstractmethod
    def on_drag(self, state: EditorState, wx: float, wy: float) -> None:
        ...

    @abstractmethod
    def on_release(self, state: EditorState, wx: float, wy: float, button: int) -> None:
        ...

    def on_hover(self, state: EditorState, wx: float, wy: float) -> None:
        pass

    def draw_overlay(self, surface: pygame.Surface, state: EditorState) -> None:
        """Draw tool-specific overlays (cursor highlight, selection preview, etc)."""
        pass

    @property
    def name(self) -> str:
        return self.tool_type.name.replace("_", " ").title()


class ToolManager:
    """Manages the set of available tools and the active tool."""

    def __init__(self):
        self.tools: dict[ToolType, Tool] = {}
        self.active_tool: Tool | None = None
        self.active_category: ToolCategory = ToolCategory.INTGRID

    def register(self, tool: Tool) -> None:
        self.tools[tool.tool_type] = tool

    def set_active(self, tool_type: ToolType) -> None:
        if tool_type in self.tools:
            if self.active_tool:
                self.active_tool.active = False
            self.active_tool = self.tools[tool_type]
            self.active_tool.active = True
            self.active_category = self.active_tool.category

    def set_category(self, category: ToolCategory) -> None:
        """Switch to the default tool for a category."""
        self.active_category = category
        defaults = {
            ToolCategory.INTGRID: ToolType.INTGRID_BRUSH,
            ToolCategory.TILES: ToolType.TILE_BRUSH,
            ToolCategory.ENTITIES: ToolType.ENTITY_SELECT,
        }
        default = defaults.get(category)
        if default and default in self.tools:
            self.set_active(default)

    def get_tools_for_category(self, category: ToolCategory) -> list[Tool]:
        return [t for t in self.tools.values() if t.category == category]
