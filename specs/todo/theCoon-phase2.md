# Phase 2 — theCoon (Rendering & Input)

All rendering, camera, HUD, and input systems. This code depends on PyGame and the simulation interfaces. Work against mock/stub data until Ben's simulation is ready to integrate.

**Branch:** `phase2-rendering`

---

## Shared Setup (do first, coordinate with Ben)

Before either dev starts, agree on and commit these shared interface changes together (or have one person do it in a `phase2-interfaces` PR that both branch from):

- [ ] **Expand Entity dataclass** in `src/simulation/state.py`
  - Add fields: `entity_type: EntityType`, `hp: int`, `max_hp: int`, `state: EntityState`, `path: list[tuple[int, int]]`, `carrying: int`, `carry_capacity: int`
  - Add `EntityType` enum: `WORKER = 0, SOLDIER = 1, NEST = 2`
  - Add `EntityState` enum: `IDLE = 0, MOVING = 1, GATHERING = 2, ATTACKING = 3, BUILDING = 4`

- [ ] **Expand CommandType** in `src/simulation/commands.py`
  - Add: `GATHER = 3`, `BUILD = 4`
  - Add `target_entity_id: int = 0` field to Command
  - Update serialization in `serialization.py`

- [ ] **Add new config constants** in `src/config.py`
  - `MAP_WIDTH_TILES = 100`, `MAP_HEIGHT_TILES = 100`
  - Camera/scroll speed constants: `CAMERA_SCROLL_SPEED = 10`, `CAMERA_EDGE_SCROLL_MARGIN = 20`
  - `MINIMAP_SIZE = 200` (pixels)
  - `SELECTION_THRESHOLD = 15` (pixels, click selection radius)

---

## Task 1: Camera & Viewport

**File:** `src/rendering/camera.py`
**Tests:** `tests/test_rendering/test_camera.py`

- [ ] Implement `Camera` class:
  - `x: int`, `y: int` — top-left corner in milli-tiles
  - `width: int`, `height: int` — viewport size in pixels
  - `tile_size: int` — pixels per tile
  - `move(dx, dy)` — shift camera, clamp to map bounds
  - `screen_to_world(screen_x, screen_y) -> (milli_tile_x, milli_tile_y)`
  - `world_to_screen(milli_tile_x, milli_tile_y) -> (screen_x, screen_y)`
  - `get_visible_tile_range() -> (min_tile_x, min_tile_y, max_tile_x, max_tile_y)`
- [ ] Scrolling triggers:
  - Arrow keys (held down = continuous scroll)
  - Mouse at screen edge (within `CAMERA_EDGE_SCROLL_MARGIN` pixels)
  - Minimap click (jump to location)
- [ ] Camera is **local only** — never sent over the network, not part of GameState
- [ ] Tests:
  - `screen_to_world` / `world_to_screen` roundtrip
  - Camera clamps to map bounds
  - `get_visible_tile_range` returns correct tile rectangle

## Task 2: Tile Map Rendering

**File:** `src/rendering/renderer.py` (extend existing)

- [ ] Render visible tiles based on camera viewport:
  - Only draw tiles within `camera.get_visible_tile_range()` (culling)
  - Tile colors: DIRT=brown, ROCK=gray, WATER=blue, FOOD=green
  - FOOD tiles: vary green intensity based on remaining food amount
- [ ] Use the `TileMap` interface Ben provides: `tilemap.get_tile(x, y)`, `tilemap.get_food(x, y)`
- [ ] **For development before Ben's code is ready:** create a simple `MockTileMap` with hardcoded terrain to develop against (e.g., mostly DIRT with some ROCK walls and FOOD patches)
- [ ] Grid lines optional (toggle with debug key?)

## Task 3: Entity Rendering (expanded)

**File:** `src/rendering/renderer.py` (extend existing)

- [ ] Draw entities relative to camera position (use `camera.world_to_screen()`)
  - Workers: small colored circles (existing, adapt for camera offset)
  - Nest: larger colored square or circle
  - Color by `player_id` (red/blue from config)
- [ ] Entity state indicators:
  - GATHERING: small food icon or color tint
  - MOVING: direction indicator or trail
  - Carrying food: small dot above entity
- [ ] Health bars above damaged units (only show if `hp < max_hp`)
- [ ] Selected unit highlight (bright outline/ring) — reads from selection state (Task 5)
- [ ] Interpolation: keep existing interpolation logic, adapt for camera coords

## Task 4: Fog of War Rendering

**File:** `src/rendering/renderer.py` (extend existing)

- [ ] After drawing tiles and entities, overlay fog of war:
  - UNEXPLORED: black overlay (fully opaque)
  - FOG: dark semi-transparent overlay (terrain visible, units hidden)
  - VISIBLE: no overlay
- [ ] Use Ben's `VisibilityMap` interface: `visibility.get_visibility(player_id, x, y)`
- [ ] **For development before Ben's code:** assume all tiles VISIBLE (no-op overlay), or create a simple mock that reveals a circle around the center
- [ ] Enemy entities in FOG tiles should not be drawn
- [ ] Only draw tiles within camera viewport (same culling as tile rendering)

## Task 5: Selection System

**File:** `src/input/selection.py`
**Tests:** `tests/test_input/test_selection.py`

- [ ] Implement `SelectionManager` class:
  - `selected_ids: set[int]` — currently selected entity IDs
  - `select_at(world_x, world_y, entities, player_id)` — click select nearest own unit within threshold
  - `select_in_rect(x1, y1, x2, y2, entities, player_id)` — box select all own units in rectangle (world coords)
  - `clear()`
- [ ] Box selection drag:
  - Track `drag_start` on left mouse button down
  - On mouse button up: if drag distance > threshold → box select, else → click select
  - Draw selection rectangle while dragging (green translucent rect)
- [ ] Selection is **local only** — not synced, not in GameState
- [ ] Only own units can be selected (filter by `player_id`)
- [ ] Tests:
  - Click selects nearest unit within threshold
  - Click on empty area clears selection
  - Box select selects all owned units in rectangle
  - Cannot select enemy units

## Task 6: Input Handler (expanded)

**File:** `src/input/handler.py` (rewrite/expand)

- [ ] Integrate with Camera for coordinate conversion:
  - All mouse clicks → `camera.screen_to_world()` → milli-tile coords
- [ ] Left click/drag: selection (delegate to SelectionManager)
- [ ] Right click: context-sensitive command
  - If clicking on a FOOD tile and workers are selected → GATHER command
  - Otherwise → MOVE command for selected units
  - (BUILD command can be deferred or stubbed)
- [ ] Keyboard:
  - S key: STOP command for selected units
  - Arrow keys / edge scroll: camera movement (delegate to Camera)
  - ESC: deselect all (or quit if nothing selected)
- [ ] All commands still use `tick = current_tick + INPUT_DELAY_TICKS`
- [ ] Update command creation to use selected entity IDs from SelectionManager

## Task 7: HUD & Minimap

**File:** `src/rendering/hud.py`
**Tests:** minimal (mostly visual)

- [ ] **Minimap** (bottom-right or bottom-left corner):
  - Render full map at tiny scale (`MAP_WIDTH_TILES` pixels wide or smaller)
  - Terrain colors (simplified: brown/gray/blue/green dots)
  - Friendly unit dots (player color)
  - White rectangle showing current camera viewport
  - Click on minimap → set camera position
  - Fog of war overlay on minimap
- [ ] **Resource display** (top of screen):
  - Show food icon + `player_resources[player_id]` count
- [ ] **Selection info** (bottom of screen, optional):
  - Number of selected units
  - Unit type if single selection
- [ ] **Debug overlay** (existing, expand):
  - Keep tick, FPS, player, connection status
  - Add: camera position, selected count

---

## Development Strategy (working without Ben's code)

Create a `tests/mocks/mock_simulation.py` with:

```python
# Stub TileMap for rendering development
class MockTileMap:
    def __init__(self, width=100, height=100):
        self.width = width
        self.height = height
        # Mostly dirt, some rock walls, food patches

    def get_tile(self, x, y) -> int: ...
    def get_food(self, x, y) -> int: ...
    def is_walkable(self, x, y) -> bool: ...

# Stub VisibilityMap
class MockVisibilityMap:
    def get_visibility(self, player_id, x, y) -> int:
        return 2  # everything visible
```

This lets you build and test all rendering code immediately. When Ben's real implementations land, swap out the mocks.

---

## Integration Notes

- Ben's simulation code provides: `GameState.tilemap`, `GameState.player_resources`, `Entity.*` fields, `VisibilityMap`
- Your Camera, SelectionManager, and HUD are local-only (no sync needed)
- Your InputHandler produces Commands that feed into the existing lockstep loop in `game.py`
- The `Game` class will need updating to wire Camera + SelectionManager into the loop — this is the integration PR
- Run `python -m pytest tests/` before every commit
- The existing `game.py` `_update_playing()` and `_render()` methods will need refactoring to pass Camera around — plan for this in the integration step
