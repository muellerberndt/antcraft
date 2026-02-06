"""Harvesting system — ants collect jelly from corpses and return it to hives.

Flow per harvesting ant:
1. Move to corpse (handled by movement + harvest aggro in tick.py)
2. Extract jelly from corpse at HARVEST_RATE (Bresenham distributed)
3. When full (ANT_CARRY_CAPACITY) or corpse empty → pathfind to nearest own hive
4. Deposit jelly at hive → pathfind back to corpse for more
5. If corpse is gone → go idle

All math is integer. Deterministic.
"""

from __future__ import annotations

from src.config import (
    ANT_CARRY_CAPACITY,
    HARVEST_RANGE,
    HARVEST_RATE,
    MILLI_TILES_PER_TILE,
    TICK_RATE,
)
from src.simulation.pathfinding import find_path
from src.simulation.state import EntityState, EntityType, GameState

_HARVEST_RANGE_MT = HARVEST_RANGE * MILLI_TILES_PER_TILE
_HARVEST_RANGE_SQ = _HARVEST_RANGE_MT * _HARVEST_RANGE_MT


def _harvest_this_tick(rate: int, tick: int) -> int:
    """Bresenham-style integer distribution of harvest rate across ticks."""
    t = tick % TICK_RATE
    return (rate * (t + 1)) // TICK_RATE - (rate * t) // TICK_RATE


def process_harvesting(state: GameState) -> None:
    """Process all harvesting ants for one tick.

    Called after movement — ants that just arrived can extract or deposit.
    """
    for entity in state.entities:
        if entity.state != EntityState.HARVESTING:
            continue
        if entity.entity_type != EntityType.ANT:
            continue
        # Still moving — wait until arrival
        if entity.is_moving or entity.path:
            continue

        corpse = state.get_entity(entity.target_entity_id)
        corpse_has_jelly = (
            corpse is not None
            and corpse.entity_type == EntityType.CORPSE
            and corpse.jelly_value > 0
        )

        if entity.carrying < ANT_CARRY_CAPACITY and corpse_has_jelly:
            # Collecting phase — extract at corpse or walk back to it
            dx = entity.x - corpse.x
            dy = entity.y - corpse.y
            if dx * dx + dy * dy <= _HARVEST_RANGE_SQ:
                _try_extract(state, entity)
            else:
                # Pushed out of range by separation — return to corpse
                _pathfind_to(state, entity, corpse.x, corpse.y)
        elif entity.carrying > 0:
            # Full or corpse empty/gone — deposit at hive
            _try_deposit(state, entity)
        else:
            # No jelly and no valid corpse — done
            entity.state = EntityState.IDLE
            entity.target_entity_id = -1


def _try_extract(state: GameState, entity) -> None:
    """Extract jelly from the targeted corpse."""
    corpse = state.get_entity(entity.target_entity_id)
    if corpse is None or corpse.entity_type != EntityType.CORPSE:
        entity.state = EntityState.IDLE
        entity.target_entity_id = -1
        return

    dx = entity.x - corpse.x
    dy = entity.y - corpse.y
    if dx * dx + dy * dy > _HARVEST_RANGE_SQ:
        # Not close enough — pathfind to corpse
        _pathfind_to(state, entity, corpse.x, corpse.y)
        return

    amount = _harvest_this_tick(HARVEST_RATE, state.tick)
    can_carry = ANT_CARRY_CAPACITY - entity.carrying
    available = corpse.jelly_value
    transfer = min(amount, can_carry, available)

    if transfer > 0:
        entity.carrying += transfer
        corpse.jelly_value -= transfer

    if entity.carrying >= ANT_CARRY_CAPACITY or corpse.jelly_value <= 0:
        _send_to_nearest_hive(state, entity)


def _try_deposit(state: GameState, entity) -> None:
    """Deposit carried jelly at nearest own hive."""
    nearest_hive = None
    best_dist_sq = 0

    for e in state.entities:
        if e.entity_type != EntityType.HIVE or e.player_id != entity.player_id:
            continue
        dx = entity.x - e.x
        dy = entity.y - e.y
        dist_sq = dx * dx + dy * dy
        if nearest_hive is None or dist_sq < best_dist_sq:
            nearest_hive = e
            best_dist_sq = dist_sq

    if nearest_hive is None:
        entity.state = EntityState.IDLE
        entity.target_entity_id = -1
        return

    if best_dist_sq > _HARVEST_RANGE_SQ:
        _pathfind_to(state, entity, nearest_hive.x, nearest_hive.y)
        return

    # Deposit
    state.player_jelly[entity.player_id] = (
        state.player_jelly.get(entity.player_id, 0) + entity.carrying
    )
    entity.carrying = 0

    # Go back for more
    corpse = state.get_entity(entity.target_entity_id)
    if (
        corpse is not None
        and corpse.entity_type == EntityType.CORPSE
        and corpse.jelly_value > 0
    ):
        _pathfind_to(state, entity, corpse.x, corpse.y)
    else:
        entity.state = EntityState.IDLE
        entity.target_entity_id = -1


def _send_to_nearest_hive(state: GameState, entity) -> None:
    """Pathfind a carrying ant to its nearest own hive."""
    nearest_hive = None
    best_dist_sq = 0

    for e in state.entities:
        if e.entity_type != EntityType.HIVE or e.player_id != entity.player_id:
            continue
        dx = entity.x - e.x
        dy = entity.y - e.y
        dist_sq = dx * dx + dy * dy
        if nearest_hive is None or dist_sq < best_dist_sq:
            nearest_hive = e
            best_dist_sq = dist_sq

    if nearest_hive is None:
        entity.state = EntityState.IDLE
        entity.target_entity_id = -1
        return

    _pathfind_to(state, entity, nearest_hive.x, nearest_hive.y)


def _pathfind_to(state: GameState, entity, goal_x: int, goal_y: int) -> None:
    """Pathfind entity to a goal position."""
    target_tile_x = goal_x // MILLI_TILES_PER_TILE
    target_tile_y = goal_y // MILLI_TILES_PER_TILE
    start_tile_x = entity.x // MILLI_TILES_PER_TILE
    start_tile_y = entity.y // MILLI_TILES_PER_TILE

    tile_path = find_path(
        state.tilemap,
        start_tile_x, start_tile_y,
        target_tile_x, target_tile_y,
    )

    if not tile_path:
        entity.target_x = goal_x
        entity.target_y = goal_y
        entity.path = []
    else:
        milli_path = [
            (tx * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2,
             ty * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2)
            for tx, ty in tile_path
        ]
        entity.path = milli_path
        entity.target_x = milli_path[-1][0]
        entity.target_y = milli_path[-1][1]
