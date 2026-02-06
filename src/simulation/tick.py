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
from src.simulation.commands import Command, CommandType
from src.simulation.hive import (
    handle_found_hive,
    handle_merge_queen,
    handle_spawn_ant,
    process_hive_mechanics,
)
from src.simulation.pathfinding import find_path
from src.simulation.state import GameState
from src.simulation.wildlife import process_wildlife


def advance_tick(state: GameState, commands: list[Command]) -> None:
    """Advance the simulation by one tick.

    Args:
        state: The current game state (mutated in place).
        commands: All commands for this tick, sorted deterministically.
    """
    _process_commands(state, commands)
    process_wildlife(state)
    _update_movement(state)
    _apply_separation(state)
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


def _handle_move(state: GameState, cmd: Command) -> None:
    """Compute A* path and assign it to entities."""
    # Check if target tile is walkable
    target_tile_x = cmd.target_x // MILLI_TILES_PER_TILE
    target_tile_y = cmd.target_y // MILLI_TILES_PER_TILE
    if not state.tilemap.is_walkable(target_tile_x, target_tile_y):
        return

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
            entity.target_x = cmd.target_x
            entity.target_y = cmd.target_y
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


_SEP_RADIUS_SQ = SEPARATION_RADIUS * SEPARATION_RADIUS


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
