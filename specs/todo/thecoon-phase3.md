# Phase 3 — theCoon (UI & Rendering)

All input handling, rendering, and visual feedback. Work on a feature branch and merge via PR.

**Branch:** `phase3-ui`

**Reference:** [phase3-units-and-buildings.md](../phase3-units-and-buildings.md), [hotkeys.md](../../docs/hotkeys.md)

---

## Shared Setup — DONE

Shared interfaces merged before parallel work begins:

- [x] `CommandType.ATTACK = 7` available for input handler
- [x] `Entity.target_entity_id` field readable by renderer
- [x] Config: `HARVEST_RANGE`, `HARVEST_RATE`, `ANT_CARRY_CAPACITY`

---

## Task 1: Context-Sensitive Right-Click — DONE

**File:** `src/input/handler.py`

Default right-click auto-detects target entity under cursor:
- [x] Right-click enemy → ATTACK — **works**
- [x] Right-click corpse → HARVEST — **WIP** (extraction works, return-to-hive buggy)
- [x] Right-click hive site → FOUND_HIVE — **untested**
- [x] Right-click ground → MOVE — **works**

Dedicated hotkey modes (press key, then right-click):
- [x] **A** → Attack mode — **works**
- [x] **M** → Move mode — **works**
- [x] **E** → Harvest mode — **WIP**
- [x] **F** → Found hive mode — **untested**

- [x] Entity_ids filtered by command validity
- [ ] Visual cursor change based on hover target (optional)

## Task 2: Game Command Hotkeys — DONE

**File:** `src/input/handler.py`

- [x] **N key** → SPAWN_ANT — **works**
- [x] **Q key** → MERGE_QUEEN — **untested**
- [x] **H key** → FOUND_HIVE — **untested**
- [x] Updated `docs/hotkeys.md` with all new bindings

## Task 3: Combat Visuals & Feedback

**File:** `src/rendering/renderer.py`, possibly new `src/rendering/effects.py`

- [ ] **Attack flash**: Brief white/red flash on entity when it takes damage
  - Track per-entity "last_hit_tick" by comparing HP changes between frames
  - Flash for 2-3 render frames
- [ ] **Attack lines**: Thin red line from attacker to target when entity.state == ATTACKING
  - Use `entity.target_entity_id` to find the target entity
  - Line fades with distance
- [ ] **State indicators** (improve existing):
  - ATTACKING: pulsing red circle (upgrade from static)
  - HARVESTING: pulsing gold circle
  - MOVING with carrying > 0: gold trail particles
- [ ] **Damage numbers** (optional, low priority):
  - Floating numbers at damage location
  - Fade up and disappear over ~1 second

## Task 4: Victory/Defeat Screen

**File:** `src/game.py` or new `src/rendering/screens.py`

- [ ] Check `state.game_over` each frame in `_render()`
- [ ] Overlay screen when game ends:
  - Semi-transparent dark overlay
  - Large text: "VICTORY" (green) or "DEFEAT" (red) based on `state.winner == player_id`
  - Draw (winner == -1): "DRAW" in yellow
- [ ] Match stats display:
  - Game duration (ticks / TICK_RATE → seconds → mm:ss)
  - Current jelly
  - Number of own ants remaining
- [ ] Controls:
  - ESC or click to quit
  - Optional: continue watching (camera still works)

## Task 5: Selection Info Panel

**File:** `src/rendering/hud.py`

Expand the existing bottom-left selection info:

- [ ] **Single unit selected**: Show all stats
  - Name (Ant / Queen / Hive)
  - HP bar with numbers (current/max)
  - Damage, Speed
  - Carrying (if > 0): "Carrying: 5/10 jelly"
  - State: Idle / Moving / Attacking / Harvesting
- [ ] **Multi-select**: Summary info
  - Unit count by type (e.g., "12 Ants, 1 Queen")
  - Total HP / max HP
  - Average health percentage
- [ ] **Available commands** (bottom bar):
  - Show hotkey hints for valid commands given current selection
  - E.g., ants selected: "[N] Spawn  [Q] Merge Queen  [S] Stop"
  - Hive selected: "[N] Spawn Ant"
  - Gray out unavailable commands (not enough jelly, wrong selection)
- [ ] **Feedback toasts** (top-center, temporary):
  - "Not enough jelly!" — when spawn/merge rejected
  - "No queen selected" — when H pressed without queen
  - Toast fades after 2 seconds

---

## Integration Notes

- Ben's simulation processes ATTACK/HARVEST commands — your input handler just generates them
- Read `entity.state`, `entity.carrying`, `entity.target_entity_id` for visual feedback
- Read `state.game_over`, `state.winner` for victory/defeat screen
- Read `state.player_jelly[player_id]` for resource display (already done)
- The HARVEST/ATTACK simulation logic may not be merged yet — test with mock commands or `--local` mode
- Hotkey commands should still be generated even before simulation handlers exist (they'll be silently ignored)
