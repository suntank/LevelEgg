# BirdLevel - Game Bird Level Editor

A desktop 2D level editor for the Game Bird console (Raspberry Pi Zero 2W), inspired by LDtk. Built with Python and Pygame-CE. Supports tilemap workflows, layered editing, entity placement, IntGrid authoring, rule-based auto-tiling, and robust export pipelines.

## Requirements

- Python 3.11+
- pygame-ce >= 2.4.1
- Pillow >= 10.0.0
- watchdog >= 3.0.0 (optional, for live asset reload)

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
# New project (opens with default sample project)
python -m birdlevel

# Open existing project
python -m birdlevel path/to/project.birdlevel
```

## Features

- **LDtk-style project structure** — Definitions (tilesets, layers, entities) separated from per-level instances
- **World + levels** — Multiple worlds, multiple levels per world
- **Layer system** — IntGrid, Tile, Entity, and Auto layers
- **IntGrid tools** — Brush, eraser, rectangle fill, flood fill with value palette
- **Tile painting tools** — Brush, rectangle, stamp, random, eyedropper
- **Entity system** — Typed fields (int, float, string, bool, color, enum), singleton/grid-lock constraints
- **Auto-layer rules** — Rule-based auto-tiling from IntGrid patterns with rotation/mirror support
- **Tileset management** — Import PNG tilesets, auto-slicing, tile picker panel
- **Export pipeline** — Full JSON, per-layer PNGs, composite PNG, entities JSON, IntGrid CSV/PNG
- **Autosave & crash recovery** — Periodic backups with restore prompt on startup
- **Undo/Redo** — Command pattern with 200-step history
- **File dialogs** — Open, Save, Save As via tkinter
- **Custom UI** — Dark-themed panels, layer tree, tool palette, tile picker, property inspector

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| **Ctrl+O** | Open project |
| **Ctrl+S** | Save project |
| **Ctrl+Shift+S** | Save As |
| **Ctrl+E** | Export |
| **Ctrl+Z** | Undo |
| **Ctrl+Y** / **Ctrl+Shift+Z** | Redo |
| **1** | Switch to IntGrid tools |
| **2** | Switch to Tile tools |
| **3** | Switch to Entity tools |
| **G** | Toggle grid overlay |
| **R** | Toggle random tile mode |
| **Tab** | Collapse/expand side panels |

## Mouse Controls

- **Left click** — Paint / place / select (active tool)
- **Middle mouse drag** — Pan canvas
- **Mouse wheel** — Zoom (cursor-centric)

## Project Structure

```
birdlevel/
├── app/              # Main application loop, input handling
│   └── ui/           # Custom Pygame UI toolkit (panels, widgets, theme)
├── assets/           # Tileset loader, sample tileset generator
├── editor/           # Editor state, command stack
│   └── tools/        # IntGrid, tile, and entity editing tools
├── export/           # JSON export, super simple export (PNG/CSV)
├── project/          # Data models, serialization, migrations
├── render/           # Camera, grid overlay, layer renderer
├── rules/            # Auto-layer rule solver
└── util/             # File dialogs, backup/recovery, path utilities
```

## Export Formats

### Full JSON Export
Complete project data in a single `.json` file, suitable for custom game engines.

### Super Simple Export
Per-level output directory containing:
- `{layer}_tiles.png` — Rendered tile layers
- `{layer}_intgrid.csv` — IntGrid data as CSV
- `{layer}_intgrid.png` — IntGrid visualization
- `{layer}_entities.json` — Entity instances with fields
- `composite.png` — All visible layers composited
# LevelEgg
