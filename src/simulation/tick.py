"""Tick logic — advance the simulation by one step.

This is the heart of the deterministic simulation. Both peers call
advance_tick() with the same commands on the same tick, producing
identical game states.

ALL MATH IS INTEGER. No floats anywhere in this module.
"""

from __future__ import annotations

from math import isqrt

from src.config import MILLI_TILES_PER_TILE
from src.simulation.commands import Command, CommandType
from src.simulation.state import GameState


def advance_tick(state: GameState, commands: list[Command]) -> None:
    """Advance the simulation by one tick.

    Args:
        state: The current game state (mutated in place).
        commands: All commands for this tick, sorted deterministically.
    """
    _process_commands(state, commands)
    _update_movement(state)
    state.tick += 1


def _process_commands(state: GameState, commands: list[Command]) -> None:
    """Apply all commands for this tick to the game state."""
    for cmd in commands:
        if cmd.command_type == CommandType.MOVE:
            _handle_move(state, cmd)
        elif cmd.command_type == CommandType.STOP:
            _handle_stop(state, cmd)


def _handle_move(state: GameState, cmd: Command) -> None:
    """Set target position for entities. Rejects moves to non-walkable tiles."""
    # Check if target tile is walkable
    target_tile_x = cmd.target_x // MILLI_TILES_PER_TILE
    target_tile_y = cmd.target_y // MILLI_TILES_PER_TILE
    if not state.tilemap.is_walkable(target_tile_x, target_tile_y):
        return

    for entity_id in cmd.entity_ids:
        entity = state.get_entity(entity_id)
        if entity is not None and entity.player_id == cmd.player_id:
            entity.target_x = cmd.target_x
            entity.target_y = cmd.target_y


def _handle_stop(state: GameState, cmd: Command) -> None:
    """Stop entities at their current position."""
    for entity_id in cmd.entity_ids:
        entity = state.get_entity(entity_id)
        if entity is not None and entity.player_id == cmd.player_id:
            entity.target_x = entity.x
            entity.target_y = entity.y


def _update_movement(state: GameState) -> None:
    """Move all entities toward their targets. Integer math only.

    Checks tilemap walkability before moving — entities stop at rock tiles.
    This is a simple collision check; proper pathfinding (A*) comes in Task 3.
    """
    tilemap = state.tilemap
    for entity in state.entities:
        if not entity.is_moving:
            continue

        dx = entity.target_x - entity.x
        dy = entity.target_y - entity.y
        dist_sq = dx * dx + dy * dy
        dist = isqrt(dist_sq)

        if dist <= entity.speed:
            new_x = entity.target_x
            new_y = entity.target_y
        else:
            new_x = entity.x + dx * entity.speed // dist
            new_y = entity.y + dy * entity.speed // dist

        # Check if destination tile is walkable
        tile_x = new_x // MILLI_TILES_PER_TILE
        tile_y = new_y // MILLI_TILES_PER_TILE
        if tilemap.is_walkable(tile_x, tile_y):
            entity.x = new_x
            entity.y = new_y
        else:
            # Blocked — stop the entity
            entity.target_x = entity.x
            entity.target_y = entity.y
