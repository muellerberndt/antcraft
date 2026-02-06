"""Input handler — converts PyGame events to Commands.

Left click/drag: select units (delegates to SelectionManager).
Right click: issue MOVE command for selected units.
"""

from __future__ import annotations

import pygame

from src.config import INPUT_DELAY_TICKS, MILLI_TILES_PER_TILE, SELECTION_THRESHOLD
from src.input.selection import SelectionManager
from src.simulation.commands import Command, CommandType
from src.simulation.state import GameState


class InputHandler:
    """Converts PyGame mouse/keyboard events into simulation Commands."""

    def __init__(self, player_id: int, tile_size: int) -> None:
        self._player_id = player_id
        self._tile_size = tile_size
        self.selection = SelectionManager()
        # Drag state (screen coords)
        self._drag_start: tuple[int, int] | None = None
        self._drag_current: tuple[int, int] | None = None
        self._dragging = False

    @property
    def drag_rect(self) -> tuple[int, int, int, int] | None:
        """Return the current drag rectangle in screen coords, or None."""
        if self._dragging and self._drag_start and self._drag_current:
            return (*self._drag_start, *self._drag_current)
        return None

    def _screen_to_world(self, sx: int, sy: int, camera_x: int, camera_y: int) -> tuple[int, int]:
        """Convert screen pixel coords to milli-tile world coords."""
        wx = (sx + camera_x) * MILLI_TILES_PER_TILE // self._tile_size
        wy = (sy + camera_y) * MILLI_TILES_PER_TILE // self._tile_size
        return wx, wy

    def process_events(
        self,
        events: list[pygame.event.Event],
        state: GameState,
        current_tick: int,
        camera_x: int = 0,
        camera_y: int = 0,
    ) -> list[Command]:
        """Process PyGame events and return any Commands generated."""
        commands: list[Command] = []
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._drag_start = event.pos
                self._drag_current = event.pos
                self._dragging = False

            elif event.type == pygame.MOUSEMOTION and self._drag_start is not None:
                self._drag_current = event.pos
                dx = event.pos[0] - self._drag_start[0]
                dy = event.pos[1] - self._drag_start[1]
                if dx * dx + dy * dy > SELECTION_THRESHOLD * SELECTION_THRESHOLD:
                    self._dragging = True

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self._drag_start is not None:
                    if self._dragging:
                        self._box_select(
                            self._drag_start, event.pos, state,
                            camera_x, camera_y,
                        )
                    else:
                        self._click_select(
                            event.pos, state, camera_x, camera_y,
                        )
                self._drag_start = None
                self._drag_current = None
                self._dragging = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                cmd = self._handle_right_click(
                    event.pos, state, current_tick, camera_x, camera_y,
                )
                if cmd is not None:
                    commands.append(cmd)

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_s:
                cmd = self._handle_stop(state, current_tick)
                if cmd is not None:
                    commands.append(cmd)

        return commands

    def _click_select(
        self,
        screen_pos: tuple[int, int],
        state: GameState,
        camera_x: int,
        camera_y: int,
    ) -> None:
        """Click-select at screen position."""
        wx, wy = self._screen_to_world(screen_pos[0], screen_pos[1], camera_x, camera_y)
        # Convert pixel threshold to milli-tile threshold
        threshold_mt = SELECTION_THRESHOLD * MILLI_TILES_PER_TILE // self._tile_size
        self.selection.select_at(wx, wy, state.entities, self._player_id, threshold_mt)

    def _box_select(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        state: GameState,
        camera_x: int,
        camera_y: int,
    ) -> None:
        """Box-select from drag start to end."""
        wx1, wy1 = self._screen_to_world(start[0], start[1], camera_x, camera_y)
        wx2, wy2 = self._screen_to_world(end[0], end[1], camera_x, camera_y)
        self.selection.select_in_rect(wx1, wy1, wx2, wy2, state.entities, self._player_id)

    def _handle_right_click(
        self,
        screen_pos: tuple[int, int],
        state: GameState,
        current_tick: int,
        camera_x: int,
        camera_y: int,
    ) -> Command | None:
        """Right click: MOVE command for selected units."""
        if not self.selection.selected_ids:
            return None

        wx, wy = self._screen_to_world(screen_pos[0], screen_pos[1], camera_x, camera_y)

        return Command(
            command_type=CommandType.MOVE,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=tuple(sorted(self.selection.selected_ids)),
            target_x=wx,
            target_y=wy,
        )

    def _handle_stop(self, state: GameState, current_tick: int) -> Command | None:
        """S key: STOP command for selected units."""
        if not self.selection.selected_ids:
            return None

        return Command(
            command_type=CommandType.STOP,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=tuple(sorted(self.selection.selected_ids)),
        )
