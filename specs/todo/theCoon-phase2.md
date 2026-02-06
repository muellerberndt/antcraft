# Phase 2 — theCoon (Rendering & Input)

All rendering, camera, HUD, and input systems. This code depends on PyGame and the simulation interfaces. Work against mock/stub data until Ben's simulation is ready to integrate.

**Branch:** `phase2-rendering`

**Reference:** [game_mechanics.md](../game_mechanics.md), [balance.md](../balance.md)

---

## Shared Setup — DONE

The shared interfaces PR has been merged. The following are already in place:

- [x] `EntityType`: ANT, QUEEN, HIVE, HIVE_SITE, CORPSE, APHID, BEETLE, MANTIS
- [x] `EntityState`: IDLE, MOVING, ATTACKING, HARVESTING, FOUNDING
- [x] `CommandType`: MOVE, STOP, HARVEST, SPAWN_ANT, MERGE_QUEEN, FOUND_HIVE
- [x] `Command.target_entity_id` field added, serialization updated
- [x] Config: CAMERA_SCROLL_SPEED, CAMERA_EDGE_SCROLL_MARGIN, MINIMAP_SIZE, SELECTION_THRESHOLD
- [x] Config: all balance parameters from balance.md

---

## Task 1: Camera & Viewport — DONE

**File:** `src/rendering/camera.py`, `tests/test_rendering/test_camera.py`

- [x] `Camera` class with `screen_to_world`, `world_to_screen`, `move` (clamped), `get_visible_tile_range`, `center_on`, `handle_key_scroll`, `handle_edge_scroll`
- [x] 23 unit tests passing (roundtrip within ±1 pixel tolerance due to integer division)
- [x] Arrow key + WASD scrolling wired into `game.py` via simpler pixel-offset approach (Ben's camera code)
- [x] Camera is local only

**Note:** `game.py` uses a direct pixel-offset camera (`_camera_x`, `_camera_y`) rather than the Camera class. The Camera class exists for future use/integration.

## Task 2: Tile Map Rendering — DONE

**File:** `src/rendering/renderer.py`

- [x] Pre-rendered map surface via `_build_map_surface()` — full tilemap baked to a `pygame.Surface`
- [x] Camera viewport blitting with `_draw_tiles(camera_x, camera_y)`
- [x] Tile colors: DIRT=brown with per-tile variation, ROCK=gray with variation
- [x] Subtle edge shading (bottom/right) for depth
- [x] Uses Ben's `TileMap` and `generate_map(seed, w, h)` from `src/simulation/tilemap.py`

## Task 3: Entity Rendering — DONE

**File:** `src/rendering/renderer.py`

- [x] Per-entity-type sprite drawing with pygame primitives:
  - **ANT**: segmented body (abdomen oval + thorax + head), 3 leg pairs, antennae, player-colored
  - **QUEEN**: larger ant body with gold crown (3 spikes), player-colored
  - **HIVE**: player-colored hexagon with inner honeycomb hex
  - **HIVE_SITE**: gray outline hexagon
  - **CORPSE**: small body oval with splayed legs, fades with decay
  - **APHID**: plump green oval with head and antennae
  - **BEETLE**: brown shell with split line, dark head with pincers, 3 leg pairs
  - **MANTIS**: green elongated body, triangular head with yellow eyes, bent raptorial arms
- [x] Entity state indicators:
  - ATTACKING: red flash ring
  - HARVESTING: yellow jelly dot on carrying ants
- [x] Health bars above damaged units (`hp < max_hp`)
- [x] Target indicator line for moving units
- [x] Position interpolation between ticks
- [x] Off-screen culling with 20px margin
- [ ] Selected unit highlight — pending Task 5 (Selection System)
- [ ] FOUNDING animation — pending simulation support

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
- [ ] Selectable types: ANT, QUEEN (not hives, wildlife, corpses)
- [ ] Tests:
  - Click selects nearest unit within threshold
  - Click on empty area clears selection
  - Box select selects all owned units in rectangle
  - Cannot select enemy units
  - Cannot select hives/corpses/wildlife

## Task 6: Input Handler (expanded)

**File:** `src/input/handler.py` (rewrite/expand)

- [ ] Integrate with Camera for coordinate conversion:
  - All mouse clicks → `camera.screen_to_world()` → milli-tile coords
- [ ] Left click/drag: selection (delegate to SelectionManager)
- [ ] Right click: context-sensitive command
  - If clicking on a CORPSE entity and ants are selected → HARVEST command (target_entity_id = corpse ID)
  - If clicking on a HIVE_SITE and a QUEEN is selected → FOUND_HIVE command
  - Otherwise → MOVE command for selected units
- [ ] Keyboard:
  - S key: STOP command for selected units
  - Q key (at hive): SPAWN_ANT command (target_entity_id = hive)
  - M key (at hive with ants selected): MERGE_QUEEN command
  - Arrow keys / edge scroll: camera movement (delegate to Camera)
  - ESC: deselect all (or quit if nothing selected)
- [ ] All commands still use `tick = current_tick + INPUT_DELAY_TICKS`
- [ ] Update command creation to use selected entity IDs from SelectionManager

## Task 7: HUD & Minimap

**File:** `src/rendering/hud.py`
**Tests:** minimal (mostly visual)

- [ ] **Minimap** (bottom-right or bottom-left corner):
  - Render full map at tiny scale (`MAP_WIDTH_TILES` pixels wide or smaller)
  - Terrain colors (simplified: brown/gray/blue dots)
  - Friendly unit dots (player color)
  - Enemy unit dots (if visible, not in fog)
  - Hive icons for all known hives
  - Hive site markers (neutral)
  - White rectangle showing current camera viewport
  - Click on minimap → set camera position
  - Fog of war overlay on minimap
- [ ] **Resource display** (top of screen):
  - Show jelly icon + `player_jelly[player_id]` count
  - Show ant count for current player
- [ ] **Selection info** (bottom of screen, optional):
  - Number of selected units
  - HP bars if single selection
  - Unit type (ant/queen) if single selection
- [ ] **Debug overlay** (existing, expand):
  - Keep tick, FPS, player, connection status
  - Add: camera position, selected count, jelly amount

---

## Development Strategy (working without Ben's code)

Create a `tests/mocks/mock_simulation.py` with:

```python
# Stub TileMap for rendering development
class MockTileMap:
    def __init__(self, width=100, height=100):
        self.width = width
        self.height = height
        # Mostly DIRT, some ROCK walls, WATER features

    def get_tile(self, x, y) -> int: ...
    def is_walkable(self, x, y) -> bool: ...

# Stub VisibilityMap
class MockVisibilityMap:
    def get_visibility(self, player_id, x, y) -> int:
        return 2  # everything visible
```

This lets you build and test all rendering code immediately. When Ben's real implementations land, swap out the mocks.

---

## Integration Notes

- Ben's simulation code provides: `GameState.tilemap`, `GameState.player_jelly`, `Entity.*` fields, `VisibilityMap`
- Your Camera, SelectionManager, and HUD are local-only (no sync needed)
- Your InputHandler produces Commands that feed into the existing lockstep loop in `game.py`
- The `Game` class will need updating to wire Camera + SelectionManager into the loop — this is the integration PR
- Run `python -m pytest tests/` before every commit
- The existing `game.py` `_update_playing()` and `_render()` methods will need refactoring to pass Camera around — plan for this in the integration step
