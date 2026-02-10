"""Generate a sample tileset image for testing the editor."""
from __future__ import annotations

import os

import pygame


def generate_sample_tileset(output_path: str, tile_size: int = 16,
                             cols: int = 8, rows: int = 8) -> str:
    """Create a simple procedural tileset PNG for testing.

    Generates colored tiles with varied patterns:
    - Row 0: solid ground tones
    - Row 1: wall/brick patterns
    - Row 2: grass/nature tones
    - Row 3: water/ice tones
    - Row 4: lava/hazard tones
    - Row 5: metal/tech tones
    - Row 6: decorative patterns
    - Row 7: special tiles (start, end, key, door, etc.)
    """
    w = cols * tile_size
    h = rows * tile_size
    surface = pygame.Surface((w, h), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))

    palettes = [
        # Row 0: ground
        [(120, 90, 60), (140, 105, 70), (100, 75, 50), (130, 100, 65),
         (110, 85, 55), (150, 115, 80), (90, 70, 45), (135, 100, 68)],
        # Row 1: walls/bricks
        [(160, 80, 70), (170, 90, 78), (150, 72, 62), (180, 95, 82),
         (140, 68, 58), (165, 85, 74), (175, 92, 80), (155, 76, 66)],
        # Row 2: grass/nature
        [(60, 140, 60), (70, 155, 65), (55, 130, 55), (80, 160, 70),
         (50, 120, 48), (75, 150, 62), (65, 145, 58), (85, 165, 75)],
        # Row 3: water/ice
        [(50, 100, 180), (60, 115, 195), (45, 90, 165), (70, 125, 200),
         (55, 105, 185), (65, 120, 190), (40, 85, 160), (75, 130, 205)],
        # Row 4: lava/hazard
        [(220, 80, 30), (240, 100, 40), (200, 60, 20), (230, 90, 35),
         (210, 70, 25), (250, 110, 45), (195, 55, 18), (235, 95, 38)],
        # Row 5: metal/tech
        [(130, 135, 140), (145, 150, 155), (120, 125, 130), (155, 160, 165),
         (110, 115, 120), (140, 145, 150), (150, 155, 160), (125, 130, 135)],
        # Row 6: decorative
        [(180, 140, 200), (160, 200, 180), (200, 180, 140), (140, 180, 200),
         (200, 160, 180), (180, 200, 160), (170, 170, 200), (200, 170, 170)],
        # Row 7: special
        [(255, 220, 50), (50, 220, 255), (255, 50, 220), (50, 255, 50),
         (255, 150, 50), (150, 50, 255), (255, 255, 150), (150, 255, 255)],
    ]

    for row in range(rows):
        palette = palettes[row % len(palettes)]
        for col in range(cols):
            base_color = palette[col % len(palette)]
            tx = col * tile_size
            ty = row * tile_size

            # Base fill
            pygame.draw.rect(surface, base_color, (tx, ty, tile_size, tile_size))

            # Add patterns based on row
            if row == 1:
                # Brick pattern
                mid = tile_size // 2
                line_color = tuple(max(0, c - 30) for c in base_color)
                pygame.draw.line(surface, line_color, (tx, ty + mid), (tx + tile_size, ty + mid), 1)
                if col % 2 == 0:
                    pygame.draw.line(surface, line_color, (tx + mid, ty), (tx + mid, ty + mid), 1)
                else:
                    pygame.draw.line(surface, line_color, (tx + mid, ty + mid), (tx + mid, ty + tile_size), 1)
            elif row == 2:
                # Grass tufts
                highlight = tuple(min(255, c + 40) for c in base_color)
                for i in range(3):
                    gx = tx + 3 + i * 5
                    gy = ty + tile_size - 4 - (i % 2) * 3
                    pygame.draw.line(surface, highlight, (gx, gy), (gx, gy - 4), 1)
            elif row == 3:
                # Water ripple
                highlight = tuple(min(255, c + 25) for c in base_color)
                wy = ty + tile_size // 3
                pygame.draw.line(surface, highlight, (tx + 2, wy), (tx + tile_size - 2, wy), 1)
            elif row == 7:
                # Special: draw a small icon shape
                cx = tx + tile_size // 2
                cy = ty + tile_size // 2
                r = tile_size // 4
                pygame.draw.circle(surface, (255, 255, 255), (cx, cy), r, 1)

            # Subtle edge shading
            shadow = tuple(max(0, c - 20) for c in base_color)
            pygame.draw.line(surface, shadow, (tx + tile_size - 1, ty), (tx + tile_size - 1, ty + tile_size - 1), 1)
            pygame.draw.line(surface, shadow, (tx, ty + tile_size - 1), (tx + tile_size - 1, ty + tile_size - 1), 1)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    pygame.image.save(surface, output_path)
    return output_path


if __name__ == "__main__":
    pygame.init()
    # Need a display for Surface operations
    pygame.display.set_mode((1, 1))
    path = generate_sample_tileset("sample_tileset.png")
    print(f"Generated: {path}")
    pygame.quit()
