"""Game renderer — draws tiles, entities, and debug overlay.

Renders the tile map as a pre-generated surface, then draws entities
on top with position interpolation. Supports a camera offset for
scrolling the viewport across the map.
"""

from __future__ import annotations

import pygame

from src.config import (
    COLOR_BG,
    COLOR_DEBUG_TEXT,
    COLOR_PLAYER_1,
    COLOR_PLAYER_2,
    MILLI_TILES_PER_TILE,
    TILE_RENDER_SIZE,
)
from src.simulation.state import Entity, EntityType, GameState
from src.simulation.tilemap import TileMap, TileType

PLAYER_COLORS = {0: COLOR_PLAYER_1, 1: COLOR_PLAYER_2}
ANT_RADIUS = 5
HIVE_RADIUS = 12
HIVE_SITE_RADIUS = 8
COLOR_HIVE_SITE = (160, 150, 120)  # neutral beige
MAX_ENTITY_RADIUS = HIVE_RADIUS  # for culling


class Renderer:
    """Draws the game state to the screen."""

    def __init__(self, screen: pygame.Surface, tilemap: TileMap | None = None) -> None:
        self._screen = screen
        self._tile_size = TILE_RENDER_SIZE
        self._font = pygame.font.SysFont("monospace", 16)
        self._map_surface: pygame.Surface | None = None
        if tilemap is not None:
            self._build_map_surface(tilemap)

    def _build_map_surface(self, tilemap: TileMap) -> None:
        """Pre-render the entire tile map to a surface."""
        ts = self._tile_size
        w = tilemap.width * ts
        h = tilemap.height * ts
        self._map_surface = pygame.Surface((w, h))

        for y in range(tilemap.height):
            for x in range(tilemap.width):
                tile = tilemap.get_tile(x, y)
                # Deterministic per-tile color variation using a hash
                hval = ((x * 374761393 + y * 668265263) ^ 0xB55A4F09) & 0xFFFFFFFF
                variation = (hval % 21) - 10  # -10 to +10
                fine = ((hval >> 16) % 11) - 5  # -5 to +5 secondary

                if tile == TileType.DIRT:
                    r = _clamp(101 + variation, 0, 255)
                    g = _clamp(76 + variation + fine, 0, 255)
                    b = _clamp(38 + variation // 2, 0, 255)
                    color = (r, g, b)
                    edge_color = (_clamp(r - 12, 0, 255),
                                  _clamp(g - 12, 0, 255),
                                  _clamp(b - 8, 0, 255))
                else:  # ROCK
                    gray = _clamp(78 + variation, 0, 255)
                    color = (gray, _clamp(gray - 3, 0, 255), _clamp(gray - 1, 0, 255))
                    edge_color = (_clamp(gray - 15, 0, 255),
                                  _clamp(gray - 18, 0, 255),
                                  _clamp(gray - 14, 0, 255))

                rect = pygame.Rect(x * ts, y * ts, ts, ts)
                pygame.draw.rect(self._map_surface, color, rect)
                # Subtle edge shading (bottom and right) for depth
                pygame.draw.line(self._map_surface, edge_color,
                                 (x * ts, (y + 1) * ts - 1),
                                 ((x + 1) * ts - 1, (y + 1) * ts - 1))
                pygame.draw.line(self._map_surface, edge_color,
                                 ((x + 1) * ts - 1, y * ts),
                                 ((x + 1) * ts - 1, (y + 1) * ts - 1))

    def draw(
        self,
        state: GameState,
        prev_entities: list[tuple[int, int]] | None,
        interp: float,
        debug_info: dict[str, str],
        camera_x: int = 0,
        camera_y: int = 0,
    ) -> None:
        """Draw one frame.

        Args:
            state: Current game state.
            prev_entities: Previous tick positions for interpolation.
            interp: Interpolation factor [0.0, 1.0].
            debug_info: Key-value pairs for debug overlay.
            camera_x: Camera offset in pixels (horizontal).
            camera_y: Camera offset in pixels (vertical).
        """
        self._screen.fill(COLOR_BG)
        self._draw_tiles(camera_x, camera_y)
        self._draw_entities(state, prev_entities, interp, camera_x, camera_y)
        self._draw_debug(debug_info)
        pygame.display.flip()

    def _draw_tiles(self, camera_x: int, camera_y: int) -> None:
        """Blit the pre-rendered map surface with camera offset."""
        if self._map_surface is None:
            return
        sw = self._screen.get_width()
        sh = self._screen.get_height()
        # Source rect: which part of the map to show
        src = pygame.Rect(camera_x, camera_y, sw, sh)
        self._screen.blit(self._map_surface, (0, 0), src)

    def _draw_entities(
        self,
        state: GameState,
        prev_positions: list[tuple[int, int]] | None,
        interp: float,
        camera_x: int,
        camera_y: int,
    ) -> None:
        sw = self._screen.get_width()
        sh = self._screen.get_height()
        r = MAX_ENTITY_RADIUS

        for i, entity in enumerate(state.entities):
            if prev_positions is not None and i < len(prev_positions):
                px, py = prev_positions[i]
                draw_x = int(px + (entity.x - px) * interp)
                draw_y = int(py + (entity.y - py) * interp)
            else:
                draw_x = entity.x
                draw_y = entity.y

            # Convert milli-tiles to screen pixels, apply camera offset
            sx = draw_x * self._tile_size // MILLI_TILES_PER_TILE - camera_x
            sy = draw_y * self._tile_size // MILLI_TILES_PER_TILE - camera_y

            # Cull off-screen entities
            if sx < -r or sx > sw + r or sy < -r or sy > sh + r:
                continue

            self._draw_entity(entity, sx, sy)

            # Draw target indicator if moving
            if entity.is_moving:
                tx = entity.target_x * self._tile_size // MILLI_TILES_PER_TILE - camera_x
                ty = entity.target_y * self._tile_size // MILLI_TILES_PER_TILE - camera_y
                color = PLAYER_COLORS.get(entity.player_id, (200, 200, 200))
                target_color = tuple(c // 2 for c in color)
                pygame.draw.circle(self._screen, target_color, (tx, ty), 4)
                pygame.draw.line(self._screen, target_color, (sx, sy), (tx, ty), 1)

    def _draw_entity(self, entity: Entity, sx: int, sy: int) -> None:
        """Draw a single entity at screen position (sx, sy)."""
        color = PLAYER_COLORS.get(entity.player_id, (200, 200, 200))

        if entity.entity_type == EntityType.HIVE:
            # Large filled circle with thicker outline
            pygame.draw.circle(self._screen, color, (sx, sy), HIVE_RADIUS)
            pygame.draw.circle(self._screen, (0, 0, 0), (sx, sy), HIVE_RADIUS, 2)
            # Inner dot to distinguish from ants
            pygame.draw.circle(self._screen, (255, 255, 255), (sx, sy), 3)

        elif entity.entity_type == EntityType.HIVE_SITE:
            # Neutral diamond marker
            pts = [(sx, sy - HIVE_SITE_RADIUS), (sx + HIVE_SITE_RADIUS, sy),
                   (sx, sy + HIVE_SITE_RADIUS), (sx - HIVE_SITE_RADIUS, sy)]
            pygame.draw.polygon(self._screen, COLOR_HIVE_SITE, pts, 2)

        elif entity.entity_type == EntityType.ANT:
            # Small player-colored circle
            pygame.draw.circle(self._screen, color, (sx, sy), ANT_RADIUS)
            pygame.draw.circle(self._screen, (0, 0, 0), (sx, sy), ANT_RADIUS, 1)

        else:
            # Fallback for other types (corpses, wildlife, queens)
            pygame.draw.circle(self._screen, color, (sx, sy), ANT_RADIUS)
            pygame.draw.circle(self._screen, (0, 0, 0), (sx, sy), ANT_RADIUS, 2)

    def _draw_debug(self, debug_info: dict[str, str]) -> None:
        y = 5
        for key, value in debug_info.items():
            text = f"{key}: {value}"
            surface = self._font.render(text, True, COLOR_DEBUG_TEXT)
            self._screen.blit(surface, (5, y))
            y += 20


def _clamp(val: int, lo: int, hi: int) -> int:
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val
