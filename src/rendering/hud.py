"""HUD and minimap rendering.

Draws the minimap (bottom-right), resource bar (top-center),
selection info (bottom-left), and debug overlay (top-left).
"""

from __future__ import annotations

import pygame

from src.config import (
    COLOR_DEBUG_TEXT,
    COLOR_PLAYER_1,
    COLOR_PLAYER_2,
    MINIMAP_SIZE,
    MILLI_TILES_PER_TILE,
)
from src.simulation.state import EntityType, GameState
from src.simulation.tilemap import TileMap, TileType
from src.simulation.visibility import FOG, UNEXPLORED, VISIBLE

PLAYER_COLORS = {0: COLOR_PLAYER_1, 1: COLOR_PLAYER_2}
_MINIMAP_MARGIN = 10
_MINIMAP_BORDER = (40, 40, 40)
_MINIMAP_BG = (20, 15, 10)


class HUD:
    """Draws minimap, resource bar, selection info, and debug overlay."""

    def __init__(self, screen: pygame.Surface, tilemap: TileMap) -> None:
        self._screen = screen
        self._font = pygame.font.SysFont("monospace", 16)
        self._large_font = pygame.font.SysFont("monospace", 20, bold=True)
        self._tilemap = tilemap

        # Minimap scale: pixels per tile
        self._mm_scale = MINIMAP_SIZE / max(tilemap.width, tilemap.height)
        self._mm_w = int(tilemap.width * self._mm_scale)
        self._mm_h = int(tilemap.height * self._mm_scale)

        # Minimap position (bottom-right)
        sw = screen.get_width()
        sh = screen.get_height()
        self._mm_x = sw - self._mm_w - _MINIMAP_MARGIN
        self._mm_y = sh - self._mm_h - _MINIMAP_MARGIN

        # Pre-render terrain
        self._minimap_base = self._build_minimap_terrain(tilemap)

        # Overlay surface for per-frame drawing
        self._mm_overlay = pygame.Surface(
            (self._mm_w, self._mm_h), pygame.SRCALPHA,
        )

    def _build_minimap_terrain(self, tilemap: TileMap) -> pygame.Surface:
        """Pre-render the minimap terrain surface."""
        surf = pygame.Surface((self._mm_w, self._mm_h))
        surf.fill(_MINIMAP_BG)
        scale = self._mm_scale

        for y in range(tilemap.height):
            for x in range(tilemap.width):
                tile = tilemap.get_tile(x, y)
                if tile == TileType.DIRT:
                    color = (80, 60, 30)
                else:  # ROCK
                    color = (50, 50, 48)
                px = int(x * scale)
                py = int(y * scale)
                pw = max(1, int((x + 1) * scale) - px)
                ph = max(1, int((y + 1) * scale) - py)
                pygame.draw.rect(surf, color, (px, py, pw, ph))

        return surf

    @property
    def minimap_rect(self) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) of the minimap in screen coords."""
        return (self._mm_x, self._mm_y, self._mm_w, self._mm_h)

    def screen_to_tile(self, screen_x: int, screen_y: int) -> tuple[int, int] | None:
        """Convert a screen click to tile coords if it's on the minimap."""
        rx = screen_x - self._mm_x
        ry = screen_y - self._mm_y
        if rx < 0 or ry < 0 or rx >= self._mm_w or ry >= self._mm_h:
            return None
        tile_x = int(rx / self._mm_scale)
        tile_y = int(ry / self._mm_scale)
        return (tile_x, tile_y)

    def draw(
        self,
        state: GameState,
        player_id: int,
        camera_x: int,
        camera_y: int,
        tile_size: int,
        selected_ids: set[int],
        debug_info: dict[str, str],
    ) -> None:
        """Draw all HUD elements."""
        self._draw_minimap(state, player_id, camera_x, camera_y, tile_size)
        self._draw_resources(state, player_id)
        self._draw_selection_info(state, selected_ids)
        self._draw_debug(debug_info)

    # ---- Minimap ----

    def _draw_minimap(
        self,
        state: GameState,
        player_id: int,
        camera_x: int,
        camera_y: int,
        tile_size: int,
    ) -> None:
        """Draw the minimap with terrain, fog, entities, and viewport rect."""
        # Blit pre-rendered terrain
        self._screen.blit(self._minimap_base, (self._mm_x, self._mm_y))

        # Draw fog overlay on minimap
        self._draw_minimap_fog(state, player_id)

        # Draw entities on minimap
        self._draw_minimap_entities(state, player_id)

        # Draw camera viewport rectangle
        self._draw_minimap_viewport(camera_x, camera_y, tile_size)

        # Border
        pygame.draw.rect(
            self._screen, _MINIMAP_BORDER,
            (self._mm_x - 1, self._mm_y - 1, self._mm_w + 2, self._mm_h + 2), 1,
        )

    def _draw_minimap_fog(self, state: GameState, player_id: int) -> None:
        """Draw fog of war on the minimap."""
        scale = self._mm_scale
        vis_map = state.visibility
        fog = self._mm_overlay
        fog.fill((0, 0, 0, 0))

        for ty in range(self._tilemap.height):
            for tx in range(self._tilemap.width):
                vis = vis_map.get_visibility(player_id, tx, ty)
                if vis == VISIBLE:
                    continue
                px = int(tx * scale)
                py = int(ty * scale)
                pw = max(1, int((tx + 1) * scale) - px)
                ph = max(1, int((ty + 1) * scale) - py)
                if vis == UNEXPLORED:
                    pygame.draw.rect(fog, (0, 0, 0, 220), (px, py, pw, ph))
                else:  # FOG
                    pygame.draw.rect(fog, (0, 0, 0, 120), (px, py, pw, ph))

        self._screen.blit(fog, (self._mm_x, self._mm_y))

    def _draw_minimap_entities(self, state: GameState, player_id: int) -> None:
        """Draw entity dots on the minimap."""
        scale = self._mm_scale
        vis_map = state.visibility
        mt = MILLI_TILES_PER_TILE

        for entity in state.entities:
            # Skip corpses on minimap
            if entity.entity_type == EntityType.CORPSE:
                continue

            tile_x = entity.x // mt
            tile_y = entity.y // mt

            # Enemy/neutral entities only visible if tile is VISIBLE
            if entity.player_id != player_id and entity.player_id >= 0:
                if vis_map.get_visibility(player_id, tile_x, tile_y) != VISIBLE:
                    continue

            # Determine color and size
            px = self._mm_x + int(tile_x * scale + scale / 2)
            py = self._mm_y + int(tile_y * scale + scale / 2)

            if entity.entity_type == EntityType.HIVE:
                color = PLAYER_COLORS.get(entity.player_id, (200, 200, 200))
                pygame.draw.rect(self._screen, color, (px - 2, py - 2, 5, 5))
            elif entity.entity_type == EntityType.HIVE_SITE:
                pygame.draw.rect(self._screen, (120, 120, 120), (px - 1, py - 1, 3, 3))
            elif entity.player_id >= 0:
                # Player units (ants, queens)
                color = PLAYER_COLORS.get(entity.player_id, (200, 200, 200))
                self._screen.set_at((px, py), color)
            else:
                # Wildlife — yellow-green dot
                if vis_map.get_visibility(player_id, tile_x, tile_y) == VISIBLE:
                    self._screen.set_at((px, py), (160, 180, 60))

    def _draw_minimap_viewport(
        self, camera_x: int, camera_y: int, tile_size: int,
    ) -> None:
        """Draw white rectangle showing the current camera viewport."""
        scale = self._mm_scale
        sw = self._screen.get_width()
        sh = self._screen.get_height()

        # Camera viewport in tile coords
        vx = camera_x / tile_size * scale
        vy = camera_y / tile_size * scale
        vw = sw / tile_size * scale
        vh = sh / tile_size * scale

        rect = pygame.Rect(
            int(self._mm_x + vx), int(self._mm_y + vy),
            int(vw), int(vh),
        )
        pygame.draw.rect(self._screen, (255, 255, 255), rect, 1)

    # ---- Resource display ----

    def _draw_resources(self, state: GameState, player_id: int) -> None:
        """Draw jelly and ant count at top-right corner."""
        jelly = state.player_jelly.get(player_id, 0)
        ant_count = sum(
            1 for e in state.entities
            if e.entity_type == EntityType.ANT and e.player_id == player_id
        )

        jelly_text = f"Jelly: {jelly}"
        ants_text = f"Ants: {ant_count}"

        jelly_surf = self._large_font.render(jelly_text, True, (240, 220, 60))
        ants_surf = self._large_font.render(ants_text, True, (200, 200, 200))

        sw = self._screen.get_width()
        total_w = jelly_surf.get_width() + 20 + ants_surf.get_width()
        start_x = sw - total_w - 16

        # Background bar
        bar_h = 28
        bar_surf = pygame.Surface((total_w + 20, bar_h), pygame.SRCALPHA)
        bar_surf.fill((0, 0, 0, 140))
        self._screen.blit(bar_surf, (start_x - 10, 4))

        self._screen.blit(jelly_surf, (start_x, 6))
        self._screen.blit(ants_surf, (start_x + jelly_surf.get_width() + 20, 6))

    # ---- Selection info ----

    def _draw_selection_info(self, state: GameState, selected_ids: set[int]) -> None:
        """Draw selection info at bottom-left."""
        if not selected_ids:
            return

        ants = 0
        queens = 0
        single_entity = None
        for eid in selected_ids:
            e = state.get_entity(eid)
            if e is None:
                continue
            if e.entity_type == EntityType.ANT:
                ants += 1
            elif e.entity_type == EntityType.QUEEN:
                queens += 1
            if len(selected_ids) == 1:
                single_entity = e

        parts: list[str] = []
        if ants > 0:
            parts.append(f"{ants} Ant{'s' if ants > 1 else ''}")
        if queens > 0:
            parts.append(f"{queens} Queen{'s' if queens > 1 else ''}")
        if not parts:
            return

        text = " + ".join(parts) + " selected"
        text_surf = self._font.render(text, True, (200, 200, 200))

        sh = self._screen.get_height()
        y = sh - 30

        # Background
        bg_w = text_surf.get_width() + 16
        bg_surf = pygame.Surface((bg_w, 24), pygame.SRCALPHA)
        bg_surf.fill((0, 0, 0, 140))
        self._screen.blit(bg_surf, (8, y - 2))
        self._screen.blit(text_surf, (16, y))

        # HP bar for single selection
        if single_entity and single_entity.max_hp > 0:
            bar_w, bar_h = 80, 6
            bx = 16
            by = y - 12
            pygame.draw.rect(self._screen, (60, 0, 0), (bx, by, bar_w, bar_h))
            fill = max(1, single_entity.hp * bar_w // single_entity.max_hp)
            pygame.draw.rect(self._screen, (0, 200, 0), (bx, by, fill, bar_h))

    # ---- Debug overlay ----

    def _draw_debug(self, debug_info: dict[str, str]) -> None:
        """Draw debug info at top-left."""
        y = 5
        for key, value in debug_info.items():
            text = f"{key}: {value}"
            surface = self._font.render(text, True, COLOR_DEBUG_TEXT)
            self._screen.blit(surface, (5, y))
            y += 20
