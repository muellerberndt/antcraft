# Phase 3: Playable Game

## Goal

Make AntCraft playable end-to-end. Two players can fight, harvest, expand, and win/lose. Focus on the core gameplay loop — no extra unit types, buildings, or tech tree yet.

## Scope (Simplified)

- **One building**: Hive (already implemented)
- **Two units**: Ant (fights + harvests) and Queen (founds hives)
- **No workers**: The single ant type handles combat, harvesting, and merging
- **Economy**: Passive hive income (done) + corpse harvesting (new)
- **Better combat**: Explicit attack targeting for micro control
- **Game feel**: Visual feedback, hotkeys, victory/defeat screen

This aligns with [game_mechanics.md](game_mechanics.md) — the simplified "ants are the resource" design.

---

## What's Already Done (Phase 2)

- Tile map with procedural generation, A* pathfinding, movement
- Combat: auto-attack, death, corpse creation, corpse decay
- Hive mechanics: spawn ant, merge queen, found hive, passive income, win condition
- Wildlife: periodic spawning, beetle/mantis AI chase
- Fog of war, visibility system
- Selection (click + drag box), move, stop commands
- Minimap, HP bars, selection indicators, resource display
- Multiplayer lockstep networking with desync detection

---

## What Phase 3 Adds

### 1. Harvesting System (Simulation)

The missing piece of the jelly economy. Ants can pick up jelly from corpses and carry it back to the hive.

**Flow:**
1. Player right-clicks a corpse with ants selected → HARVEST command
2. Ants pathfind to the corpse
3. At the corpse: state = HARVESTING, jelly transfers from corpse to ant's `carrying` (rate-limited, HARVEST_RATE jelly/sec)
4. When ant is full (ANT_CARRY_CAPACITY) or corpse is depleted → auto-return to nearest own hive
5. At hive: deposit `carrying` into `player_jelly`, ant becomes idle

**Edge cases:**
- Corpse decays while ant is walking to it → ant idles
- Multiple ants harvest same corpse → first-come, shared until depleted
- Ant killed while carrying → jelly is lost (carried jelly NOT dropped as new corpse)
- Ant ordered to do something else mid-harvest → cancels harvest, keeps any jelly in `carrying` until it reaches a hive

**Config:**
- `HARVEST_RANGE = 1` tile (same as attack range)
- `HARVEST_RATE = 5` jelly/sec (Bresenham distributed)
- `ANT_CARRY_CAPACITY = 10` max jelly per trip

### 2. Explicit Attack Command (Simulation)

Right-click on an enemy = chase and attack that specific target. Enables micro control and focus-fire.

**Flow:**
1. Player right-clicks an enemy entity → ATTACK command (target_entity_id = enemy)
2. Ant pathfinds toward target's position
3. When in attack range: auto-attack system deals damage (existing)
4. If target moves out of range: ant re-pathfinds to follow
5. If target dies: ant clears target, becomes idle

**Shared with auto-attack:**
- The existing `_auto_attack()` in combat.py handles damage dealing
- ATTACK command adds *chasing* — the ant actively follows the target
- Ants with explicit targets prioritize those targets over nearest-enemy auto-attack

**Config:**
- CommandType.ATTACK = 7 (new command type)
- Entity.target_entity_id field (tracks chase/harvest target)

### 3. Context-Sensitive Right-Click (Input)

Right-click behavior depends on what's under the cursor:

| Click target        | Command generated | Condition |
|---------------------|-------------------|-----------|
| Enemy unit/building | ATTACK            | Any combat unit selected |
| Corpse              | HARVEST           | Ant selected |
| Hive site           | FOUND_HIVE        | Queen selected |
| Ground              | MOVE              | Any unit selected |

Requires entity hit-detection under the cursor (check nearest entity within click radius).

### 4. Game Command Hotkeys (Input)

| Key | Command | Behavior |
|-----|---------|----------|
| N   | SPAWN_ANT | Spawn ant from selected hive (or nearest own hive) |
| Q   | MERGE_QUEEN | Merge 5 ants at nearest own hive into a queen |
| H   | FOUND_HIVE | Send selected queen to nearest unclaimed hive site |

Hotkeys should show feedback when triggered (flash, sound) and when rejected (insufficient jelly, wrong selection).

### 5. Combat Visuals & Feedback (Rendering)

Improve combat readability so players can micro effectively:

- **Attack animation**: Visual pulse/flash when a unit deals damage
- **Damage feedback**: Brief flash on hit, or floating damage numbers
- **State clarity**: Visually distinguish idle / moving / attacking / harvesting states
- **Harvesting visual**: Ant picks up glowing jelly, carries it visibly
- **Target lines**: Show who is attacking whom (thin line from attacker to target)

### 6. Victory/Defeat Screen (Rendering)

When `game_over` is True:

- Full-screen overlay: "VICTORY" or "DEFEAT"
- Match stats: game duration, ants spawned, ants killed, jelly harvested
- Continue watching / Quit options

### 7. Selection & Info Panel (Rendering)

Improve the bottom-of-screen info:

- Selected unit stats: HP, damage, speed, carrying
- Multi-select: unit count by type, total HP
- Available commands for current selection (with hotkey hints)
- Feedback toast: "Not enough jelly!", "No hive nearby", etc.

---

## Shared Interfaces (Implement First)

These changes must be merged before parallel work begins:

- `CommandType.ATTACK = 7`
- `Entity.target_entity_id: int = -1` + include in `compute_hash()`
- Config: `HARVEST_RANGE`, `HARVEST_RATE`, `ANT_CARRY_CAPACITY`

---

## Work Split

### Ben — Simulation

**Branch:** `phase3-simulation`

1. Harvesting system (HARVEST command, tick logic, auto-return)
2. Explicit ATTACK command (chase + follow + re-pathfind)
3. Tests for harvesting + attack

### theCoon — UI & Rendering

**Branch:** `phase3-ui`

1. Context-sensitive right-click (entity hit detection, command routing)
2. Game command hotkeys (N/Q/H)
3. Combat visuals & feedback (attack animations, damage indicators)
4. Victory/defeat screen
5. Selection & info panel improvements

### Integration Points

- **Right-click → commands**: theCoon generates ATTACK/HARVEST commands, Ben's simulation processes them
- **Entity.state + carrying**: Renderer reads these to show correct visuals
- **game_over + winner**: Renderer reads these for victory/defeat screen

---

## Done Criteria

- [ ] Ants harvest corpses and carry jelly back to hive
- [ ] Right-click on enemy = attack-chase; right-click on corpse = harvest
- [ ] Hotkeys work for spawn ant, merge queen, found hive
- [ ] Attack visuals show who is fighting whom
- [ ] Victory/defeat screen displays on game end
- [ ] Full match playable over network with no desync
- [ ] Tests cover harvesting, attack command, and integration
