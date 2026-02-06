"""Game renderer — draws tiles, entities, and debug overlay.

Renders the tile map as a pre-generated surface, then draws entities
on top with position interpolation. Supports a camera offset for
scrolling the viewport across the map.
"""

from __future__ import annotations

import math

import pygame

from src.config import (
    COLOR_BG,
    COLOR_PLAYER_1,
    COLOR_PLAYER_2,
    MILLI_TILES_PER_TILE,
    TILE_RENDER_SIZE,
)
from src.rendering.hud import HUD
from src.simulation.state import Entity, EntityState, EntityType, GameState
from src.simulation.tilemap import TileMap, TileType
from src.simulation.visibility import UNEXPLORED, FOG, VISIBLE

PLAYER_COLORS = {0: COLOR_PLAYER_1, 1: COLOR_PLAYER_2}
ANT_RADIUS = 5
HIVE_RADIUS = 12
HIVE_SITE_RADIUS = 8
MAX_ENTITY_RADIUS = 20  # for culling (mantis arms extend far)


class Renderer:
    """Draws the game state to the screen."""

    def __init__(self, screen: pygame.Surface, tilemap: TileMap | None = None) -> None:
        self._screen = screen
        self._tile_size = TILE_RENDER_SIZE
        self._font = pygame.font.SysFont("monospace", 16)
        self._map_surface: pygame.Surface | None = None
        self._fog_surface = pygame.Surface(
            (screen.get_width(), screen.get_height()), pygame.SRCALPHA,
        )
        self._hud: HUD | None = None
        if tilemap is not None:
            self._build_map_surface(tilemap)
            self._hud = HUD(screen, tilemap)

    @property
    def hud(self) -> HUD | None:
        return self._hud

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
        player_id: int = 0,
        selected_ids: set[int] | None = None,
        drag_rect: tuple[int, int, int, int] | None = None,
    ) -> None:
        """Draw one frame."""
        self._screen.fill(COLOR_BG)
        self._draw_tiles(camera_x, camera_y)
        self._draw_entities(
            state, prev_entities, interp, camera_x, camera_y, player_id,
            selected_ids or set(),
        )
        self._draw_fog(state, camera_x, camera_y, player_id)
        if drag_rect:
            self._draw_drag_rect(drag_rect)
        if self._hud:
            self._hud.draw(
                state, player_id, camera_x, camera_y,
                self._tile_size, selected_ids or set(), debug_info,
            )
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

    def _draw_fog(
        self,
        state: GameState,
        camera_x: int,
        camera_y: int,
        player_id: int,
    ) -> None:
        """Draw fog of war overlay. UNEXPLORED=black, FOG=semi-transparent."""
        ts = self._tile_size
        sw = self._screen.get_width()
        sh = self._screen.get_height()
        vis_map = state.visibility

        fog = self._fog_surface
        fog.fill((0, 0, 0, 0))

        start_tx = camera_x // ts
        start_ty = camera_y // ts
        end_tx = (camera_x + sw) // ts + 1
        end_ty = (camera_y + sh) // ts + 1

        for ty in range(start_ty, end_ty):
            for tx in range(start_tx, end_tx):
                vis = vis_map.get_visibility(player_id, tx, ty)
                if vis == VISIBLE:
                    continue
                px = tx * ts - camera_x
                py = ty * ts - camera_y
                if vis == UNEXPLORED:
                    pygame.draw.rect(fog, (0, 0, 0, 255), (px, py, ts, ts))
                else:  # FOG
                    pygame.draw.rect(fog, (0, 0, 0, 140), (px, py, ts, ts))

        self._screen.blit(fog, (0, 0))

    def _draw_entities(
        self,
        state: GameState,
        prev_positions: list[tuple[int, int]] | None,
        interp: float,
        camera_x: int,
        camera_y: int,
        player_id: int = 0,
        selected_ids: set[int] | None = None,
    ) -> None:
        sw = self._screen.get_width()
        sh = self._screen.get_height()
        r = MAX_ENTITY_RADIUS
        vis_map = state.visibility

        for i, entity in enumerate(state.entities):
            if prev_positions is not None and i < len(prev_positions):
                px, py = prev_positions[i]
                draw_x = int(px + (entity.x - px) * interp)
                draw_y = int(py + (entity.y - py) * interp)
            else:
                draw_x = entity.x
                draw_y = entity.y

            # Hide non-own entities in non-VISIBLE tiles
            if entity.player_id != player_id:
                tile_x = draw_x // MILLI_TILES_PER_TILE
                tile_y = draw_y // MILLI_TILES_PER_TILE
                if vis_map.get_visibility(player_id, tile_x, tile_y) != VISIBLE:
                    continue

            # Convert milli-tiles to screen pixels, apply camera offset
            sx = draw_x * self._tile_size // MILLI_TILES_PER_TILE - camera_x
            sy = draw_y * self._tile_size // MILLI_TILES_PER_TILE - camera_y

            # Cull off-screen entities
            if sx < -r or sx > sw + r or sy < -r or sy > sh + r:
                continue

            self._draw_entity(entity, sx, sy, camera_x, camera_y)

            # Selection highlight
            if selected_ids and entity.entity_id in selected_ids:
                pygame.draw.circle(
                    self._screen, (0, 220, 0), (sx, sy), ANT_RADIUS + 8, 2,
                )

            # Draw target indicator if moving
            if entity.is_moving and entity.player_id >= 0:
                tx = entity.target_x * self._tile_size // MILLI_TILES_PER_TILE - camera_x
                ty = entity.target_y * self._tile_size // MILLI_TILES_PER_TILE - camera_y
                color = PLAYER_COLORS.get(entity.player_id, (200, 200, 200))
                target_color = tuple(c // 2 for c in color)
                pygame.draw.circle(self._screen, target_color, (tx, ty), 4)
                pygame.draw.line(self._screen, target_color, (sx, sy), (tx, ty), 1)

    def _draw_drag_rect(self, drag_rect: tuple[int, int, int, int]) -> None:
        """Draw the selection drag rectangle (green translucent)."""
        x1, y1, x2, y2 = drag_rect
        rx = min(x1, x2)
        ry = min(y1, y2)
        rw = abs(x2 - x1)
        rh = abs(y2 - y1)
        if rw < 2 or rh < 2:
            return
        rect_surf = pygame.Surface((rw, rh), pygame.SRCALPHA)
        rect_surf.fill((0, 200, 0, 40))
        self._screen.blit(rect_surf, (rx, ry))
        pygame.draw.rect(self._screen, (0, 220, 0), (rx, ry, rw, rh), 1)

    def _draw_entity(
        self, entity: Entity, sx: int, sy: int,
        camera_x: int, camera_y: int,
    ) -> None:
        """Draw a single entity at screen position (sx, sy)."""
        etype = entity.entity_type
        s = self._screen

        if etype == EntityType.ANT:
            _draw_ant(s, sx, sy, entity, large=False)
        elif etype == EntityType.QUEEN:
            _draw_ant(s, sx, sy, entity, large=True)
        elif etype == EntityType.HIVE:
            color = PLAYER_COLORS.get(entity.player_id, (200, 200, 200))
            _draw_hexagon(s, sx, sy, 16, color)
            _draw_hexagon(s, sx, sy, 8, _darken(color, 40))
            _draw_hexagon(s, sx, sy, 16, (0, 0, 0), width=2)
        elif etype == EntityType.HIVE_SITE:
            _draw_hexagon(s, sx, sy, 12, (100, 100, 100))
            _draw_hexagon(s, sx, sy, 12, (60, 60, 60), width=2)
        elif etype == EntityType.CORPSE:
            _draw_corpse(s, sx, sy, entity)
        elif etype == EntityType.APHID:
            _draw_aphid(s, sx, sy)
        elif etype == EntityType.BEETLE:
            _draw_beetle(s, sx, sy)
        elif etype == EntityType.MANTIS:
            _draw_mantis(s, sx, sy)

        # Attack flash
        if entity.state == EntityState.ATTACKING:
            pygame.draw.circle(s, (255, 60, 60), (sx, sy), ANT_RADIUS + 6, 2)

        # Health bar for damaged units
        if entity.hp < entity.max_hp and entity.max_hp > 0:
            bar_w, bar_h = 20, 3
            bx = sx - bar_w // 2
            by = sy - 18
            pygame.draw.rect(s, (60, 0, 0), (bx, by, bar_w, bar_h))
            fill = max(1, entity.hp * bar_w // entity.max_hp)
            pygame.draw.rect(s, (0, 200, 0), (bx, by, fill, bar_h))



def _draw_hexagon(
    surface: pygame.Surface, cx: int, cy: int, radius: int,
    color: tuple, width: int = 0,
) -> None:
    """Draw a hexagon centered at (cx, cy)."""
    points = []
    for i in range(6):
        angle = math.pi / 3 * i - math.pi / 6
        px = cx + int(radius * math.cos(angle))
        py = cy + int(radius * math.sin(angle))
        points.append((px, py))
    pygame.draw.polygon(surface, color, points, width)


def _darken(color: tuple, amount: int) -> tuple:
    return tuple(max(0, c - amount) for c in color)


def _draw_ant(
    surface: pygame.Surface, sx: int, sy: int,
    entity: Entity, large: bool,
) -> None:
    """Draw an ant (or queen) with body segments, legs, and antennae."""
    color = PLAYER_COLORS.get(entity.player_id, (200, 200, 200))
    outline = _darken(color, 60)

    if large:
        # Queen: bigger body
        body_w, body_h = 12, 16
        head_r = 5
        head_off = 12
        leg_len = 8
        leg_spread = 5
    else:
        body_w, body_h = 8, 11
        head_r = 3
        head_off = 8
        leg_len = 6
        leg_spread = 4

    # Abdomen (rear oval)
    pygame.draw.ellipse(surface, color,
                        (sx - body_w // 2, sy - 2, body_w, body_h))
    pygame.draw.ellipse(surface, outline,
                        (sx - body_w // 2, sy - 2, body_w, body_h), 1)

    # Thorax (middle small circle)
    thorax_y = sy - 2
    pygame.draw.circle(surface, color, (sx, thorax_y), body_w // 3 + 1)

    # Head
    head_y = sy - head_off
    pygame.draw.circle(surface, color, (sx, head_y), head_r)
    pygame.draw.circle(surface, outline, (sx, head_y), head_r, 1)

    # Legs (3 pairs from thorax)
    for dy_off in (-2, 1, 4):
        ly = thorax_y + dy_off
        # Left leg
        pygame.draw.line(surface, outline,
                         (sx - 2, ly),
                         (sx - leg_len, ly + leg_spread), 1)
        # Right leg
        pygame.draw.line(surface, outline,
                         (sx + 2, ly),
                         (sx + leg_len, ly + leg_spread), 1)

    # Antennae
    pygame.draw.line(surface, outline,
                     (sx - 1, head_y - head_r),
                     (sx - 5, head_y - head_r - 6), 1)
    pygame.draw.line(surface, outline,
                     (sx + 1, head_y - head_r),
                     (sx + 5, head_y - head_r - 6), 1)

    # Queen crown (3 gold spikes)
    if large:
        gold = (255, 215, 0)
        for dx in (-3, 0, 3):
            pygame.draw.polygon(surface, gold, [
                (sx + dx - 2, head_y - head_r - 2),
                (sx + dx + 2, head_y - head_r - 2),
                (sx + dx, head_y - head_r - 7),
            ])

    # Jelly indicator — only show when actually carrying jelly
    if entity.carrying > 0:
        pygame.draw.circle(surface, (240, 220, 60), (sx, sy + body_h + 2), 3)


def _draw_corpse(
    surface: pygame.Surface, sx: int, sy: int, entity: Entity,
) -> None:
    """Draw a dead ant corpse — legs splayed out."""
    gray = max(80, 180 - entity.carrying * 5)
    c = (gray, gray - 10, gray - 20)
    # Small body
    pygame.draw.ellipse(surface, c, (sx - 4, sy - 3, 8, 6))
    # Splayed legs
    for angle_deg in (30, 90, 150):
        rad = math.radians(angle_deg)
        dx = int(6 * math.cos(rad))
        dy = int(6 * math.sin(rad))
        pygame.draw.line(surface, c, (sx, sy), (sx + dx, sy + dy), 1)
        pygame.draw.line(surface, c, (sx, sy), (sx - dx, sy + dy), 1)


def _draw_aphid(surface: pygame.Surface, sx: int, sy: int) -> None:
    """Draw a small green aphid."""
    body_color = (110, 190, 80)
    dark = (70, 140, 50)
    # Plump oval body
    pygame.draw.ellipse(surface, body_color, (sx - 4, sy - 3, 8, 6))
    pygame.draw.ellipse(surface, dark, (sx - 4, sy - 3, 8, 6), 1)
    # Tiny head
    pygame.draw.circle(surface, body_color, (sx, sy - 4), 2)
    # Antennae
    pygame.draw.line(surface, dark, (sx - 1, sy - 6), (sx - 3, sy - 9), 1)
    pygame.draw.line(surface, dark, (sx + 1, sy - 6), (sx + 3, sy - 9), 1)


def _draw_beetle(surface: pygame.Surface, sx: int, sy: int) -> None:
    """Draw a beetle with shell halves."""
    shell = (140, 100, 50)
    dark = (80, 55, 25)
    head_color = (60, 40, 20)
    # Shell (oval)
    pygame.draw.ellipse(surface, shell, (sx - 7, sy - 5, 14, 12))
    pygame.draw.ellipse(surface, dark, (sx - 7, sy - 5, 14, 12), 1)
    # Shell split line
    pygame.draw.line(surface, dark, (sx, sy - 5), (sx, sy + 7), 1)
    # Head
    pygame.draw.circle(surface, head_color, (sx, sy - 7), 3)
    # Pincers
    pygame.draw.line(surface, head_color, (sx - 2, sy - 9), (sx - 5, sy - 12), 2)
    pygame.draw.line(surface, head_color, (sx + 2, sy - 9), (sx + 5, sy - 12), 2)
    # Legs
    for dy in (-2, 1, 4):
        pygame.draw.line(surface, dark, (sx - 6, sy + dy), (sx - 10, sy + dy + 3), 1)
        pygame.draw.line(surface, dark, (sx + 6, sy + dy), (sx + 10, sy + dy + 3), 1)


def _draw_mantis(surface: pygame.Surface, sx: int, sy: int) -> None:
    """Draw a praying mantis — elongated body with raptorial arms."""
    body = (50, 160, 50)
    dark = (30, 100, 30)
    eye_color = (200, 200, 40)
    # Elongated abdomen
    pygame.draw.ellipse(surface, body, (sx - 5, sy, 10, 16))
    pygame.draw.ellipse(surface, dark, (sx - 5, sy, 10, 16), 1)
    # Thorax
    pygame.draw.ellipse(surface, body, (sx - 4, sy - 6, 8, 8))
    # Triangular head
    pygame.draw.polygon(surface, body, [
        (sx - 5, sy - 8),
        (sx + 5, sy - 8),
        (sx, sy - 15),
    ])
    pygame.draw.polygon(surface, dark, [
        (sx - 5, sy - 8),
        (sx + 5, sy - 8),
        (sx, sy - 15),
    ], 1)
    # Eyes
    pygame.draw.circle(surface, eye_color, (sx - 3, sy - 10), 2)
    pygame.draw.circle(surface, eye_color, (sx + 3, sy - 10), 2)
    # Raptorial front arms (bent)
    pygame.draw.line(surface, dark, (sx - 4, sy - 5), (sx - 10, sy - 12), 2)
    pygame.draw.line(surface, dark, (sx - 10, sy - 12), (sx - 8, sy - 18), 2)
    pygame.draw.line(surface, dark, (sx + 4, sy - 5), (sx + 10, sy - 12), 2)
    pygame.draw.line(surface, dark, (sx + 10, sy - 12), (sx + 8, sy - 18), 2)
    # Back legs
    for dy in (2, 6):
        pygame.draw.line(surface, dark, (sx - 4, sy + dy), (sx - 9, sy + dy + 5), 1)
        pygame.draw.line(surface, dark, (sx + 4, sy + dy), (sx + 9, sy + dy + 5), 1)


def _clamp(val: int, lo: int, hi: int) -> int:
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val
