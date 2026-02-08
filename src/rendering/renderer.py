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
ANT_RADIUS = 10
HIVE_RADIUS = 24
HIVE_SITE_RADIUS = 16
MAX_ENTITY_RADIUS = 40  # for culling (mantis arms extend far)


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
        """Pre-render the entire tile map to a surface.

        Uses smooth color blending for dirt and neighbor-aware cliff
        rendering for rock to eliminate visible grid lines.
        """
        ts = self._tile_size
        w = tilemap.width * ts
        h = tilemap.height * ts
        self._map_surface = pygame.Surface((w, h))

        # Pre-compute per-tile hash values for smooth blending
        tw, th = tilemap.width, tilemap.height
        hashes: list[int] = [0] * (tw * th)
        for y in range(th):
            for x in range(tw):
                hashes[y * tw + x] = (
                    (x * 374761393 + y * 668265263) ^ 0xB55A4F09
                ) & 0xFFFFFFFF

        for y in range(th):
            for x in range(tw):
                tile = tilemap.get_tile(x, y)
                if tile == TileType.DIRT:
                    self._render_dirt_tile(x, y, tilemap, ts, hashes, tw, th)
                else:
                    self._render_rock_tile(x, y, tilemap, ts, hashes, tw, th)

    def _render_dirt_tile(
        self, x: int, y: int, tilemap: TileMap, ts: int,
        hashes: list[int], tw: int, th: int,
    ) -> None:
        """Render a dirt tile with pixel-grain texture."""
        surf = self._map_surface
        hval = hashes[y * tw + x]
        variation = (hval % 21) - 10
        fine = ((hval >> 16) % 11) - 5

        px0 = x * ts
        py0 = y * ts

        # Base fill color
        base_r = _clamp(101 + variation, 0, 255)
        base_g = _clamp(76 + variation + fine, 0, 255)
        base_b = _clamp(38 + variation // 2, 0, 255)
        pygame.draw.rect(surf, (base_r, base_g, base_b),
                         (px0, py0, ts, ts))

        # Per-pixel grain: scatter ~30% of pixels with slight variation
        # Uses a fast deterministic hash per pixel for the noise pattern
        seed = hval
        for py in range(ts):
            row_seed = ((seed + py * 668265263) * 374761393) & 0xFFFFFFFF
            for px_i in range(ts):
                # Fast per-pixel hash
                ph = ((row_seed + px_i * 2654435761) ^ 0xB55A4F09) & 0xFFFFFFFF
                # Only modify ~40% of pixels for a grainy look
                if (ph & 7) > 2:
                    continue
                grain = ((ph >> 3) % 13) - 6  # -6 to +6
                r = _clamp(base_r + grain, 0, 255)
                g = _clamp(base_g + grain, 0, 255)
                b = _clamp(base_b + grain // 2, 0, 255)
                surf.set_at((px0 + px_i, py0 + py), (r, g, b))

        # Pebble dots near rock edges
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if tilemap.get_tile(nx, ny) == TileType.ROCK:
                for i in range(3):
                    ph = ((hval * (i + 7) * 1103515245 + ny * 31) >> 4) & 0xFFFFFF
                    if nx < x:
                        pdx = (ph % 6)
                        pdy = (ph >> 8) % ts
                    elif nx > x:
                        pdx = ts - 1 - (ph % 6)
                        pdy = (ph >> 8) % ts
                    elif ny < y:
                        pdx = (ph >> 8) % ts
                        pdy = (ph % 6)
                    else:
                        pdx = (ph >> 8) % ts
                        pdy = ts - 1 - (ph % 6)
                    gray = 75 + ((ph >> 16) % 20)
                    surf.set_at((px0 + pdx, py0 + pdy), (gray, gray - 5, gray - 3))

    def _render_rock_tile(
        self, x: int, y: int, tilemap: TileMap, ts: int,
        hashes: list[int], tw: int, th: int,
    ) -> None:
        """Render a rock tile with neighbor-aware cliff edges."""
        surf = self._map_surface
        hval = hashes[y * tw + x]
        variation = (hval % 21) - 10

        px0 = x * ts
        py0 = y * ts

        # Check cardinal neighbors (True = dirt/exposed)
        n_dirt = tilemap.get_tile(x, y - 1) == TileType.DIRT
        s_dirt = tilemap.get_tile(x, y + 1) == TileType.DIRT
        w_dirt = tilemap.get_tile(x - 1, y) == TileType.DIRT
        e_dirt = tilemap.get_tile(x + 1, y) == TileType.DIRT

        is_interior = not (n_dirt or s_dirt or w_dirt or e_dirt)

        # Base rock color — interior is darker
        if is_interior:
            base_gray = _clamp(62 + variation, 0, 255)
        else:
            base_gray = _clamp(78 + variation, 0, 255)

        base_color = (base_gray, _clamp(base_gray - 3, 0, 255),
                      _clamp(base_gray - 1, 0, 255))
        rect = pygame.Rect(px0, py0, ts, ts)
        pygame.draw.rect(surf, base_color, rect)

        # Cliff edges on exposed sides
        edge_w = max(3, ts // 8)  # 4px at ts=32

        if n_dirt:
            # Top edge: dark shadow at top, lighter below
            shadow = (_clamp(base_gray - 25, 0, 255),
                      _clamp(base_gray - 28, 0, 255),
                      _clamp(base_gray - 22, 0, 255))
            highlight = (_clamp(base_gray + 8, 0, 255),
                         _clamp(base_gray + 5, 0, 255),
                         _clamp(base_gray + 7, 0, 255))
            pygame.draw.rect(surf, shadow, (px0, py0, ts, 2))
            pygame.draw.rect(surf, highlight, (px0, py0 + 2, ts, edge_w - 2))

        if s_dirt:
            # Bottom edge: lighter highlight at bottom
            highlight = (_clamp(base_gray + 12, 0, 255),
                         _clamp(base_gray + 9, 0, 255),
                         _clamp(base_gray + 10, 0, 255))
            pygame.draw.rect(surf, highlight,
                             (px0, py0 + ts - edge_w, ts, edge_w))

        if w_dirt:
            # Left edge: shadow
            shadow = (_clamp(base_gray - 18, 0, 255),
                      _clamp(base_gray - 20, 0, 255),
                      _clamp(base_gray - 16, 0, 255))
            pygame.draw.rect(surf, shadow, (px0, py0, 2, ts))
            lighter = (_clamp(base_gray + 4, 0, 255),
                       _clamp(base_gray + 1, 0, 255),
                       _clamp(base_gray + 3, 0, 255))
            pygame.draw.rect(surf, lighter, (px0 + 2, py0, edge_w - 2, ts))

        if e_dirt:
            # Right edge: highlight
            highlight = (_clamp(base_gray + 6, 0, 255),
                         _clamp(base_gray + 3, 0, 255),
                         _clamp(base_gray + 5, 0, 255))
            pygame.draw.rect(surf, highlight,
                             (px0 + ts - edge_w, py0, edge_w, ts))

        # Corner darkening where two edges meet
        corner_size = edge_w
        nw_dirt = tilemap.get_tile(x - 1, y - 1) == TileType.DIRT
        ne_dirt = tilemap.get_tile(x + 1, y - 1) == TileType.DIRT
        sw_dirt = tilemap.get_tile(x - 1, y + 1) == TileType.DIRT
        se_dirt = tilemap.get_tile(x + 1, y + 1) == TileType.DIRT

        corner_dark = (_clamp(base_gray - 30, 0, 255),
                       _clamp(base_gray - 33, 0, 255),
                       _clamp(base_gray - 28, 0, 255))

        if n_dirt and w_dirt:
            pygame.draw.rect(surf, corner_dark,
                             (px0, py0, corner_size, corner_size))
        if n_dirt and e_dirt:
            pygame.draw.rect(surf, corner_dark,
                             (px0 + ts - corner_size, py0,
                              corner_size, corner_size))
        if s_dirt and w_dirt:
            pygame.draw.rect(surf, corner_dark,
                             (px0, py0 + ts - corner_size,
                              corner_size, corner_size))
        if s_dirt and e_dirt:
            pygame.draw.rect(surf, corner_dark,
                             (px0 + ts - corner_size,
                              py0 + ts - corner_size,
                              corner_size, corner_size))

        # Inner corner shadows (rock surrounded on 3 sides, diagonal exposed)
        if not n_dirt and not w_dirt and nw_dirt:
            pygame.draw.rect(surf, corner_dark, (px0, py0, 3, 3))
        if not n_dirt and not e_dirt and ne_dirt:
            pygame.draw.rect(surf, corner_dark, (px0 + ts - 3, py0, 3, 3))
        if not s_dirt and not w_dirt and sw_dirt:
            pygame.draw.rect(surf, corner_dark, (px0, py0 + ts - 3, 3, 3))
        if not s_dirt and not e_dirt and se_dirt:
            pygame.draw.rect(surf, corner_dark,
                             (px0 + ts - 3, py0 + ts - 3, 3, 3))

        # Crack texture on rock surface
        for i in range(2):
            ch = ((hval * (i + 3) * 2654435761) >> 8) & 0xFFFFFF
            cx = (ch % (ts - 6)) + 3
            cy = ((ch >> 8) % (ts - 6)) + 3
            clen = 3 + ((ch >> 16) % 5)
            cdir = (ch >> 20) % 4
            crack_color = (_clamp(base_gray - 20, 0, 255),
                           _clamp(base_gray - 22, 0, 255),
                           _clamp(base_gray - 18, 0, 255))
            if cdir == 0:  # horizontal
                pygame.draw.line(surf, crack_color,
                                 (px0 + cx, py0 + cy),
                                 (px0 + min(cx + clen, ts - 1), py0 + cy), 1)
            elif cdir == 1:  # vertical
                pygame.draw.line(surf, crack_color,
                                 (px0 + cx, py0 + cy),
                                 (px0 + cx, py0 + min(cy + clen, ts - 1)), 1)
            else:  # diagonal
                pygame.draw.line(surf, crack_color,
                                 (px0 + cx, py0 + cy),
                                 (px0 + min(cx + clen, ts - 1),
                                  py0 + min(cy + clen, ts - 1)), 1)

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
                    self._screen, (0, 220, 0), (sx, sy), ANT_RADIUS + 16, 3,
                )

            # Draw target indicator if moving
            if entity.is_moving and entity.player_id >= 0:
                tx = entity.target_x * self._tile_size // MILLI_TILES_PER_TILE - camera_x
                ty = entity.target_y * self._tile_size // MILLI_TILES_PER_TILE - camera_y
                color = PLAYER_COLORS.get(entity.player_id, (200, 200, 200))
                target_color = tuple(c // 2 for c in color)
                pygame.draw.circle(self._screen, target_color, (tx, ty), 8)
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
            _draw_hexagon(s, sx, sy, 32, color)
            _draw_hexagon(s, sx, sy, 16, _darken(color, 40))
            _draw_hexagon(s, sx, sy, 32, (0, 0, 0), width=3)
        elif etype == EntityType.HIVE_SITE:
            _draw_hexagon(s, sx, sy, 24, (100, 100, 100))
            _draw_hexagon(s, sx, sy, 24, (60, 60, 60), width=3)
        elif etype == EntityType.CORPSE:
            _draw_corpse(s, sx, sy, entity)
        elif etype == EntityType.APHID:
            _draw_aphid(s, sx, sy)
        elif etype == EntityType.BEETLE:
            _draw_beetle(s, sx, sy)
        elif etype == EntityType.MANTIS:
            _draw_mantis(s, sx, sy)
        elif etype == EntityType.SPITTER:
            _draw_spitter(s, sx, sy, entity)

        # Attack flash
        if entity.state == EntityState.ATTACKING:
            pygame.draw.circle(s, (255, 60, 60), (sx, sy), ANT_RADIUS + 12, 3)

        # Health bar for damaged units
        if entity.hp < entity.max_hp and entity.max_hp > 0:
            bar_w, bar_h = 40, 5
            bx = sx - bar_w // 2
            by = sy - 36
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
        body_w, body_h = 24, 32
        head_r = 10
        head_off = 24
        leg_len = 16
        leg_spread = 10
    else:
        body_w, body_h = 16, 22
        head_r = 6
        head_off = 16
        leg_len = 12
        leg_spread = 8

    # Abdomen (rear oval)
    pygame.draw.ellipse(surface, color,
                        (sx - body_w // 2, sy - 4, body_w, body_h))
    pygame.draw.ellipse(surface, outline,
                        (sx - body_w // 2, sy - 4, body_w, body_h), 1)

    # Thorax (middle small circle)
    thorax_y = sy - 4
    pygame.draw.circle(surface, color, (sx, thorax_y), body_w // 3 + 2)

    # Head
    head_y = sy - head_off
    pygame.draw.circle(surface, color, (sx, head_y), head_r)
    pygame.draw.circle(surface, outline, (sx, head_y), head_r, 1)

    # Legs (3 pairs from thorax)
    for dy_off in (-4, 2, 8):
        ly = thorax_y + dy_off
        # Left leg
        pygame.draw.line(surface, outline,
                         (sx - 4, ly),
                         (sx - leg_len, ly + leg_spread), 2)
        # Right leg
        pygame.draw.line(surface, outline,
                         (sx + 4, ly),
                         (sx + leg_len, ly + leg_spread), 2)

    # Antennae
    pygame.draw.line(surface, outline,
                     (sx - 2, head_y - head_r),
                     (sx - 10, head_y - head_r - 12), 1)
    pygame.draw.line(surface, outline,
                     (sx + 2, head_y - head_r),
                     (sx + 10, head_y - head_r - 12), 1)

    # Queen crown (3 gold spikes)
    if large:
        gold = (255, 215, 0)
        for dx in (-6, 0, 6):
            pygame.draw.polygon(surface, gold, [
                (sx + dx - 4, head_y - head_r - 4),
                (sx + dx + 4, head_y - head_r - 4),
                (sx + dx, head_y - head_r - 14),
            ])

    # Jelly indicator — only show when actually carrying jelly
    if entity.carrying > 0:
        pygame.draw.circle(surface, (240, 220, 60), (sx, sy + body_h + 4), 6)


def _draw_spitter(
    surface: pygame.Surface, sx: int, sy: int, entity: Entity,
) -> None:
    """Draw a spitter ant — like a regular ant but with a green poison sac."""
    color = PLAYER_COLORS.get(entity.player_id, (200, 200, 200))
    outline = _darken(color, 60)
    poison = (80, 200, 40)

    body_w, body_h = 16, 22
    head_r = 6
    head_off = 16
    leg_len = 12
    leg_spread = 8

    # Abdomen with poison sac (green tint)
    pygame.draw.ellipse(surface, poison, (sx - body_w // 2, sy - 4, body_w, body_h))
    pygame.draw.ellipse(surface, _darken(poison, 30),
                        (sx - body_w // 2, sy - 4, body_w, body_h), 1)

    # Thorax
    thorax_y = sy - 4
    pygame.draw.circle(surface, color, (sx, thorax_y), body_w // 3 + 2)

    # Head
    head_y = sy - head_off
    pygame.draw.circle(surface, color, (sx, head_y), head_r)
    pygame.draw.circle(surface, outline, (sx, head_y), head_r, 1)

    # Legs
    for dy_off in (-4, 2, 8):
        ly = thorax_y + dy_off
        pygame.draw.line(surface, outline, (sx - 4, ly), (sx - leg_len, ly + leg_spread), 2)
        pygame.draw.line(surface, outline, (sx + 4, ly), (sx + leg_len, ly + leg_spread), 2)

    # Antennae
    pygame.draw.line(surface, outline, (sx - 2, head_y - head_r), (sx - 10, head_y - head_r - 12), 1)
    pygame.draw.line(surface, outline, (sx + 2, head_y - head_r), (sx + 10, head_y - head_r - 12), 1)

    # Poison spit indicator (green dot at "mouth")
    pygame.draw.circle(surface, poison, (sx, head_y - head_r - 4), 4)


def _draw_corpse(
    surface: pygame.Surface, sx: int, sy: int, entity: Entity,
) -> None:
    """Draw a dead ant corpse — legs splayed out, with jelly indicator."""
    # Fade as decay progresses (hp counts down from max_hp)
    decay_frac = entity.hp / max(entity.max_hp, 1)
    gray = max(60, int(180 * decay_frac))
    c = (gray, max(0, gray - 10), max(0, gray - 20))
    dark = (max(0, gray - 30), max(0, gray - 40), max(0, gray - 50))
    # Body — two overlapping ovals for segmented look
    pygame.draw.ellipse(surface, c, (sx - 10, sy - 5, 20, 14))
    pygame.draw.ellipse(surface, dark, (sx - 10, sy - 5, 20, 14), 1)
    pygame.draw.ellipse(surface, c, (sx + 2, sy - 3, 12, 10))
    # Splayed legs — thicker, longer
    for angle_deg in (25, 75, 130):
        rad = math.radians(angle_deg)
        dx = int(18 * math.cos(rad))
        dy = int(18 * math.sin(rad))
        pygame.draw.line(surface, dark, (sx, sy), (sx + dx, sy + dy), 2)
        pygame.draw.line(surface, dark, (sx, sy), (sx - dx, sy + dy), 2)
    # Jelly indicator — golden blob showing harvestable value
    if entity.jelly_value > 0:
        jelly_r = min(8, 3 + entity.jelly_value // 5)
        glow = (220, 190, 40, 160)
        # Draw a filled golden circle
        pygame.draw.circle(surface, (200, 170, 30), (sx, sy - 12), jelly_r)
        pygame.draw.circle(surface, (240, 210, 60), (sx, sy - 12), max(1, jelly_r - 2))


def _draw_aphid(surface: pygame.Surface, sx: int, sy: int) -> None:
    """Draw a small green aphid."""
    body_color = (110, 190, 80)
    dark = (70, 140, 50)
    # Plump oval body
    pygame.draw.ellipse(surface, body_color, (sx - 8, sy - 6, 16, 12))
    pygame.draw.ellipse(surface, dark, (sx - 8, sy - 6, 16, 12), 1)
    # Tiny head
    pygame.draw.circle(surface, body_color, (sx, sy - 8), 4)
    # Antennae
    pygame.draw.line(surface, dark, (sx - 2, sy - 12), (sx - 6, sy - 18), 1)
    pygame.draw.line(surface, dark, (sx + 2, sy - 12), (sx + 6, sy - 18), 1)


def _draw_beetle(surface: pygame.Surface, sx: int, sy: int) -> None:
    """Draw a beetle with shell halves."""
    shell = (140, 100, 50)
    dark = (80, 55, 25)
    head_color = (60, 40, 20)
    # Shell (oval)
    pygame.draw.ellipse(surface, shell, (sx - 14, sy - 10, 28, 24))
    pygame.draw.ellipse(surface, dark, (sx - 14, sy - 10, 28, 24), 1)
    # Shell split line
    pygame.draw.line(surface, dark, (sx, sy - 10), (sx, sy + 14), 1)
    # Head
    pygame.draw.circle(surface, head_color, (sx, sy - 14), 6)
    # Pincers
    pygame.draw.line(surface, head_color, (sx - 4, sy - 18), (sx - 10, sy - 24), 2)
    pygame.draw.line(surface, head_color, (sx + 4, sy - 18), (sx + 10, sy - 24), 2)
    # Legs
    for dy in (-4, 2, 8):
        pygame.draw.line(surface, dark, (sx - 12, sy + dy), (sx - 20, sy + dy + 6), 1)
        pygame.draw.line(surface, dark, (sx + 12, sy + dy), (sx + 20, sy + dy + 6), 1)


def _draw_mantis(surface: pygame.Surface, sx: int, sy: int) -> None:
    """Draw a praying mantis — elongated body with raptorial arms."""
    body = (50, 160, 50)
    dark = (30, 100, 30)
    eye_color = (200, 200, 40)
    # Elongated abdomen
    pygame.draw.ellipse(surface, body, (sx - 10, sy, 20, 32))
    pygame.draw.ellipse(surface, dark, (sx - 10, sy, 20, 32), 1)
    # Thorax
    pygame.draw.ellipse(surface, body, (sx - 8, sy - 12, 16, 16))
    # Triangular head
    pygame.draw.polygon(surface, body, [
        (sx - 10, sy - 16),
        (sx + 10, sy - 16),
        (sx, sy - 30),
    ])
    pygame.draw.polygon(surface, dark, [
        (sx - 10, sy - 16),
        (sx + 10, sy - 16),
        (sx, sy - 30),
    ], 1)
    # Eyes
    pygame.draw.circle(surface, eye_color, (sx - 6, sy - 20), 4)
    pygame.draw.circle(surface, eye_color, (sx + 6, sy - 20), 4)
    # Raptorial front arms (bent)
    pygame.draw.line(surface, dark, (sx - 8, sy - 10), (sx - 20, sy - 24), 2)
    pygame.draw.line(surface, dark, (sx - 20, sy - 24), (sx - 16, sy - 36), 2)
    pygame.draw.line(surface, dark, (sx + 8, sy - 10), (sx + 20, sy - 24), 2)
    pygame.draw.line(surface, dark, (sx + 20, sy - 24), (sx + 16, sy - 36), 2)
    # Back legs
    for dy in (4, 12):
        pygame.draw.line(surface, dark, (sx - 8, sy + dy), (sx - 18, sy + dy + 10), 1)
        pygame.draw.line(surface, dark, (sx + 8, sy + dy), (sx + 18, sy + dy + 10), 1)


def _clamp(val: int, lo: int, hi: int) -> int:
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val
