"""Tick logic — advance the simulation by one step.

This is the heart of the deterministic simulation. Both peers call
advance_tick() with the same commands on the same tick, producing
identical game states.

ALL MATH IS INTEGER. No floats anywhere in this module.
"""

from __future__ import annotations

from math import isqrt

from src.config import MILLI_TILES_PER_TILE, SEPARATION_FORCE, SEPARATION_RADIUS
from src.simulation.combat import process_combat
from src.simulation.harvest import process_harvesting
from src.simulation.commands import Command, CommandType
from src.simulation.hive import (
    handle_found_hive,
    handle_merge_queen,
    handle_morph_spitter,
    handle_spawn_ant,
    process_hive_mechanics,
)
from src.simulation.pathfinding import find_path
from src.simulation.state import EntityState, EntityType, GameState
from src.simulation.wildlife import process_wildlife


def advance_tick(state: GameState, commands: list[Command]) -> None:
    """Advance the simulation by one tick.

    Args:
        state: The current game state (mutated in place).
        commands: All commands for this tick, sorted deterministically.
    """
    _process_commands(state, commands)
    process_wildlife(state)
    _check_aggro(state)
    _check_harvest_aggro(state)
    _update_movement(state)
    _apply_separation(state)
    process_harvesting(state)
    process_combat(state)
    process_hive_mechanics(state)
    # Recompute fog of war for both players
    state.visibility.update(state.entities, 0)
    state.visibility.update(state.entities, 1)
    state.tick += 1


def _process_commands(state: GameState, commands: list[Command]) -> None:
    """Apply all commands for this tick to the game state."""
    for cmd in commands:
        if cmd.command_type == CommandType.MOVE:
            _handle_move(state, cmd)
        elif cmd.command_type == CommandType.STOP:
            _handle_stop(state, cmd)
        elif cmd.command_type == CommandType.SPAWN_ANT:
            handle_spawn_ant(state, cmd)
        elif cmd.command_type == CommandType.MERGE_QUEEN:
            handle_merge_queen(state, cmd)
        elif cmd.command_type == CommandType.FOUND_HIVE:
            handle_found_hive(state, cmd)
        elif cmd.command_type == CommandType.ATTACK:
            _handle_attack(state, cmd)
        elif cmd.command_type == CommandType.HARVEST:
            _handle_harvest(state, cmd)
        elif cmd.command_type == CommandType.MORPH_SPITTER:
            handle_morph_spitter(state, cmd)


def _handle_move(state: GameState, cmd: Command) -> None:
    """Compute A* path and assign it to entities."""
    target_tile_x = cmd.target_x // MILLI_TILES_PER_TILE
    target_tile_y = cmd.target_y // MILLI_TILES_PER_TILE
    final_target_x = cmd.target_x
    final_target_y = cmd.target_y

    if not state.tilemap.is_walkable(target_tile_x, target_tile_y):
        nearest = _find_nearest_walkable(state.tilemap, target_tile_x, target_tile_y)
        if nearest is None:
            return
        target_tile_x, target_tile_y = nearest
        final_target_x = target_tile_x * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
        final_target_y = target_tile_y * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2

    for entity_id in cmd.entity_ids:
        entity = state.get_entity(entity_id)
        if entity is None or entity.player_id != cmd.player_id:
            continue

        # Compute path from entity's current tile to target tile
        start_tile_x = entity.x // MILLI_TILES_PER_TILE
        start_tile_y = entity.y // MILLI_TILES_PER_TILE
        tile_path = find_path(
            state.tilemap,
            start_tile_x, start_tile_y,
            target_tile_x, target_tile_y,
        )

        if not tile_path:
            # No path found (or already at target tile) — just set direct target
            entity.target_x = final_target_x
            entity.target_y = final_target_y
            entity.path = []
            continue

        # Convert tile waypoints to milli-tile centers
        milli_path = [
            (tx * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2,
             ty * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2)
            for tx, ty in tile_path
        ]

        entity.path = milli_path
        # Set target to final destination for renderer target indicator
        entity.target_x = milli_path[-1][0]
        entity.target_y = milli_path[-1][1]


def _handle_stop(state: GameState, cmd: Command) -> None:
    """Stop entities at their current position."""
    for entity_id in cmd.entity_ids:
        entity = state.get_entity(entity_id)
        if entity is not None and entity.player_id == cmd.player_id:
            entity.target_x = entity.x
            entity.target_y = entity.y
            entity.path = []


def _handle_attack(state: GameState, cmd: Command) -> None:
    """Pathfind entities toward the target entity to attack it."""
    target = state.get_entity(cmd.target_entity_id)
    if target is None:
        return

    target_tile_x = target.x // MILLI_TILES_PER_TILE
    target_tile_y = target.y // MILLI_TILES_PER_TILE

    for entity_id in cmd.entity_ids:
        entity = state.get_entity(entity_id)
        if entity is None or entity.player_id != cmd.player_id:
            continue
        if entity.damage <= 0:
            continue

        entity.target_entity_id = target.entity_id

        start_tile_x = entity.x // MILLI_TILES_PER_TILE
        start_tile_y = entity.y // MILLI_TILES_PER_TILE
        tile_path = find_path(
            state.tilemap,
            start_tile_x, start_tile_y,
            target_tile_x, target_tile_y,
        )

        if not tile_path:
            entity.target_x = target.x
            entity.target_y = target.y
            entity.path = []
            continue

        milli_path = [
            (tx * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2,
             ty * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2)
            for tx, ty in tile_path
        ]
        entity.path = milli_path
        entity.target_x = milli_path[-1][0]
        entity.target_y = milli_path[-1][1]


def _handle_harvest(state: GameState, cmd: Command) -> None:
    """Handle HARVEST — pathfind ants to corpse or harvest-move position."""
    if cmd.target_entity_id >= 0:
        target = state.get_entity(cmd.target_entity_id)
        if target is None:
            return
        goal_x, goal_y = target.x, target.y
    else:
        goal_x, goal_y = cmd.target_x, cmd.target_y

    target_tile_x = goal_x // MILLI_TILES_PER_TILE
    target_tile_y = goal_y // MILLI_TILES_PER_TILE

    if not state.tilemap.is_walkable(target_tile_x, target_tile_y):
        nearest = _find_nearest_walkable(
            state.tilemap, target_tile_x, target_tile_y,
        )
        if nearest is None:
            return
        target_tile_x, target_tile_y = nearest
        goal_x = target_tile_x * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
        goal_y = target_tile_y * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2

    for entity_id in cmd.entity_ids:
        entity = state.get_entity(entity_id)
        if entity is None or entity.player_id != cmd.player_id:
            continue
        if entity.entity_type != EntityType.ANT:
            continue

        entity.state = EntityState.HARVESTING
        if cmd.target_entity_id >= 0:
            entity.target_entity_id = cmd.target_entity_id

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


_AGGRO_TARGETS = frozenset({
    EntityType.ANT, EntityType.QUEEN, EntityType.HIVE, EntityType.SPITTER,
    EntityType.APHID, EntityType.BEETLE, EntityType.MANTIS,
})


def _check_aggro(state: GameState) -> None:
    """Divert attack-mode units to closer enemies within aggro range.

    Only applies to entities with target_entity_id set (given an ATTACK
    command). If a closer enemy enters 25% of their sight range, they
    redirect to attack it instead.
    """
    for entity in state.entities:
        if entity.target_entity_id == -1:
            continue
        if entity.damage <= 0:
            continue
        if not entity.is_moving and not entity.path:
            continue

        aggro_range_mt = entity.sight * MILLI_TILES_PER_TILE // 4
        aggro_range_sq = aggro_range_mt * aggro_range_mt

        best_enemy = None
        best_dist_sq = aggro_range_sq + 1

        for other in state.entities:
            if other.entity_type not in _AGGRO_TARGETS:
                continue
            if other.hp <= 0:
                continue
            if other.player_id == entity.player_id:
                continue
            if entity.player_id == -1 and other.player_id == -1:
                continue

            dx = entity.x - other.x
            dy = entity.y - other.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_enemy = other

        if best_enemy is None or best_enemy.entity_id == entity.target_entity_id:
            continue

        # Divert to the closer enemy
        entity.target_entity_id = best_enemy.entity_id
        target_tile_x = best_enemy.x // MILLI_TILES_PER_TILE
        target_tile_y = best_enemy.y // MILLI_TILES_PER_TILE
        start_tile_x = entity.x // MILLI_TILES_PER_TILE
        start_tile_y = entity.y // MILLI_TILES_PER_TILE
        tile_path = find_path(
            state.tilemap,
            start_tile_x, start_tile_y,
            target_tile_x, target_tile_y,
        )
        if not tile_path:
            entity.target_x = best_enemy.x
            entity.target_y = best_enemy.y
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


def _check_harvest_aggro(state: GameState) -> None:
    """Auto-divert harvesting entities to nearby corpses within aggro range.

    Only applies to entities with state == HARVESTING. If a corpse enters
    25% of their sight range, they redirect to harvest it.
    """
    for entity in state.entities:
        if entity.state != EntityState.HARVESTING:
            continue
        if entity.carrying > 0:
            continue  # returning to hive with jelly, don't divert
        if not entity.is_moving and not entity.path:
            continue

        aggro_range_mt = entity.sight * MILLI_TILES_PER_TILE // 4
        aggro_range_sq = aggro_range_mt * aggro_range_mt

        best_corpse = None
        best_dist_sq = aggro_range_sq + 1

        for other in state.entities:
            if other.entity_type != EntityType.CORPSE:
                continue
            if other.hp <= 0:
                continue

            dx = entity.x - other.x
            dy = entity.y - other.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_corpse = other

        if best_corpse is None:
            continue
        if best_corpse.entity_id == entity.target_entity_id:
            continue

        entity.target_entity_id = best_corpse.entity_id
        target_tile_x = best_corpse.x // MILLI_TILES_PER_TILE
        target_tile_y = best_corpse.y // MILLI_TILES_PER_TILE
        start_tile_x = entity.x // MILLI_TILES_PER_TILE
        start_tile_y = entity.y // MILLI_TILES_PER_TILE
        tile_path = find_path(
            state.tilemap,
            start_tile_x, start_tile_y,
            target_tile_x, target_tile_y,
        )
        if not tile_path:
            entity.target_x = best_corpse.x
            entity.target_y = best_corpse.y
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


def _update_movement(state: GameState) -> None:
    """Move all entities along their paths. Integer math only."""
    for entity in state.entities:
        if entity.path:
            _follow_path(entity)
        elif entity.is_moving:
            # Direct movement (no path) — move straight toward target
            _move_toward(entity, entity.target_x, entity.target_y)


def _follow_path(entity) -> None:
    """Move entity toward the next waypoint in its path."""
    wx, wy = entity.path[0]
    _move_toward(entity, wx, wy)

    # Check if we reached the waypoint (within speed distance)
    dx = wx - entity.x
    dy = wy - entity.y
    dist_sq = dx * dx + dy * dy
    if dist_sq <= entity.speed * entity.speed:
        # Snap to waypoint and pop it
        entity.x = wx
        entity.y = wy
        entity.path.pop(0)

        # If path is now empty, we've arrived
        if not entity.path:
            entity.target_x = entity.x
            entity.target_y = entity.y


def _move_toward(entity, goal_x: int, goal_y: int) -> None:
    """Move entity one step toward (goal_x, goal_y)."""
    dx = goal_x - entity.x
    dy = goal_y - entity.y
    dist_sq = dx * dx + dy * dy
    dist = isqrt(dist_sq)

    if dist == 0:
        return

    if dist <= entity.speed:
        entity.x = goal_x
        entity.y = goal_y
    else:
        entity.x += dx * entity.speed // dist
        entity.y += dy * entity.speed // dist


_BFS_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
_SEP_RADIUS_SQ = SEPARATION_RADIUS * SEPARATION_RADIUS


def _find_nearest_walkable(tilemap, tile_x: int, tile_y: int) -> tuple[int, int] | None:
    """BFS outward from a non-walkable tile to find the nearest walkable one."""
    visited = {(tile_x, tile_y)}
    current = [(tile_x, tile_y)]

    for _ in range(15):
        next_layer: list[tuple[int, int]] = []
        candidates: list[tuple[int, int]] = []
        for x, y in current:
            for dx, dy in _BFS_DIRS:
                nx, ny = x + dx, y + dy
                if (nx, ny) in visited:
                    continue
                visited.add((nx, ny))
                if tilemap.is_walkable(nx, ny):
                    candidates.append((nx, ny))
                else:
                    next_layer.append((nx, ny))
        if candidates:
            # Pick closest to original target; tie-break by (y, x)
            return min(
                candidates,
                key=lambda p: ((p[0] - tile_x) ** 2 + (p[1] - tile_y) ** 2, p[1], p[0]),
            )
        current = next_layer
        if not current:
            break

    return None


def _apply_separation(state: GameState) -> None:
    """Gently push overlapping mobile entities apart.

    Computes all pushes from a snapshot, then applies — so ordering
    doesn't matter and both peers get identical results.
    """
    entities = state.entities
    n = len(entities)
    tilemap = state.tilemap

    # Phase 1: compute pushes from snapshot positions
    pushes: list[tuple[int, int]] = [(0, 0)] * n

    for i in range(n):
        ei = entities[i]
        if ei.speed == 0:
            continue

        px, py = 0, 0
        for j in range(n):
            if i == j:
                continue
            ej = entities[j]
            if ej.speed == 0:
                continue

            dx = ei.x - ej.x
            dy = ei.y - ej.y
            dist_sq = dx * dx + dy * dy

            if dist_sq >= _SEP_RADIUS_SQ:
                continue

            if dist_sq == 0:
                # Exact overlap — deterministic tiebreaker using entity_id
                if ei.entity_id > ej.entity_id:
                    px += SEPARATION_FORCE
                else:
                    px -= SEPARATION_FORCE
                continue

            dist = isqrt(dist_sq)
            # Push proportional to force, in direction away from neighbor
            px += dx * SEPARATION_FORCE // dist
            py += dy * SEPARATION_FORCE // dist

        pushes[i] = (px, py)

    # Phase 2: apply pushes, checking walkability
    for i in range(n):
        px, py = pushes[i]
        if px == 0 and py == 0:
            continue
        ei = entities[i]
        new_x = ei.x + px
        new_y = ei.y + py
        tile_x = new_x // MILLI_TILES_PER_TILE
        tile_y = new_y // MILLI_TILES_PER_TILE
        if tilemap.is_walkable(tile_x, tile_y):
            ei.x = new_x
            ei.y = new_y
