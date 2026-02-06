# Phase 3: Units, Buildings & Tech Tree

## Goal

Design and implement the actual game content — what makes AntCraft a game, not just a tech demo. By the end of this phase, a real match is playable: build up your colony, produce units, tech up, and fight.

## Milestone Deliverable

- Full unit roster (4–5 ant types) with distinct roles.
- Building set with construction mechanics.
- Tech tree with meaningful upgrade choices.
- Combat system with attack, damage, and unit death.
- A winnable/loseable game (destroy the enemy nest).

---

## 1. Ant Unit Types

All values are initial balance targets — expect heavy tuning in Phase 4.

| Unit | Role | HP | Speed | Attack | Range | Cost | Build Time | Special |
|------|------|-----|-------|--------|-------|------|------------|---------|
| **Worker** | Economy | 30 | 80 | 5 | melee | 50 | 3s | Gathers food, constructs buildings |
| **Soldier** | Frontline | 80 | 60 | 15 | melee | 100 | 5s | Tanky, decent damage |
| **Spitter** | Ranged | 40 | 50 | 12 | 4 tiles | 120 | 6s | Ranged acid attack |
| **Scout** | Recon | 25 | 120 | 3 | melee | 40 | 2s | Fast, large sight range (8 tiles) |
| **Queen Ant** | Siege | 150 | 30 | 25 | melee | 300 | 15s | Massive damage vs buildings. Limit 1. |

### Unit Behaviors (State Machine)

Each unit has a behavior state:

```
IDLE → can transition to any state
MOVING → following path to target
GATHERING → worker at food source, periodic harvest ticks
BUILDING → worker at build site, periodic construction ticks
ATTACKING → in combat range, periodic attack ticks
RETURNING → worker carrying food back to nest
FLEEING → moving away from threats (optional, for workers)
```

- Units auto-attack enemies that enter their aggro radius (configurable per type).
- Workers flee by default when attacked (can be overridden with explicit attack command).
- Right-clicking an enemy issues an ATTACK command. Right-clicking ground issues MOVE.

## 2. Buildings

| Building | Role | HP | Cost | Build Time | Prerequisite |
|----------|------|-----|------|------------|--------------|
| **Nest** | HQ, worker production | 500 | — | — | Starting building |
| **Tunnel** | Expansion, income boost | 200 | 150 | 10s | Nest |
| **Nursery** | Produces combat units | 250 | 200 | 8s | Nest |
| **Food Store** | Increases max food capacity | 150 | 100 | 6s | Nest |
| **Guard Post** | Static defense, ranged attack | 200 | 150 | 8s | Nursery |
| **Evolution Chamber** | Unlocks upgrades | 200 | 250 | 12s | Nursery |

### Construction

1. Player selects a building from the build menu and places it on valid tiles.
2. A BUILD command is issued to a selected worker.
3. Worker moves to the site and spends build time constructing.
4. Building appears as "under construction" (reduced HP, non-functional) until complete.
5. If the worker is killed, construction pauses. Another worker can resume.

### Production

- Nest produces Workers.
- Nursery produces combat units (Soldier, Spitter, Scout, Queen Ant).
- Production queue: up to 5 units queued per building.
- A unit-in-progress has a production timer. When complete, it spawns near the building.

## 3. Tech Tree

```
Nest (start)
├── Tunnel (expansion)
├── Food Store (economy)
├── Nursery (combat units)
│   ├── Guard Post (static defense)
│   └── Evolution Chamber (upgrades)
│       ├── Hardened Carapace: +20% HP for Soldiers
│       ├── Acid Potency: +25% damage for Spitters
│       ├── Tunnel Network: +30% unit speed near Tunnels
│       └── Queen Ant: unlocks Queen Ant production
```

### Upgrade Mechanics

- Upgrades are researched at the Evolution Chamber (one at a time).
- Each upgrade has a food cost and research time.
- Upgrades apply globally to all existing and future units of that type.

## 4. Combat System

### Attack Resolution

```python
def resolve_attack(attacker: Entity, target: Entity, state: GameState):
    damage = attacker.attack_damage
    # Apply upgrades
    damage = apply_damage_modifiers(damage, attacker, state)
    target.hp -= damage
    if target.hp <= 0:
        destroy_entity(target, state)
```

- Attacks happen on a cooldown timer (attack_interval ticks per type).
- Melee: attacker must be adjacent (within 1 tile).
- Ranged: attacker must be within range (Euclidean distance, integer math).
- No projectile simulation — ranged attacks hit instantly (keeps it simple and deterministic).

### Targeting Priority

When auto-attacking, units prioritize:
1. Closest enemy unit in aggro range.
2. If multiple at same distance: lowest HP first (focus fire).

### Building Damage

- Units can attack buildings.
- Queen Ant deals 2x damage to buildings (siege role).
- Destroying the Nest wins the game.

## 5. Win Condition

**Destroy the enemy Nest.** When a Nest reaches 0 HP, that player loses.

- Display a victory/defeat screen.
- Log match stats: game duration, units produced, food gathered, units lost.

## 6. Pheromone Trails (Visual)

- When ants move, they leave a fading visual trail on the ground.
- Purely cosmetic in Phase 3 — does not affect gameplay.
- Trail intensity fades over time (render-side only, not simulation state).
- Creates an organic, ant-like feel to army movements.

---

## Work Split

### Dev A — Game Logic & Balance
- `src/simulation/combat.py` — attack resolution, damage, targeting
- `src/simulation/production.py` — unit production queues, building construction
- `src/simulation/tech.py` — upgrade research, modifier application
- `src/simulation/entities.py` — expand entity types, unit stats, behavior state machine
- `src/simulation/commands.py` — new command types (BUILD, PRODUCE, RESEARCH, ATTACK)
- Balance spreadsheet / config for unit stats
- Tests for combat math, production timing, tech tree prerequisites

### Dev B — UI & Presentation
- `src/rendering/renderer.py` — unit sprites/shapes per type, building visuals, HP bars
- `src/rendering/hud.py` — build menu, production queue display, tech tree UI
- `src/rendering/effects.py` — pheromone trails, attack animations, death effects
- `src/input/handler.py` — build placement, production hotkeys, attack-move
- Victory/defeat screen
- Visual polish and feedback (selection circles, rally points)

### Integration Points

- **Entity types & stats**: agree on the full EntityType enum and stat values.
- **Command types**: new commands need serialization support (Dev B updates networking if needed).
- **Build menu**: UI needs to know building prerequisites, costs, and available units.

### Merge Strategy

1. Dev A implements combat + production + tech as pure simulation logic with tests.
2. Dev B implements UI against mock/hardcoded data.
3. Integration PR: wire UI to real simulation data, play a full match.
4. Both devs playtest and tweak balance together.

---

## Done Criteria

- [ ] All 5 ant types are implemented with distinct stats and behaviors.
- [ ] All 6 buildings can be constructed by workers.
- [ ] Nursery produces combat units with a queue.
- [ ] Evolution Chamber researches upgrades that affect unit stats.
- [ ] Combat works: units attack, take damage, die.
- [ ] Queen Ant deals bonus damage to buildings.
- [ ] Destroying the Nest triggers victory/defeat.
- [ ] Tech tree prerequisites are enforced.
- [ ] Full match playable over network with no desync.
- [ ] Tests cover combat resolution, production, tech prerequisites.
