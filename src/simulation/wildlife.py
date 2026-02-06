"""Wildlife system — AI behavior and periodic spawning.

Wildlife entities (aphids, beetles, mantis) are neutral NPCs that provide
jelly when killed. Beetles and mantis actively chase nearby player entities.
Aphids are passive and stationary.

All math is integer. Spawning uses GameState.next_random() for determinism.
"""

from __future__ import annotations

from src.config import (
    APHID_DAMAGE,
    APHID_HP,
    APHID_JELLY,
    BEETLE_DAMAGE,
    BEETLE_HP,
    BEETLE_JELLY,
    BEETLE_SPEED,
    MANTIS_DAMAGE,
    MANTIS_HP,
    MANTIS_JELLY,
    MANTIS_SPEED,
    MILLI_TILES_PER_TILE,
    WILDLIFE_AGGRO_RANGE,
    WILDLIFE_HIVE_EXCLUSION,
    WILDLIFE_MAX_APHIDS,
    WILDLIFE_MAX_BEETLES,
    WILDLIFE_MAX_MANTIS,
    WILDLIFE_SPAWN_INTERVAL,
)
from src.simulation.pathfinding import find_path
from src.simulation.state import EntityState, EntityType, GameState

# Aggro range in milli-tiles (squared for distance comparison)
_AGGRO_RANGE_MT = WILDLIFE_AGGRO_RANGE * MILLI_TILES_PER_TILE
_AGGRO_RANGE_SQ = _AGGRO_RANGE_MT * _AGGRO_RANGE_MT

# Hive exclusion in tiles (squared)
_HIVE_EXCLUSION_SQ = WILDLIFE_HIVE_EXCLUSION * WILDLIFE_HIVE_EXCLUSION

# Wildlife types that have AI (chase behavior)
_AGGRESSIVE_TYPES = frozenset({EntityType.BEETLE, EntityType.MANTIS})

# Stats lookup for spawning
_WILDLIFE_STATS = {
    EntityType.APHID: {
        "speed": 0, "hp": APHID_HP, "max_hp": APHID_HP,
        "damage": APHID_DAMAGE, "jelly_value": APHID_JELLY,
    },
    EntityType.BEETLE: {
        "speed": BEETLE_SPEED, "hp": BEETLE_HP, "max_hp": BEETLE_HP,
        "damage": BEETLE_DAMAGE, "jelly_value": BEETLE_JELLY,
    },
    EntityType.MANTIS: {
        "speed": MANTIS_SPEED, "hp": MANTIS_HP, "max_hp": MANTIS_HP,
        "damage": MANTIS_DAMAGE, "jelly_value": MANTIS_JELLY,
    },
}


def process_wildlife(state: GameState) -> None:
    """Run wildlife AI and spawning for one tick.

    Called before movement in the tick pipeline so that AI-set targets
    are processed by movement this same tick.
    """
    _update_wildlife_ai(state)
    _spawn_wildlife(state)


def _update_wildlife_ai(state: GameState) -> None:
    """Aggressive wildlife chases nearby player entities.

    Beetles and mantis scan for the nearest player-owned entity within
    aggro range. If found and not already attacking or moving, they
    pathfind toward it. Aphids do nothing.
    """
    mt = MILLI_TILES_PER_TILE

    for entity in state.entities:
        if entity.player_id != -1:
            continue
        if entity.entity_type not in _AGGRESSIVE_TYPES:
            continue
        if entity.speed <= 0:
            continue
        # Already attacking — combat system handles it
        if entity.state == EntityState.ATTACKING:
            continue
        # Already chasing something — let movement finish
        if entity.is_moving or entity.path:
            continue

        # Find nearest player-owned entity within aggro range
        best_target = None
        best_dist_sq = _AGGRO_RANGE_SQ + 1

        for target in state.entities:
            if target.player_id < 0:
                continue  # skip wildlife/neutral
            dx = entity.x - target.x
            dy = entity.y - target.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_target = target

        if best_target is None:
            continue

        # Pathfind toward target
        start_tx = entity.x // mt
        start_ty = entity.y // mt
        goal_tx = best_target.x // mt
        goal_ty = best_target.y // mt

        tile_path = find_path(state.tilemap, start_tx, start_ty, goal_tx, goal_ty)

        if tile_path:
            milli_path = [
                (tx * mt + mt // 2, ty * mt + mt // 2)
                for tx, ty in tile_path
            ]
            entity.path = milli_path
            entity.target_x = milli_path[-1][0]
            entity.target_y = milli_path[-1][1]
        else:
            # Direct movement fallback (no path or already adjacent)
            entity.target_x = best_target.x
            entity.target_y = best_target.y


def _spawn_wildlife(state: GameState) -> None:
    """Periodically spawn wildlife at random walkable locations.

    Runs every WILDLIFE_SPAWN_INTERVAL ticks. Rolls PRNG to pick a type,
    checks population cap, then tries to place on a valid tile away from hives.
    """
    if state.tick % WILDLIFE_SPAWN_INTERVAL != 0:
        return

    # Count existing wildlife
    counts = {EntityType.APHID: 0, EntityType.BEETLE: 0, EntityType.MANTIS: 0}
    for e in state.entities:
        if e.entity_type in counts:
            counts[e.entity_type] += 1

    # Roll to pick type (50% aphid, 30% beetle, 20% mantis)
    roll = state.next_random(100)

    if roll < 50:
        etype = EntityType.APHID
        cap = WILDLIFE_MAX_APHIDS
    elif roll < 80:
        etype = EntityType.BEETLE
        cap = WILDLIFE_MAX_BEETLES
    else:
        etype = EntityType.MANTIS
        cap = WILDLIFE_MAX_MANTIS

    if counts[etype] >= cap:
        return

    _try_spawn_one(state, etype)


def _try_spawn_one(state: GameState, etype: EntityType) -> None:
    """Try to place a wildlife entity on a valid tile (up to 10 attempts)."""
    tilemap = state.tilemap
    mt = MILLI_TILES_PER_TILE

    # Collect hive tile positions for exclusion check
    hive_tiles = []
    for e in state.entities:
        if e.entity_type == EntityType.HIVE:
            hive_tiles.append((e.x // mt, e.y // mt))

    for _ in range(10):
        tx = state.next_random(tilemap.width)
        ty = state.next_random(tilemap.height)

        if not tilemap.is_walkable(tx, ty):
            continue

        # Check distance from all hives
        too_close = False
        for hx, hy in hive_tiles:
            dx = tx - hx
            dy = ty - hy
            if dx * dx + dy * dy < _HIVE_EXCLUSION_SQ:
                too_close = True
                break

        if too_close:
            continue

        # Spawn the entity
        stats = _WILDLIFE_STATS[etype]
        state.create_entity(
            player_id=-1,
            x=tx * mt + mt // 2,
            y=ty * mt + mt // 2,
            entity_type=etype,
            sight=0,
            **stats,
        )
        return
