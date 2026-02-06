"""Tile map and procedural generation.

Deterministic, integer-only, no PyGame dependency.
Uses a local LCG for random number generation (NOT Python's random module)
to ensure identical maps on both peers given the same seed.
"""

from __future__ import annotations

from enum import IntEnum


class TileType(IntEnum):
    DIRT = 0
    ROCK = 1


class TileMap:
    """2D tile grid for the game map.

    Tiles are stored in a flat list, row-major: tiles[y * width + x].
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.tiles: list[int] = [TileType.DIRT] * (width * height)
        self.start_positions: list[tuple[int, int]] = []
        self.hive_site_positions: list[tuple[int, int]] = []

    def get_tile(self, x: int, y: int) -> TileType:
        """Get tile type at (x, y). Out-of-bounds returns ROCK."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return TileType(self.tiles[y * self.width + x])
        return TileType.ROCK

    def set_tile(self, x: int, y: int, tile_type: TileType) -> None:
        """Set tile type at (x, y). Ignores out-of-bounds."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.tiles[y * self.width + x] = tile_type

    def is_walkable(self, x: int, y: int) -> bool:
        """Check if a tile can be walked on. DIRT is walkable, ROCK is not."""
        return self.get_tile(x, y) == TileType.DIRT


def _lcg_next(state: int) -> tuple[int, int]:
    """Single step of LCG PRNG. Returns (new_state, raw_value)."""
    state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
    return state, state


def generate_map(seed: int, width: int, height: int) -> TileMap:
    """Generate a symmetrical map using cellular automata.

    The map is horizontally mirrored for 2-player fairness. Uses a
    deterministic LCG seeded from `seed` — no Python random module.

    Args:
        seed: Random seed for generation.
        width: Map width in tiles.
        height: Map height in tiles.

    Returns:
        A populated TileMap with terrain, start positions, and hive sites.
    """
    tilemap = TileMap(width, height)
    rng = seed & 0xFFFFFFFF
    half_w = (width + 1) // 2

    # --- Step 1: Random rock scatter on left half ---
    rock_pct = 45
    for y in range(height):
        for x in range(half_w):
            rng, val = _lcg_next(rng)
            if val % 100 < rock_pct:
                tilemap.set_tile(x, y, TileType.ROCK)

    # --- Step 2: Cellular automata smoothing (4 iterations) ---
    # Rule: if >= 5 of 9 cells (self + 8 neighbors) are rock, become rock.
    # Produces organic cave-like rock formations.
    for _ in range(4):
        new_tiles = list(tilemap.tiles)
        for y in range(height):
            for x in range(half_w):
                rock_neighbors = 0
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        nx, ny = x + dx, y + dy
                        if nx < 0 or nx >= width or ny < 0 or ny >= height:
                            rock_neighbors += 1  # border counts as rock
                        elif tilemap.tiles[ny * width + nx] == TileType.ROCK:
                            rock_neighbors += 1
                if rock_neighbors >= 5:
                    new_tiles[y * width + x] = TileType.ROCK
                else:
                    new_tiles[y * width + x] = TileType.DIRT
        tilemap.tiles = new_tiles

    # --- Step 3: Mirror left half to right half ---
    for y in range(height):
        for x in range(half_w):
            tilemap.tiles[y * width + (width - 1 - x)] = tilemap.tiles[y * width + x]

    # --- Step 4: Rock border around map edges ---
    for x in range(width):
        tilemap.set_tile(x, 0, TileType.ROCK)
        tilemap.set_tile(x, height - 1, TileType.ROCK)
    for y in range(height):
        tilemap.set_tile(0, y, TileType.ROCK)
        tilemap.set_tile(width - 1, y, TileType.ROCK)

    # --- Step 5: Player start positions + clear areas ---
    start_positions = [
        (width // 4, height // 2),
        (width - 1 - width // 4, height // 2),
    ]
    tilemap.start_positions = start_positions

    clear_radius = 6
    _clear_symmetric(tilemap, start_positions[0][0], start_positions[0][1], clear_radius)

    # --- Step 6: Hive site locations (symmetrical expansion points) ---
    hive_sites = [
        (width // 2, height // 4),
        (width // 2, 3 * height // 4),
    ]
    tilemap.hive_site_positions = hive_sites

    site_radius = 3
    for _, (cx, cy) in enumerate(hive_sites):
        _clear_symmetric(tilemap, cx, cy, site_radius)

    return tilemap


def _clear_symmetric(tilemap: TileMap, cx: int, cy: int, radius: int) -> None:
    """Clear a circular area and its horizontal mirror to maintain symmetry."""
    mirror_cx = tilemap.width - 1 - cx
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius:
                tilemap.set_tile(cx + dx, cy + dy, TileType.DIRT)
                tilemap.set_tile(mirror_cx + dx, cy + dy, TileType.DIRT)
