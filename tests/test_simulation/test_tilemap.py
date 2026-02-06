"""Tests for TileMap and procedural map generation."""

from src.simulation.tilemap import TileMap, TileType, generate_map


class TestTileMap:
    """Tests for the TileMap data structure."""

    def test_initial_tiles_are_dirt(self):
        tm = TileMap(10, 10)
        for y in range(10):
            for x in range(10):
                assert tm.get_tile(x, y) == TileType.DIRT

    def test_set_and_get_tile(self):
        tm = TileMap(10, 10)
        tm.set_tile(3, 4, TileType.ROCK)
        assert tm.get_tile(3, 4) == TileType.ROCK
        assert tm.get_tile(3, 3) == TileType.DIRT

    def test_out_of_bounds_returns_rock(self):
        tm = TileMap(10, 10)
        assert tm.get_tile(-1, 0) == TileType.ROCK
        assert tm.get_tile(0, -1) == TileType.ROCK
        assert tm.get_tile(10, 0) == TileType.ROCK
        assert tm.get_tile(0, 10) == TileType.ROCK
        assert tm.get_tile(100, 100) == TileType.ROCK

    def test_set_out_of_bounds_ignored(self):
        tm = TileMap(10, 10)
        tm.set_tile(-1, 0, TileType.ROCK)  # should not crash
        tm.set_tile(10, 0, TileType.ROCK)
        # All in-bounds tiles should still be DIRT
        for y in range(10):
            for x in range(10):
                assert tm.get_tile(x, y) == TileType.DIRT

    def test_is_walkable(self):
        tm = TileMap(10, 10)
        assert tm.is_walkable(0, 0) is True
        tm.set_tile(0, 0, TileType.ROCK)
        assert tm.is_walkable(0, 0) is False

    def test_is_walkable_out_of_bounds(self):
        tm = TileMap(10, 10)
        assert tm.is_walkable(-1, 0) is False
        assert tm.is_walkable(10, 0) is False

    def test_flat_array_indexing(self):
        tm = TileMap(5, 5)
        tm.set_tile(3, 2, TileType.ROCK)
        # row-major: index = y * width + x = 2 * 5 + 3 = 13
        assert tm.tiles[13] == TileType.ROCK


class TestGenerateMap:
    """Tests for procedural map generation."""

    def test_same_seed_same_map(self):
        m1 = generate_map(42, 50, 50)
        m2 = generate_map(42, 50, 50)
        assert m1.tiles == m2.tiles

    def test_different_seeds_different_maps(self):
        m1 = generate_map(42, 50, 50)
        m2 = generate_map(99, 50, 50)
        assert m1.tiles != m2.tiles

    def test_map_is_horizontally_symmetric(self):
        tm = generate_map(42, 60, 40)
        for y in range(tm.height):
            for x in range(tm.width // 2):
                mirror_x = tm.width - 1 - x
                assert tm.get_tile(x, y) == tm.get_tile(mirror_x, y), (
                    f"Asymmetry at ({x},{y}) vs ({mirror_x},{y})"
                )

    def test_starting_areas_are_walkable(self):
        tm = generate_map(42, 100, 100)
        assert len(tm.start_positions) == 2
        for cx, cy in tm.start_positions:
            # Check a radius around the start position
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    if dx * dx + dy * dy <= 9:
                        assert tm.is_walkable(cx + dx, cy + dy), (
                            f"Non-walkable tile at start area ({cx+dx},{cy+dy})"
                        )

    def test_start_positions_are_symmetric(self):
        tm = generate_map(42, 100, 100)
        p0x, p0y = tm.start_positions[0]
        p1x, p1y = tm.start_positions[1]
        assert p1x == tm.width - 1 - p0x
        assert p1y == p0y

    def test_border_is_rock(self):
        tm = generate_map(42, 50, 50)
        for x in range(tm.width):
            assert tm.get_tile(x, 0) == TileType.ROCK
            assert tm.get_tile(x, tm.height - 1) == TileType.ROCK
        for y in range(tm.height):
            assert tm.get_tile(0, y) == TileType.ROCK
            assert tm.get_tile(tm.width - 1, y) == TileType.ROCK

    def test_hive_sites_placed(self):
        tm = generate_map(42, 100, 100)
        assert len(tm.hive_site_positions) > 0

    def test_hive_sites_are_walkable(self):
        tm = generate_map(42, 100, 100)
        for cx, cy in tm.hive_site_positions:
            assert tm.is_walkable(cx, cy), (
                f"Hive site at ({cx},{cy}) is not walkable"
            )

    def test_has_both_tile_types(self):
        tm = generate_map(42, 100, 100)
        has_dirt = any(t == TileType.DIRT for t in tm.tiles)
        has_rock = any(t == TileType.ROCK for t in tm.tiles)
        assert has_dirt
        assert has_rock

    def test_determinism_across_sizes(self):
        """Same seed with same dimensions always produces identical output."""
        for seed in [0, 1, 12345, 0xDEADBEEF]:
            m1 = generate_map(seed, 40, 40)
            m2 = generate_map(seed, 40, 40)
            assert m1.tiles == m2.tiles
            assert m1.start_positions == m2.start_positions
            assert m1.hive_site_positions == m2.hive_site_positions
