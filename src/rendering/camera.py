"""Camera & viewport for AntCraft.

The camera defines which portion of the tile map is visible on screen.
All positions are in milli-tiles (integers). The camera is local-only
and never synced over the network.
"""

from __future__ import annotations

from src.config import (
    CAMERA_EDGE_SCROLL_MARGIN,
    CAMERA_SCROLL_SPEED,
    MAP_HEIGHT_TILES,
    MAP_WIDTH_TILES,
    MILLI_TILES_PER_TILE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)


class Camera:
    """Viewport into the game world."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = SCREEN_WIDTH,
        height: int = SCREEN_HEIGHT,
        tile_size: int = 32,
        map_width: int = MAP_WIDTH_TILES,
        map_height: int = MAP_HEIGHT_TILES,
    ) -> None:
        self.width = width
        self.height = height
        self.tile_size = tile_size
        self.map_width = map_width
        self.map_height = map_height
        # x, y are top-left corner in milli-tiles — clamp on init
        self.x = x
        self.y = y
        self._clamp()

    def _clamp(self) -> None:
        """Clamp camera position so it doesn't go outside the map."""
        # How many milli-tiles the viewport covers
        viewport_mt_w = self.width * MILLI_TILES_PER_TILE // self.tile_size
        viewport_mt_h = self.height * MILLI_TILES_PER_TILE // self.tile_size

        map_mt_w = self.map_width * MILLI_TILES_PER_TILE
        map_mt_h = self.map_height * MILLI_TILES_PER_TILE

        max_x = max(0, map_mt_w - viewport_mt_w)
        max_y = max(0, map_mt_h - viewport_mt_h)

        self.x = max(0, min(self.x, max_x))
        self.y = max(0, min(self.y, max_y))

    def move(self, dx: int, dy: int) -> None:
        """Shift camera by (dx, dy) milli-tiles, clamped to map bounds."""
        self.x += dx
        self.y += dy
        self._clamp()

    def screen_to_world(self, screen_x: int, screen_y: int) -> tuple[int, int]:
        """Convert screen pixel coordinates to world milli-tile coordinates."""
        world_x = self.x + screen_x * MILLI_TILES_PER_TILE // self.tile_size
        world_y = self.y + screen_y * MILLI_TILES_PER_TILE // self.tile_size
        return (world_x, world_y)

    def world_to_screen(self, world_x: int, world_y: int) -> tuple[int, int]:
        """Convert world milli-tile coordinates to screen pixel coordinates."""
        screen_x = (world_x - self.x) * self.tile_size // MILLI_TILES_PER_TILE
        screen_y = (world_y - self.y) * self.tile_size // MILLI_TILES_PER_TILE
        return (screen_x, screen_y)

    def get_visible_tile_range(self) -> tuple[int, int, int, int]:
        """Return the range of tiles visible in the viewport.

        Returns:
            (min_tile_x, min_tile_y, max_tile_x, max_tile_y) inclusive.
        """
        min_tx = self.x // MILLI_TILES_PER_TILE
        min_ty = self.y // MILLI_TILES_PER_TILE

        # Bottom-right corner of viewport in milli-tiles
        br_x = self.x + self.width * MILLI_TILES_PER_TILE // self.tile_size
        br_y = self.y + self.height * MILLI_TILES_PER_TILE // self.tile_size

        max_tx = min(br_x // MILLI_TILES_PER_TILE, self.map_width - 1)
        max_ty = min(br_y // MILLI_TILES_PER_TILE, self.map_height - 1)

        return (min_tx, min_ty, max_tx, max_ty)

    def handle_edge_scroll(self, mouse_x: int, mouse_y: int) -> None:
        """Scroll camera when mouse is near screen edge."""
        scroll_mt = CAMERA_SCROLL_SPEED * MILLI_TILES_PER_TILE // self.tile_size
        dx = 0
        dy = 0

        if mouse_x < CAMERA_EDGE_SCROLL_MARGIN:
            dx = -scroll_mt
        elif mouse_x > self.width - CAMERA_EDGE_SCROLL_MARGIN:
            dx = scroll_mt

        if mouse_y < CAMERA_EDGE_SCROLL_MARGIN:
            dy = -scroll_mt
        elif mouse_y > self.height - CAMERA_EDGE_SCROLL_MARGIN:
            dy = scroll_mt

        if dx or dy:
            self.move(dx, dy)

    def handle_key_scroll(self, keys_pressed: dict[int, bool]) -> None:
        """Scroll camera with arrow keys. Pass pygame.key.get_pressed()."""
        import pygame

        scroll_mt = CAMERA_SCROLL_SPEED * MILLI_TILES_PER_TILE // self.tile_size
        dx = 0
        dy = 0

        if keys_pressed[pygame.K_LEFT]:
            dx = -scroll_mt
        if keys_pressed[pygame.K_RIGHT]:
            dx = scroll_mt
        if keys_pressed[pygame.K_UP]:
            dy = -scroll_mt
        if keys_pressed[pygame.K_DOWN]:
            dy = scroll_mt

        if dx or dy:
            self.move(dx, dy)

    def center_on(self, world_x: int, world_y: int) -> None:
        """Center the camera on a world position (milli-tiles)."""
        viewport_mt_w = self.width * MILLI_TILES_PER_TILE // self.tile_size
        viewport_mt_h = self.height * MILLI_TILES_PER_TILE // self.tile_size
        self.x = world_x - viewport_mt_w // 2
        self.y = world_y - viewport_mt_h // 2
        self._clamp()
