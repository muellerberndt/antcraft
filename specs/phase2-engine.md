# Phase 2: Game Engine

## Goal

Build the core engine systems that make it feel like a real RTS. At the end of this phase, two players can scroll around a procedurally generated tile map, select and command multiple units with proper pathfinding, and gather food from the map — all synchronized over the network.

Still placeholder graphics (colored shapes), but the gameplay skeleton is real.

## Milestone Deliverable

- Procedurally generated tile map with terrain types (dirt, rock, water, food).
- Camera scrolling and a minimap.
- 5–10 ants per player, selectable via click and box-select.
- Right-click to move with A* pathfinding around obstacles.
- Worker ants can gather food and return it to the nest.
- Fog of war hides unexplored areas.
- All of the above synchronized in lockstep.

---

## 1. Tile Map

### Map Representation

```python
class TileMap:
    width: int   # in tiles
    height: int  # in tiles
    tiles: list[list[TileType]]  # 2D grid

class TileType(IntEnum):
    DIRT = 0       # walkable, buildable
    ROCK = 1       # impassable, not buildable
    WATER = 2      # impassable
    FOOD = 3       # walkable, contains harvestable food
```

- Map size: ~100x100 tiles for 1v1.
- Each tile stores its type and any resource amount (for FOOD tiles).
- Map is generated deterministically from a shared seed (agreed during connection handshake).

### Procedural Generation

- Use the shared PRNG to generate terrain.
- Mirror the map along the center axis for fairness (player 1's terrain is a mirror of player 2's).
- Guarantee each player has a valid starting location with nearby food.
- Rock/water clusters created via cellular automata or noise (using integer math).

## 2. Camera & Viewport

- The camera defines which portion of the map is visible.
- Scroll via edge-of-screen mouse detection, arrow keys, or minimap click.
- Camera position is **local only** — not part of the simulation state, not synced.

### Minimap

- Small overview of the full map in a corner of the screen.
- Shows terrain, unit positions (friendly as dots), fog of war.
- Click on minimap to jump camera to that location.

## 3. Entity System

Expand the Phase 1 entity to support multiple unit types and buildings.

```python
@dataclass
class Entity:
    entity_id: int
    entity_type: EntityType  # WORKER, SOLDIER, NEST, etc.
    player_id: int
    x: int          # milli-tiles
    y: int          # milli-tiles
    hp: int
    max_hp: int
    speed: int      # milli-tiles per tick
    state: EntityState  # IDLE, MOVING, GATHERING, ATTACKING, BUILDING
    # Movement
    path: list[tuple[int, int]]  # remaining waypoints
    # Gathering
    carrying: int   # food units being carried
    carry_capacity: int
```

### Entity Manager

- Entities stored in a flat list (or dict by ID) in GameState.
- Deterministic ID assignment: incrementing counter.
- Entity creation/destruction happens only during tick processing.

## 4. Pathfinding

### A* on Tile Grid

- Grid-based A* with 8-directional movement.
- Diagonal movement costs more (1414 vs 1000 in milli-tile units, approximating sqrt(2)).
- Impassable tiles (rock, water) are obstacles.
- Buildings are obstacles.
- Path is computed when a MOVE command is processed and stored on the entity.
- Each tick, the entity moves toward the next waypoint.

### Performance Considerations

- For Phase 2, simple A* is fine (100x100 grid, <20 units).
- If it becomes a bottleneck later, consider flow fields or hierarchical pathfinding.
- Pathfinding must be deterministic — same start/goal/map always produces same path.

## 5. Selection & Commands

### Selection

- **Click**: select a single unit (nearest to click within threshold).
- **Box select**: drag a rectangle to select all owned units within it.
- **Selection is local** — not part of simulation state.
- Only own units can be selected.

### New Command Types

| Command | Payload | Effect |
|---------|---------|--------|
| `MOVE` | unit_ids, target_x, target_y | Selected units pathfind to target |
| `STOP` | unit_ids | Selected units stop moving |
| `GATHER` | unit_ids, target_entity_id | Workers move to food and start harvesting |
| `BUILD` | unit_id, building_type, tile_x, tile_y | Worker moves to tile and builds |

## 6. Resource System

### Food Economy

- FOOD tiles contain a resource amount (integer).
- Worker ants move to a food tile, spend N ticks harvesting, fill their `carrying` amount.
- Workers return food to the Nest building, adding it to the player's stockpile.
- When a FOOD tile is depleted, it becomes DIRT.

```python
# In GameState
player_resources: dict[int, int]  # player_id → food amount
```

### Resource Display

- Show current food count in the HUD.
- Food tiles visually indicate remaining amount (color intensity or size).

## 7. Fog of War

- Each tile has a visibility state per player: **unexplored**, **fog** (previously seen), **visible**.
- A unit reveals tiles within its sight radius (e.g., 5 tiles).
- Visibility is recomputed each tick based on unit positions.
- Fog of war is part of simulation state (needed for game logic like targeting).
- Unexplored areas render as black. Fog areas show terrain but not enemy units.

---

## Work Split

### Dev A — Simulation Systems
- `src/simulation/map.py` — TileMap, procedural generation, terrain
- `src/simulation/pathfinding.py` — A* implementation
- `src/simulation/resources.py` — food economy, gathering logic
- `src/simulation/entities.py` — expanded entity system, entity states
- `src/simulation/tick.py` — update tick logic for new systems (movement along path, gathering, fog)
- `src/simulation/visibility.py` — fog of war computation
- Tests for pathfinding determinism, resource logic, visibility

### Dev B — Rendering & Input
- `src/rendering/renderer.py` — tile map rendering, entity rendering, fog overlay
- `src/rendering/camera.py` — viewport scrolling, screen↔world coordinate conversion
- `src/rendering/hud.py` — minimap, resource display, selection indicators
- `src/input/handler.py` — mouse/keyboard → commands (move, gather, build)
- `src/input/selection.py` — click and box selection logic
- Expand command types in `src/simulation/commands.py` (shared)
- Visual integration tests

### Integration Points

- **Map data** → rendering needs to draw tiles. Agree on TileMap interface.
- **Entity data** → rendering needs positions, types, states, health. Agree on Entity fields.
- **Camera** → input handler needs camera to convert screen coords to world coords.
- **Selection** → input creates commands referencing selected unit IDs.

### Merge Strategy

1. Dev A builds simulation systems with a simple test harness (print-based or headless).
2. Dev B builds rendering/input against mock data (hardcoded map, fake entities).
3. Integration PR wires real simulation data into the renderer.
4. Test: play a game where workers gather food while networked.

---

## Done Criteria

- [ ] Procedurally generated map renders with distinct terrain types.
- [ ] Camera scrolls smoothly, minimap works.
- [ ] Units can be selected (click + box) and commanded to move.
- [ ] A* pathfinding routes units around obstacles.
- [ ] Workers gather food and return it to nest, stockpile increases.
- [ ] Fog of war hides unseen areas, reveals around units.
- [ ] All above works in networked lockstep (two players, no desync).
- [ ] Tests pass for pathfinding, resource logic, map generation, visibility.
