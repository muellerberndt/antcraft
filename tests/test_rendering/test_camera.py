"""Tests for Camera & Viewport."""

from src.config import MILLI_TILES_PER_TILE
from src.rendering.camera import Camera


# --- Helpers ---

def make_camera(**kwargs) -> Camera:
    """Create a camera with small defaults for easy testing."""
    defaults = dict(
        x=0, y=0,
        width=640, height=480,
        tile_size=32,
        map_width=100, map_height=100,
    )
    defaults.update(kwargs)
    return Camera(**defaults)


# --- Coordinate conversion ---

class TestCoordinateConversion:
    def test_screen_to_world_at_origin(self):
        cam = make_camera(x=0, y=0)
        wx, wy = cam.screen_to_world(0, 0)
        assert wx == 0
        assert wy == 0

    def test_screen_to_world_offset(self):
        cam = make_camera(x=0, y=0, tile_size=32)
        # 32 pixels = 1 tile = 1000 milli-tiles
        wx, wy = cam.screen_to_world(32, 32)
        assert wx == MILLI_TILES_PER_TILE
        assert wy == MILLI_TILES_PER_TILE

    def test_screen_to_world_with_camera_offset(self):
        cam = make_camera(x=5000, y=3000, tile_size=32)
        wx, wy = cam.screen_to_world(0, 0)
        assert wx == 5000
        assert wy == 3000

    def test_world_to_screen_at_origin(self):
        cam = make_camera(x=0, y=0)
        sx, sy = cam.world_to_screen(0, 0)
        assert sx == 0
        assert sy == 0

    def test_world_to_screen_offset(self):
        cam = make_camera(x=0, y=0, tile_size=32)
        sx, sy = cam.world_to_screen(MILLI_TILES_PER_TILE, MILLI_TILES_PER_TILE)
        assert sx == 32
        assert sy == 32

    def test_world_to_screen_with_camera_offset(self):
        cam = make_camera(x=5000, y=3000, tile_size=32)
        sx, sy = cam.world_to_screen(5000, 3000)
        assert sx == 0
        assert sy == 0

    def test_roundtrip_screen_to_world_to_screen(self):
        # Integer division truncation means roundtrip can lose up to 1 pixel
        cam = make_camera(x=0, y=0, tile_size=32)
        for sx, sy in [(0, 0), (100, 200), (320, 240), (639, 479)]:
            wx, wy = cam.screen_to_world(sx, sy)
            sx2, sy2 = cam.world_to_screen(wx, wy)
            assert abs(sx2 - sx) <= 1
            assert abs(sy2 - sy) <= 1

    def test_roundtrip_within_one_pixel(self):
        # With non-aligned camera offset, roundtrip may lose up to 1 pixel
        cam = make_camera(x=10000, y=8000, tile_size=32)
        for sx, sy in [(0, 0), (100, 200), (320, 240)]:
            wx, wy = cam.screen_to_world(sx, sy)
            sx2, sy2 = cam.world_to_screen(wx, wy)
            assert abs(sx2 - sx) <= 1
            assert abs(sy2 - sy) <= 1


# --- Clamping ---

class TestClamping:
    def test_clamp_negative_x(self):
        cam = make_camera(x=-5000, y=0)
        assert cam.x == 0

    def test_clamp_negative_y(self):
        cam = make_camera(x=0, y=-5000)
        assert cam.y == 0

    def test_clamp_beyond_map_right(self):
        cam = make_camera(x=999999, y=0, map_width=100, tile_size=32, width=640)
        # Viewport covers 640 * 1000 / 32 = 20000 milli-tiles
        # Map is 100 * 1000 = 100000 milli-tiles
        # Max x = 100000 - 20000 = 80000
        assert cam.x == 80000

    def test_clamp_beyond_map_bottom(self):
        cam = make_camera(x=0, y=999999, map_height=100, tile_size=32, height=480)
        # Viewport covers 480 * 1000 / 32 = 15000 milli-tiles
        # Map is 100 * 1000 = 100000 milli-tiles
        # Max y = 100000 - 15000 = 85000
        assert cam.y == 85000

    def test_move_clamps(self):
        cam = make_camera(x=0, y=0)
        cam.move(-10000, -10000)
        assert cam.x == 0
        assert cam.y == 0

    def test_small_map_clamps_to_zero(self):
        # Map smaller than viewport — camera stuck at (0, 0)
        cam = make_camera(x=5000, y=5000, map_width=10, map_height=10, tile_size=32, width=640, height=480)
        assert cam.x == 0
        assert cam.y == 0


# --- Movement ---

class TestMovement:
    def test_move_positive(self):
        cam = make_camera(x=0, y=0)
        cam.move(1000, 2000)
        assert cam.x == 1000
        assert cam.y == 2000

    def test_move_negative(self):
        cam = make_camera(x=5000, y=5000)
        cam.move(-1000, -2000)
        assert cam.x == 4000
        assert cam.y == 3000

    def test_move_cumulative(self):
        cam = make_camera(x=0, y=0)
        cam.move(1000, 1000)
        cam.move(1000, 1000)
        assert cam.x == 2000
        assert cam.y == 2000


# --- Visible tile range ---

class TestVisibleTileRange:
    def test_at_origin(self):
        cam = make_camera(x=0, y=0, tile_size=32, width=640, height=480)
        min_tx, min_ty, max_tx, max_ty = cam.get_visible_tile_range()
        assert min_tx == 0
        assert min_ty == 0
        # 640 / 32 = 20 tiles wide, 480 / 32 = 15 tiles tall
        assert max_tx == 20
        assert max_ty == 15

    def test_offset_camera(self):
        # Camera at tile (5, 3)
        cam = make_camera(x=5000, y=3000, tile_size=32, width=640, height=480)
        min_tx, min_ty, max_tx, max_ty = cam.get_visible_tile_range()
        assert min_tx == 5
        assert min_ty == 3
        assert max_tx == 25
        assert max_ty == 18

    def test_clamped_to_map_bounds(self):
        cam = make_camera(x=80000, y=85000, tile_size=32, width=640, height=480,
                          map_width=100, map_height=100)
        min_tx, min_ty, max_tx, max_ty = cam.get_visible_tile_range()
        assert max_tx <= 99
        assert max_ty <= 99


# --- Center on ---

class TestCenterOn:
    def test_center_on_map_center(self):
        cam = make_camera(x=0, y=0, tile_size=32, width=640, height=480,
                          map_width=100, map_height=100)
        cam.center_on(50000, 50000)
        # Viewport: 20000 mt wide, 15000 mt tall
        # Expected: x = 50000 - 10000 = 40000, y = 50000 - 7500 = 42500
        assert cam.x == 40000
        assert cam.y == 42500

    def test_center_on_origin_clamps(self):
        cam = make_camera(tile_size=32, width=640, height=480)
        cam.center_on(0, 0)
        assert cam.x == 0
        assert cam.y == 0

    def test_center_on_bottom_right_clamps(self):
        cam = make_camera(tile_size=32, width=640, height=480,
                          map_width=100, map_height=100)
        cam.center_on(100000, 100000)
        assert cam.x == 80000
        assert cam.y == 85000
