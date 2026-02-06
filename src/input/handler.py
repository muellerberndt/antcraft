"""Input handler — converts PyGame events to Commands.

Phase 1: click-to-move. The player's ant follows the mouse click.
"""

from __future__ import annotations

import pygame

from src.config import INPUT_DELAY_TICKS, MILLI_TILES_PER_TILE
from src.simulation.commands import Command, CommandType
from src.simulation.state import GameState


class InputHandler:
    """Converts PyGame mouse/keyboard events into simulation Commands."""

    def __init__(self, player_id: int, tile_size: int) -> None:
        self._player_id = player_id
        self._tile_size = tile_size  # pixels per tile for coord conversion

    def process_events(
        self,
        events: list[pygame.event.Event],
        state: GameState,
        current_tick: int,
    ) -> list[Command]:
        """Process PyGame events and return any Commands generated."""
        commands: list[Command] = []
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                cmd = self._handle_click(event.pos, state, current_tick)
                if cmd is not None:
                    commands.append(cmd)
        return commands

    def _handle_click(
        self,
        screen_pos: tuple[int, int],
        state: GameState,
        current_tick: int,
    ) -> Command | None:
        """Convert a mouse click to a MOVE command for the player's entities."""
        # Convert screen pixels to milli-tiles
        px, py = screen_pos
        target_x = px * MILLI_TILES_PER_TILE // self._tile_size
        target_y = py * MILLI_TILES_PER_TILE // self._tile_size

        # Find all entities owned by this player
        my_entities = [
            e for e in state.entities if e.player_id == self._player_id
        ]
        if not my_entities:
            return None

        return Command(
            command_type=CommandType.MOVE,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=tuple(e.entity_id for e in my_entities),
            target_x=target_x,
            target_y=target_y,
        )
