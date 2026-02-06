"""Tick logic — advance the simulation by one step.

This is the heart of the deterministic simulation. Both peers call
advance_tick() with the same commands on the same tick, producing
identical game states.

ALL MATH IS INTEGER. No floats anywhere in this module.
"""

from __future__ import annotations

from math import isqrt

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
    """Set target position for entities."""
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
    """Move all entities toward their targets. Integer math only."""
    for entity in state.entities:
        if not entity.is_moving:
            continue

        dx = entity.target_x - entity.x
        dy = entity.target_y - entity.y
        dist_sq = dx * dx + dy * dy
        dist = isqrt(dist_sq)

        if dist <= entity.speed:
            # Close enough — snap to target
            entity.x = entity.target_x
            entity.y = entity.target_y
        else:
            # Move speed units toward target
            entity.x += dx * entity.speed // dist
            entity.y += dy * entity.speed // dist
