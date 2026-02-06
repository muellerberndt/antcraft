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
- [x] Selected unit highlight (green circle) — implemented in Task 5
- [ ] FOUNDING animation — pending simulation support

## Task 4: Fog of War Rendering — DONE

**Files:** `src/simulation/visibility.py`, `src/rendering/renderer.py`, `tests/test_simulation/test_visibility.py`

- [x] `VisibilityMap` class: per-player 2D tile grid with UNEXPLORED/FOG/VISIBLE states
- [x] `update()` recomputes visibility each tick: demotes VISIBLE→FOG, reveals tiles within entity sight radius using integer Euclidean distance (`dx*dx + dy*dy <= radius*radius`)
- [x] Per-entity sight radius: ANT=5, QUEEN=7, HIVE=16 tiles (wildlife/neutrals=0)
- [x] Fog overlay rendering via pre-allocated SRCALPHA surface: UNEXPLORED=black, FOG=semi-transparent dark, VISIBLE=no overlay
- [x] Enemy/neutral entities hidden in non-VISIBLE tiles
- [x] Fog overlay only drawn for tiles within camera viewport
- [x] Visibility wired into GameState, updated at end of each `advance_tick()`, included in `compute_hash()`
- [x] Initial visibility computed after entity placement (tick 0)
- [x] 14 unit tests: reveal, fog transitions, per-player isolation, euclidean distance, edge cases

## Task 5: Selection System — DONE

**Files:** `src/input/selection.py`, `src/input/handler.py`, `src/rendering/renderer.py`, `tests/test_input/test_selection.py`

- [x] `SelectionManager` class with `selected_ids: set[int]`, `select_at()`, `select_in_rect()`, `clear()`
- [x] Click select: nearest own selectable unit within threshold (milli-tile distance)
- [x] Box select: drag rectangle selects all own selectable units in world-coord rect
- [x] Drag tracking in InputHandler: left mouse down starts drag, motion updates, mouse up triggers box or click select based on threshold
- [x] Green translucent drag rectangle rendered while dragging
- [x] Green selection highlight circle around selected entities
- [x] Selection is **local only** — not synced, not in GameState
- [x] Only own ANT and QUEEN can be selected (enemies, hives, wildlife, corpses excluded)
- [x] Right click issues MOVE command for selected units
- [x] S key issues STOP command for selected units
- [x] Selected unit count shown in debug overlay
- [x] 15 unit tests: click select, closest selection, empty click clears, enemy exclusion, hive/corpse/wildlife exclusion, queen selectable, box select, rect order invariance, box excludes enemies/non-selectable

## Task 6: Input Handler (expanded)

**File:** `src/input/handler.py` (rewrite/expand)

Already done in Task 5:
- [x] Screen-to-world coordinate conversion (`_screen_to_world` in InputHandler)
- [x] Left click/drag: selection (delegate to SelectionManager)
- [x] Right click: MOVE command for selected units
- [x] S key: STOP command for selected units
- [x] All commands use `tick = current_tick + INPUT_DELAY_TICKS`
- [x] Command creation uses selected entity IDs from SelectionManager


## Task 7: HUD & Minimap — DONE

**Files:** `src/rendering/hud.py`, `src/rendering/renderer.py`, `src/game.py`

- [x] **Minimap** (bottom-right corner, 200x200px):
  - Pre-rendered terrain surface (brown=dirt, gray=rock, 2px per tile)
  - Fog of war overlay (UNEXPLORED=dark, FOG=semi-transparent)
  - Friendly unit dots (player color), enemy dots (only if VISIBLE)
  - Hive icons (larger colored squares), hive site markers (gray)
  - Wildlife dots (yellow-green, only if VISIBLE)
  - White rectangle showing current camera viewport
  - Click on minimap jumps camera to that position (consumed before input handler)
  - 1px dark border
- [x] **Resource display** (top-right corner):
  - Jelly count (gold text) + ant count (white text)
  - Semi-transparent dark background bar
- [x] **Selection info** (bottom-left):
  - Shows "N Ants selected" / "N Queens selected" with background
  - HP bar for single unit selection
- [x] **Debug overlay** (top-left, moved from renderer to HUD):
  - Tick, Player, Jelly, Ants, FPS, Connected, Selected count
- [x] HUD class owns all fonts and overlay rendering
- [x] Wired into renderer draw pipeline (after fog, before flip)

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
