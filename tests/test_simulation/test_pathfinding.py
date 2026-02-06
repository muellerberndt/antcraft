"""Tests for A* pathfinding."""

from src.simulation.pathfinding import find_path, CARDINAL_COST, DIAGONAL_COST
from src.simulation.tilemap import TileMap, TileType


def _make_open_map(width: int = 20, height: int = 20) -> TileMap:
    """Create a fully walkable map (all DIRT)."""
    return TileMap(width, height)


def _make_map_with_wall(width: int = 20, height: int = 20) -> TileMap:
    """Create a map with a vertical rock wall from (10, 0) to (10, 14),
    leaving a gap at (10, 15) through (10, 19)."""
    tm = TileMap(width, height)
    for y in range(15):
        tm.set_tile(10, y, TileType.ROCK)
    return tm


class TestStraightLinePath:
    def test_horizontal_path(self):
        tm = _make_open_map()
        path = find_path(tm, 2, 5, 8, 5)
        assert len(path) > 0
        assert path[-1] == (8, 5)
        # All waypoints should be on y=5 (straight horizontal)
        for x, y in path:
            assert y == 5

    def test_vertical_path(self):
        tm = _make_open_map()
        path = find_path(tm, 5, 2, 5, 8)
        assert len(path) > 0
        assert path[-1] == (5, 8)
        for x, y in path:
            assert x == 5

    def test_diagonal_path(self):
        tm = _make_open_map()
        path = find_path(tm, 2, 2, 7, 7)
        assert len(path) > 0
        assert path[-1] == (7, 7)
        # Pure diagonal: each step should move +1 in both x and y
        assert len(path) == 5
        for i, (x, y) in enumerate(path):
            assert x == 3 + i
            assert y == 3 + i


class TestPathAroundWall:
    def test_path_goes_around_wall(self):
        tm = _make_map_with_wall()
        path = find_path(tm, 5, 5, 15, 5)
        assert len(path) > 0
        assert path[-1] == (15, 5)
        # Path should not pass through any rock tile
        for x, y in path:
            assert tm.is_walkable(x, y)

    def test_path_through_gap(self):
        """Path should find the gap at y>=15 in the wall."""
        tm = _make_map_with_wall()
        path = find_path(tm, 5, 10, 15, 10)
        assert len(path) > 0
        assert path[-1] == (15, 10)
        for x, y in path:
            assert tm.is_walkable(x, y)


class TestNoPath:
    def test_completely_blocked(self):
        """Surround the start with rocks — no path possible."""
        tm = _make_open_map()
        # Wall around (5, 5)
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if dx != 0 or dy != 0:
                    tm.set_tile(5 + dx, 5 + dy, TileType.ROCK)
        path = find_path(tm, 5, 5, 15, 15)
        assert path == []

    def test_goal_is_rock(self):
        tm = _make_open_map()
        tm.set_tile(10, 10, TileType.ROCK)
        path = find_path(tm, 5, 5, 10, 10)
        assert path == []

    def test_start_is_rock(self):
        tm = _make_open_map()
        tm.set_tile(5, 5, TileType.ROCK)
        path = find_path(tm, 5, 5, 10, 10)
        assert path == []

    def test_start_equals_goal(self):
        tm = _make_open_map()
        path = find_path(tm, 5, 5, 5, 5)
        assert path == []


class TestDeterminism:
    def test_same_inputs_same_path(self):
        """Running pathfinding twice with the same inputs must produce
        the identical path."""
        tm = _make_map_with_wall()
        path1 = find_path(tm, 3, 3, 17, 3)
        path2 = find_path(tm, 3, 3, 17, 3)
        assert path1 == path2

    def test_deterministic_across_maps(self):
        """Two separately constructed but identical maps produce the same path."""
        tm1 = _make_map_with_wall()
        tm2 = _make_map_with_wall()
        path1 = find_path(tm1, 3, 3, 17, 3)
        path2 = find_path(tm2, 3, 3, 17, 3)
        assert path1 == path2


class TestCosts:
    def test_diagonal_costs_more_than_cardinal(self):
        """A diagonal step costs ~1414 vs 1000 for cardinal, so a path
        that is 5 tiles diagonally should cost more than 5 tiles cardinally."""
        assert DIAGONAL_COST > CARDINAL_COST

    def test_prefers_cardinal_when_shorter(self):
        """Moving 5 tiles east should take 5 cardinal steps, not zigzag."""
        tm = _make_open_map()
        path = find_path(tm, 2, 5, 7, 5)
        assert len(path) == 5
        for x, y in path:
            assert y == 5


class TestPathAvoidRock:
    def test_path_avoids_rock_tiles(self):
        tm = _make_open_map()
        # Place a line of rocks blocking direct path
        for y in range(3, 8):
            tm.set_tile(5, y, TileType.ROCK)
        path = find_path(tm, 3, 5, 8, 5)
        assert len(path) > 0
        assert path[-1] == (8, 5)
        for x, y in path:
            assert tm.is_walkable(x, y)


class TestDiagonalCornerCutting:
    def test_no_corner_cutting(self):
        """Diagonal moves should not cut through rock corners."""
        tm = _make_open_map()
        # Place rocks so that cutting a corner would be invalid:
        # Rock at (5,5) and (6,6) — diagonal from (5,6) to (6,5) would
        # cut through the corner between these rocks
        tm.set_tile(5, 5, TileType.ROCK)
        tm.set_tile(6, 6, TileType.ROCK)
        path = find_path(tm, 5, 6, 6, 5)
        assert len(path) > 0
        # Path should go around, not diagonally through the corner
        # A direct diagonal would be length 1, going around takes more steps
        assert len(path) > 1


class TestStartExcluded:
    def test_start_not_in_path(self):
        """The starting position should not be included in the returned path."""
        tm = _make_open_map()
        path = find_path(tm, 3, 3, 6, 3)
        assert len(path) > 0
        assert (3, 3) not in path
        assert path[-1] == (6, 3)
