"""Tests for fog of war visibility computation."""

from src.config import MILLI_TILES_PER_TILE
from src.simulation.state import Entity, EntityType, GameState
from src.simulation.visibility import UNEXPLORED, FOG, VISIBLE, VisibilityMap


def _make_entity(player_id: int, tx: int, ty: int, sight: int = 5) -> Entity:
    """Create an entity at tile coords (tx, ty) with given sight."""
    mt = MILLI_TILES_PER_TILE
    return Entity(
        entity_id=0, entity_type=EntityType.ANT, player_id=player_id,
        x=tx * mt + mt // 2, y=ty * mt + mt // 2,
        target_x=tx * mt + mt // 2, target_y=ty * mt + mt // 2,
        sight=sight,
    )


class TestVisibilityBasics:
    def test_initial_state_is_unexplored(self):
        vm = VisibilityMap(20, 20)
        assert vm.get_visibility(0, 5, 5) == UNEXPLORED
        assert vm.get_visibility(1, 10, 10) == UNEXPLORED

    def test_out_of_bounds_returns_unexplored(self):
        vm = VisibilityMap(10, 10)
        assert vm.get_visibility(0, -1, 0) == UNEXPLORED
        assert vm.get_visibility(0, 0, -1) == UNEXPLORED
        assert vm.get_visibility(0, 10, 0) == UNEXPLORED
        assert vm.get_visibility(0, 0, 10) == UNEXPLORED

    def test_invalid_player_returns_unexplored(self):
        vm = VisibilityMap(10, 10)
        assert vm.get_visibility(-1, 5, 5) == UNEXPLORED
        assert vm.get_visibility(5, 5, 5) == UNEXPLORED


class TestVisibilityReveal:
    def test_unit_reveals_tiles_within_sight(self):
        vm = VisibilityMap(20, 20)
        entity = _make_entity(player_id=0, tx=10, ty=10, sight=3)
        vm.update([entity], 0)

        # Center should be visible
        assert vm.get_visibility(0, 10, 10) == VISIBLE
        # Within radius
        assert vm.get_visibility(0, 10, 8) == VISIBLE  # 2 tiles away
        assert vm.get_visibility(0, 12, 10) == VISIBLE  # 2 tiles away
        # At radius boundary (3 tiles)
        assert vm.get_visibility(0, 10, 7) == VISIBLE  # exactly 3

    def test_tiles_outside_sight_stay_unexplored(self):
        vm = VisibilityMap(20, 20)
        entity = _make_entity(player_id=0, tx=10, ty=10, sight=3)
        vm.update([entity], 0)

        # Well outside radius
        assert vm.get_visibility(0, 0, 0) == UNEXPLORED
        assert vm.get_visibility(0, 10, 0) == UNEXPLORED

    def test_sight_uses_euclidean_distance(self):
        vm = VisibilityMap(20, 20)
        entity = _make_entity(player_id=0, tx=10, ty=10, sight=3)
        vm.update([entity], 0)

        # Diagonal: dx=3, dy=0 -> dist_sq=9, sight_sq=9 -> visible
        assert vm.get_visibility(0, 13, 10) == VISIBLE
        # Diagonal: dx=3, dy=1 -> dist_sq=10, sight_sq=9 -> not visible
        assert vm.get_visibility(0, 13, 11) == UNEXPLORED
        # Diagonal: dx=2, dy=2 -> dist_sq=8, sight_sq=9 -> visible
        assert vm.get_visibility(0, 12, 12) == VISIBLE

    def test_zero_sight_reveals_nothing(self):
        vm = VisibilityMap(20, 20)
        entity = _make_entity(player_id=0, tx=10, ty=10, sight=0)
        vm.update([entity], 0)
        assert vm.get_visibility(0, 10, 10) == UNEXPLORED


class TestFogTransition:
    def test_visible_becomes_fog_after_update(self):
        vm = VisibilityMap(20, 20)
        entity = _make_entity(player_id=0, tx=10, ty=10, sight=3)
        vm.update([entity], 0)
        assert vm.get_visibility(0, 10, 10) == VISIBLE

        # Move entity away, update again — old tiles become FOG
        entity2 = _make_entity(player_id=0, tx=5, ty=5, sight=3)
        vm.update([entity2], 0)
        assert vm.get_visibility(0, 10, 10) == FOG
        assert vm.get_visibility(0, 5, 5) == VISIBLE

    def test_fog_stays_fog_not_unexplored(self):
        vm = VisibilityMap(20, 20)
        entity = _make_entity(player_id=0, tx=10, ty=10, sight=3)
        vm.update([entity], 0)

        # Move away
        entity2 = _make_entity(player_id=0, tx=5, ty=5, sight=3)
        vm.update([entity2], 0)
        assert vm.get_visibility(0, 10, 10) == FOG

        # Move again — previously FOG stays FOG
        entity3 = _make_entity(player_id=0, tx=0, ty=0, sight=3)
        vm.update([entity3], 0)
        assert vm.get_visibility(0, 10, 10) == FOG
        assert vm.get_visibility(0, 5, 5) == FOG


class TestPerPlayer:
    def test_visibility_is_per_player(self):
        vm = VisibilityMap(20, 20)
        e0 = _make_entity(player_id=0, tx=5, ty=5, sight=3)
        e1 = _make_entity(player_id=1, tx=15, ty=15, sight=3)
        vm.update([e0, e1], 0)
        vm.update([e0, e1], 1)

        # Player 0 sees around (5,5), not around (15,15)
        assert vm.get_visibility(0, 5, 5) == VISIBLE
        assert vm.get_visibility(0, 15, 15) == UNEXPLORED

        # Player 1 sees around (15,15), not around (5,5)
        assert vm.get_visibility(1, 15, 15) == VISIBLE
        assert vm.get_visibility(1, 5, 5) == UNEXPLORED

    def test_update_only_affects_specified_player(self):
        vm = VisibilityMap(20, 20)
        e0 = _make_entity(player_id=0, tx=10, ty=10, sight=3)
        vm.update([e0], 0)
        assert vm.get_visibility(0, 10, 10) == VISIBLE
        assert vm.get_visibility(1, 10, 10) == UNEXPLORED


class TestMultipleEntities:
    def test_multiple_units_combine_vision(self):
        vm = VisibilityMap(30, 30)
        e1 = _make_entity(player_id=0, tx=5, ty=15, sight=3)
        e2 = _make_entity(player_id=0, tx=25, ty=15, sight=3)
        vm.update([e1, e2], 0)

        assert vm.get_visibility(0, 5, 15) == VISIBLE
        assert vm.get_visibility(0, 25, 15) == VISIBLE
        # Between them — not visible
        assert vm.get_visibility(0, 15, 15) == UNEXPLORED


class TestGridBytes:
    def test_get_grid_bytes_length(self):
        vm = VisibilityMap(10, 10)
        data = vm.get_grid_bytes(0)
        assert len(data) == 100

    def test_invalid_player_returns_empty(self):
        vm = VisibilityMap(10, 10)
        assert vm.get_grid_bytes(-1) == b""
        assert vm.get_grid_bytes(5) == b""
