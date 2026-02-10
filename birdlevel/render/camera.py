"""Camera system with pan and zoom for the editor canvas."""
from __future__ import annotations

import pygame


class Camera:
    """Handles world-to-screen and screen-to-world coordinate transforms."""

    def __init__(self, screen_w: int = 1920, screen_h: int = 1080):
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self.zoom: float = 1.0
        self.min_zoom: float = 0.1
        self.max_zoom: float = 10.0
        self.screen_w = screen_w
        self.screen_h = screen_h
        # Viewport rect in screen space (excludes UI panels)
        self.viewport = pygame.Rect(0, 0, screen_w, screen_h)

    def set_viewport(self, x: int, y: int, w: int, h: int) -> None:
        self.viewport = pygame.Rect(x, y, w, h)

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        sx = (wx + self.offset_x) * self.zoom + self.viewport.x + self.viewport.w / 2
        sy = (wy + self.offset_y) * self.zoom + self.viewport.y + self.viewport.h / 2
        return sx, sy

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        wx = (sx - self.viewport.x - self.viewport.w / 2) / self.zoom - self.offset_x
        wy = (sy - self.viewport.y - self.viewport.h / 2) / self.zoom - self.offset_y
        return wx, wy

    def world_to_grid(self, wx: float, wy: float, grid_size: int) -> tuple[int, int]:
        gx = int(wx // grid_size) if wx >= 0 else int(wx // grid_size)
        gy = int(wy // grid_size) if wy >= 0 else int(wy // grid_size)
        return gx, gy

    def screen_to_grid(self, sx: float, sy: float, grid_size: int) -> tuple[int, int]:
        wx, wy = self.screen_to_world(sx, sy)
        return self.world_to_grid(wx, wy, grid_size)

    def pan(self, dx: float, dy: float) -> None:
        self.offset_x += dx / self.zoom
        self.offset_y += dy / self.zoom

    def zoom_at(self, screen_x: float, screen_y: float, factor: float) -> None:
        """Zoom centered on a screen point."""
        old_wx, old_wy = self.screen_to_world(screen_x, screen_y)
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        new_wx, new_wy = self.screen_to_world(screen_x, screen_y)
        self.offset_x += new_wx - old_wx
        self.offset_y += new_wy - old_wy

    def center_on(self, wx: float, wy: float) -> None:
        """Center the camera on a world position."""
        self.offset_x = -wx
        self.offset_y = -wy

    def visible_world_rect(self) -> pygame.Rect:
        """Return the world-space rectangle visible on screen."""
        tl_x, tl_y = self.screen_to_world(self.viewport.x, self.viewport.y)
        br_x, br_y = self.screen_to_world(
            self.viewport.x + self.viewport.w, self.viewport.y + self.viewport.h
        )
        w = br_x - tl_x
        h = br_y - tl_y
        return pygame.Rect(int(tl_x), int(tl_y), int(w), int(h))
