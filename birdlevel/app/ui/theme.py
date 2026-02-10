"""UI theme constants and color palette."""
from __future__ import annotations


class Theme:
    """Central color and dimension constants for the editor UI."""

    # Background colors
    BG_DARK = (30, 30, 38)
    BG_PANEL = (40, 42, 54)
    BG_HEADER = (50, 52, 66)
    BG_INPUT = (55, 58, 72)
    BG_CANVAS = (25, 25, 35)
    BG_HOVER = (60, 65, 82)
    BG_SELECTED = (80, 90, 130)
    BG_BUTTON = (60, 63, 78)
    BG_BUTTON_HOVER = (75, 80, 100)
    BG_BUTTON_ACTIVE = (90, 100, 140)

    # Text colors
    TEXT = (220, 220, 230)
    TEXT_DIM = (140, 140, 160)
    TEXT_BRIGHT = (255, 255, 255)
    TEXT_ACCENT = (130, 170, 255)
    TEXT_WARNING = (255, 200, 80)
    TEXT_ERROR = (255, 100, 100)
    TEXT_SUCCESS = (100, 220, 120)

    # Accent colors
    ACCENT = (100, 140, 255)
    ACCENT_HOVER = (130, 165, 255)
    ACCENT_DIM = (70, 100, 180)

    # Border colors
    BORDER = (65, 68, 85)
    BORDER_LIGHT = (80, 85, 105)
    BORDER_FOCUS = (100, 140, 255)

    # Layer type indicator colors
    LAYER_INTGRID = (80, 130, 220)
    LAYER_TILES = (180, 140, 60)
    LAYER_ENTITY = (200, 100, 120)
    LAYER_AUTO = (100, 200, 150)

    # Dimensions
    TOP_BAR_HEIGHT = 36
    BOTTOM_BAR_HEIGHT = 28
    LEFT_PANEL_WIDTH = 240
    RIGHT_PANEL_WIDTH = 280
    PANEL_PADDING = 8
    ITEM_HEIGHT = 26
    BUTTON_HEIGHT = 28
    FONT_SIZE = 14
    FONT_SIZE_SMALL = 12
    FONT_SIZE_HEADER = 16
    SCROLLBAR_WIDTH = 8
    ICON_SIZE = 16

    # Scroll
    SCROLL_SPEED = 20
