"""Placeholder renderer for Phase 1.

Draws entities as colored circles on a blank background.
Shows debug overlay with tick, connection status, and FPS.
Interpolates entity positions between ticks for smooth movement.
"""

from __future__ import annotations

import pygame

from src.config import (
    COLOR_BG,
    COLOR_DEBUG_TEXT,
    COLOR_PLAYER_1,
    COLOR_PLAYER_2,
    MILLI_TILES_PER_TILE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from src.simulation.state import Entity, GameState

PLAYER_COLORS = {0: COLOR_PLAYER_1, 1: COLOR_PLAYER_2}
ANT_RADIUS = 8


class Renderer:
    """Draws the game state to the screen."""

    def __init__(self, screen: pygame.Surface, tile_size: int) -> None:
        self._screen = screen
        self._tile_size = tile_size
        self._font = pygame.font.SysFont("monospace", 16)

    def draw(
        self,
        state: GameState,
        prev_entities: list[tuple[int, int]] | None,
        interp: float,
        debug_info: dict[str, str],
    ) -> None:
        """Draw one frame.

        Args:
            state: Current game state.
            prev_entities: Previous tick positions [(x,y), ...] for interpolation.
                           Same order as state.entities. None to skip interpolation.
            interp: Interpolation factor [0.0, 1.0] between prev and current tick.
            debug_info: Key-value pairs to show in debug overlay.
        """
        self._screen.fill(COLOR_BG)
        self._draw_grid()
        self._draw_entities(state, prev_entities, interp)
        self._draw_debug(debug_info)
        pygame.display.flip()

    def _draw_grid(self) -> None:
        """Draw a subtle grid for spatial reference."""
        grid_color = (55, 45, 35)
        for x in range(0, SCREEN_WIDTH, self._tile_size):
            pygame.draw.line(self._screen, grid_color, (x, 0), (x, SCREEN_HEIGHT))
        for y in range(0, SCREEN_HEIGHT, self._tile_size):
            pygame.draw.line(self._screen, grid_color, (0, y), (SCREEN_WIDTH, y))

    def _draw_entities(
        self,
        state: GameState,
        prev_positions: list[tuple[int, int]] | None,
        interp: float,
    ) -> None:
        for i, entity in enumerate(state.entities):
            if prev_positions is not None and i < len(prev_positions):
                # Interpolate between previous and current position
                px, py = prev_positions[i]
                draw_x = int(px + (entity.x - px) * interp)
                draw_y = int(py + (entity.y - py) * interp)
            else:
                draw_x = entity.x
                draw_y = entity.y

            # Convert milli-tiles to screen pixels
            sx = draw_x * self._tile_size // MILLI_TILES_PER_TILE
            sy = draw_y * self._tile_size // MILLI_TILES_PER_TILE

            color = PLAYER_COLORS.get(entity.player_id, (200, 200, 200))
            pygame.draw.circle(self._screen, color, (sx, sy), ANT_RADIUS)
            # Draw a darker outline
            pygame.draw.circle(self._screen, (0, 0, 0), (sx, sy), ANT_RADIUS, 2)

            # Draw target indicator if moving
            if entity.is_moving:
                tx = entity.target_x * self._tile_size // MILLI_TILES_PER_TILE
                ty = entity.target_y * self._tile_size // MILLI_TILES_PER_TILE
                target_color = tuple(c // 2 for c in color)
                pygame.draw.circle(self._screen, target_color, (tx, ty), 4)
                pygame.draw.line(self._screen, target_color, (sx, sy), (tx, ty), 1)

    def _draw_debug(self, debug_info: dict[str, str]) -> None:
        y = 5
        for key, value in debug_info.items():
            text = f"{key}: {value}"
            surface = self._font.render(text, True, COLOR_DEBUG_TEXT)
            self._screen.blit(surface, (5, y))
            y += 20
