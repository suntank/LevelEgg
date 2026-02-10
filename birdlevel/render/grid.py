"""Grid overlay rendering."""
from __future__ import annotations

import pygame

from birdlevel.render.camera import Camera


def draw_grid(
    surface: pygame.Surface,
    camera: Camera,
    grid_size: int,
    level_w: int,
    level_h: int,
    color: tuple[int, int, int, int] = (255, 255, 255, 30),
) -> None:
    """Draw grid lines for the level area within the viewport."""
    vr = camera.visible_world_rect()
    # Clamp to level bounds
    start_x = max(0, int(vr.x // grid_size) * grid_size)
    start_y = max(0, int(vr.y // grid_size) * grid_size)
    end_x = min(level_w, vr.x + vr.w + grid_size)
    end_y = min(level_h, vr.y + vr.h + grid_size)

    clip = surface.get_clip()
    surface.set_clip(camera.viewport)

    # Vertical lines
    x = start_x
    while x <= end_x:
        sx, sy1 = camera.world_to_screen(x, max(0, vr.y))
        _, sy2 = camera.world_to_screen(x, min(level_h, vr.y + vr.h))
        if camera.viewport.x <= sx <= camera.viewport.x + camera.viewport.w:
            pygame.draw.line(surface, color[:3], (int(sx), int(sy1)), (int(sx), int(sy2)), 1)
        x += grid_size

    # Horizontal lines
    y = start_y
    while y <= end_y:
        sx1, sy = camera.world_to_screen(max(0, vr.x), y)
        sx2, _ = camera.world_to_screen(min(level_w, vr.x + vr.w), y)
        if camera.viewport.y <= sy <= camera.viewport.y + camera.viewport.h:
            pygame.draw.line(surface, color[:3], (int(sx1), int(sy)), (int(sx2), int(sy)), 1)
        y += grid_size

    surface.set_clip(clip)


def draw_level_border(
    surface: pygame.Surface,
    camera: Camera,
    level_w: int,
    level_h: int,
    color: tuple[int, int, int] = (200, 200, 200),
) -> None:
    """Draw the level boundary rectangle."""
    sx1, sy1 = camera.world_to_screen(0, 0)
    sx2, sy2 = camera.world_to_screen(level_w, level_h)
    rect = pygame.Rect(int(sx1), int(sy1), int(sx2 - sx1), int(sy2 - sy1))
    clip = surface.get_clip()
    surface.set_clip(camera.viewport)
    pygame.draw.rect(surface, color, rect, 2)
    surface.set_clip(clip)
