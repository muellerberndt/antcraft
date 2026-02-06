"""Fog of war visibility computation.

Manages per-player visibility of tiles:
- UNEXPLORED (0): never seen
- FOG (1): previously seen but no friendly unit nearby
- VISIBLE (2): currently within sight of a friendly unit

DETERMINISM: Both peers update visibility identically at the end
of each tick, so the grids stay in sync.
"""

from __future__ import annotations

from src.config import MILLI_TILES_PER_TILE

UNEXPLORED = 0
FOG = 1
VISIBLE = 2


class VisibilityMap:
    """Per-player tile visibility grid."""

    def __init__(self, width: int, height: int, num_players: int = 2) -> None:
        self.width = width
        self.height = height
        self.num_players = num_players
        # Per-player grids stored as flat bytearrays: grid[y * width + x]
        self._grids: list[bytearray] = [
            bytearray(width * height) for _ in range(num_players)
        ]

    def get_visibility(self, player_id: int, x: int, y: int) -> int:
        """Get visibility state of a tile for a player."""
        if player_id < 0 or player_id >= self.num_players:
            return UNEXPLORED
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return UNEXPLORED
        return self._grids[player_id][y * self.width + x]

    def update(self, entities: list, player_id: int) -> None:
        """Recompute visibility for a player based on their entity positions.

        All currently VISIBLE tiles become FOG.
        Then entities with sight > 0 belonging to player_id reveal tiles.
        Uses integer distance: dx*dx + dy*dy <= radius*radius.
        """
        if player_id < 0 or player_id >= self.num_players:
            return

        grid = self._grids[player_id]
        w = self.width
        h = self.height

        # Demote VISIBLE -> FOG
        for i in range(len(grid)):
            if grid[i] == VISIBLE:
                grid[i] = FOG

        # Reveal tiles around each entity belonging to this player
        for entity in entities:
            if entity.player_id != player_id:
                continue
            if entity.sight <= 0:
                continue

            # Convert milli-tile position to tile coords
            tx = entity.x // MILLI_TILES_PER_TILE
            ty = entity.y // MILLI_TILES_PER_TILE
            sight = entity.sight
            sight_sq = sight * sight

            min_x = max(0, tx - sight)
            max_x = min(w - 1, tx + sight)
            min_y = max(0, ty - sight)
            max_y = min(h - 1, ty + sight)

            for cy in range(min_y, max_y + 1):
                row = cy * w
                dy = cy - ty
                dy_sq = dy * dy
                for cx in range(min_x, max_x + 1):
                    dx = cx - tx
                    if dx * dx + dy_sq <= sight_sq:
                        grid[row + cx] = VISIBLE

    def get_grid_bytes(self, player_id: int) -> bytes:
        """Get raw grid bytes for hashing."""
        if player_id < 0 or player_id >= self.num_players:
            return b""
        return bytes(self._grids[player_id])
