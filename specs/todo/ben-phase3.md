# Phase 3 — Ben (Simulation)

All simulation code. Headless, testable without PyGame, deterministic (integer math only). Work on a feature branch and merge via PR.

**Branch:** `phase3-simulation`

**Reference:** [phase3-units-and-buildings.md](../phase3-units-and-buildings.md), [game_mechanics.md](../game_mechanics.md), [balance.md](../balance.md)

---

## Shared Setup — DONE

Shared interfaces merged before parallel work begins:

- [x] `CommandType.ATTACK = 7`
- [x] `Entity.target_entity_id: int = -1` (tracks harvest/attack target)
- [x] `compute_hash()` updated to include `target_entity_id`
- [x] Config: `HARVEST_RANGE = 1`, `HARVEST_RATE = 5`, `ANT_CARRY_CAPACITY = 10`

---

## Task 1: Harvesting System

**File:** `src/simulation/harvest.py` (new)
**Tests:** `tests/test_simulation/test_harvest.py`

- [ ] HARVEST command handler (in `tick.py`):
  - Validate: entity is ANT, target is CORPSE, correct player
  - Set `entity.target_entity_id = corpse_id`
  - Pathfind ant to corpse position
- [ ] Harvesting tick logic (new `process_harvesting(state)` called in `advance_tick`):
  - **Moving to corpse**: ant has `target_entity_id` pointing to a corpse
    - If corpse gone (decayed): clear target, idle
    - If within HARVEST_RANGE: state = HARVESTING, stop movement
  - **At corpse (HARVESTING state)**:
    - Transfer jelly: Bresenham-distributed `HARVEST_RATE` jelly/sec
    - `amount = min(rate_this_tick, corpse.jelly_value, ANT_CARRY_CAPACITY - carrying)`
    - `entity.carrying += amount; corpse.jelly_value -= amount`
    - If corpse depleted (jelly_value <= 0): remove corpse from entities
    - If ant full or corpse empty: clear target, pathfind to nearest own hive
  - **Returning to hive**: ant has `carrying > 0` and no `target_entity_id`
    - If near own hive (within HARVEST_RANGE): deposit `carrying` to `player_jelly`, set carrying = 0, state = IDLE
    - If arrived at target but no hive there: re-pathfind to nearest own hive
- [ ] Tick pipeline placement: after wildlife, before movement
  - `commands → wildlife → harvesting → movement → separation → combat → hive → fog → tick++`
  - Reason: harvesting sets paths/targets that movement then processes
- [ ] Tests:
  - Ant pathfinds to corpse on HARVEST command
  - Ant transfers jelly at correct rate (Bresenham)
  - Ant stops when full (ANT_CARRY_CAPACITY)
  - Ant auto-returns to nearest own hive when done
  - Jelly deposited to player_jelly at hive
  - Corpse removed when fully depleted
  - Corpse decays mid-harvest → ant idles
  - Multiple ants share same corpse
  - Ant killed while carrying → jelly lost
  - Harvesting interrupted by MOVE/STOP → clears harvest target
  - Determinism: identical state after harvest cycle

## Task 2: Explicit Attack Command

**File:** `src/simulation/tick.py` (extend) + `src/simulation/combat.py` (modify)
**Tests:** `tests/test_simulation/test_attack.py`

- [ ] ATTACK command handler (in `tick.py`):
  - Validate: entity has damage > 0, target is enemy entity
  - Set `entity.target_entity_id = enemy_id`
  - Pathfind toward enemy's current position
- [ ] Attack chase logic (new `_process_attack_chasing(state)` or extend combat):
  - Each tick, for entities with `target_entity_id` pointing to an enemy:
    - If target dead/gone: clear `target_entity_id`, state = IDLE
    - If target alive and NOT in attack range and ant is idle (not moving):
      - Re-pathfind toward target's CURRENT position (target may have moved)
    - If target alive and in attack range: auto-attack handles damage (existing)
  - Tick pipeline: run before movement (so chase paths are set), or after combat (to re-chase)
- [ ] Modify `_auto_attack` in combat.py:
  - If entity has `target_entity_id` pointing to a valid enemy in range: prefer that target
  - Fall back to nearest-enemy logic for entities without explicit target
- [ ] MOVE/STOP commands should clear `target_entity_id` (cancel chase)
- [ ] Tests:
  - ATTACK command makes ant chase target
  - Ant re-pathfinds when target moves
  - Ant stops chasing when target dies
  - Ant with explicit target prioritizes it in auto-attack
  - MOVE/STOP cancels attack chase
  - Determinism: identical state after chase sequence

---

## Integration Notes

- theCoon's right-click handler will generate ATTACK/HARVEST commands using the agreed CommandType + target_entity_id
- The renderer reads `entity.state`, `entity.carrying`, and `entity.target_entity_id` for visuals
- `process_harvesting` must run deterministically — same Bresenham formula as income/damage
- Run `python -m pytest tests/` before every commit
