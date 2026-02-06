"""Tests for SelectionManager."""

from src.config import MILLI_TILES_PER_TILE
from src.input.selection import SelectionManager
from src.simulation.state import Entity, EntityType

MT = MILLI_TILES_PER_TILE


def _ent(eid: int, player_id: int, tx: int, ty: int,
         etype: EntityType = EntityType.ANT) -> Entity:
    """Create an entity at tile center (tx, ty)."""
    x = tx * MT + MT // 2
    y = ty * MT + MT // 2
    return Entity(
        entity_id=eid, entity_type=etype, player_id=player_id,
        x=x, y=y, target_x=x, target_y=y,
    )


class TestClickSelect:
    def test_selects_nearest_own_unit(self):
        sm = SelectionManager()
        entities = [
            _ent(0, 0, 5, 5),
            _ent(1, 0, 10, 10),
        ]
        sm.select_at(5 * MT + MT // 2, 5 * MT + MT // 2, entities, 0, 2 * MT)
        assert sm.selected_ids == {0}

    def test_selects_closest_when_multiple_in_range(self):
        sm = SelectionManager()
        entities = [
            _ent(0, 0, 5, 5),  # center at (5500, 5500)
            _ent(1, 0, 6, 5),  # center at (6500, 5500)
        ]
        # Click at (6400, 5500) — closer to entity 1
        click_x = 6 * MT + MT // 2 - 100
        click_y = 5 * MT + MT // 2
        sm.select_at(click_x, click_y, entities, 0, 3 * MT)
        assert sm.selected_ids == {1}

    def test_click_on_empty_clears_selection(self):
        sm = SelectionManager()
        sm.selected_ids = {0, 1}
        entities = [_ent(0, 0, 5, 5)]
        # Click far away
        sm.select_at(50 * MT, 50 * MT, entities, 0, 2 * MT)
        assert sm.selected_ids == set()

    def test_cannot_select_enemy_units(self):
        sm = SelectionManager()
        entities = [
            _ent(0, 1, 5, 5),  # enemy
        ]
        sm.select_at(5 * MT + MT // 2, 5 * MT + MT // 2, entities, 0, 2 * MT)
        assert sm.selected_ids == set()

    def test_cannot_select_hive(self):
        sm = SelectionManager()
        entities = [
            _ent(0, 0, 5, 5, EntityType.HIVE),
        ]
        sm.select_at(5 * MT + MT // 2, 5 * MT + MT // 2, entities, 0, 2 * MT)
        assert sm.selected_ids == set()

    def test_cannot_select_corpse(self):
        sm = SelectionManager()
        entities = [
            _ent(0, 0, 5, 5, EntityType.CORPSE),
        ]
        sm.select_at(5 * MT + MT // 2, 5 * MT + MT // 2, entities, 0, 2 * MT)
        assert sm.selected_ids == set()

    def test_cannot_select_wildlife(self):
        sm = SelectionManager()
        entities = [
            _ent(0, -1, 5, 5, EntityType.APHID),
            _ent(1, -1, 5, 5, EntityType.BEETLE),
        ]
        sm.select_at(5 * MT + MT // 2, 5 * MT + MT // 2, entities, 0, 2 * MT)
        assert sm.selected_ids == set()

    def test_can_select_queen(self):
        sm = SelectionManager()
        entities = [
            _ent(0, 0, 5, 5, EntityType.QUEEN),
        ]
        sm.select_at(5 * MT + MT // 2, 5 * MT + MT // 2, entities, 0, 2 * MT)
        assert sm.selected_ids == {0}

    def test_replaces_previous_selection(self):
        sm = SelectionManager()
        entities = [
            _ent(0, 0, 5, 5),
            _ent(1, 0, 10, 10),
        ]
        sm.select_at(5 * MT + MT // 2, 5 * MT + MT // 2, entities, 0, 2 * MT)
        assert sm.selected_ids == {0}
        sm.select_at(10 * MT + MT // 2, 10 * MT + MT // 2, entities, 0, 2 * MT)
        assert sm.selected_ids == {1}


class TestBoxSelect:
    def test_selects_all_own_in_rect(self):
        sm = SelectionManager()
        entities = [
            _ent(0, 0, 5, 5),
            _ent(1, 0, 6, 6),
            _ent(2, 0, 20, 20),  # outside
        ]
        sm.select_in_rect(4 * MT, 4 * MT, 7 * MT, 7 * MT, entities, 0)
        assert sm.selected_ids == {0, 1}

    def test_rect_order_doesnt_matter(self):
        sm = SelectionManager()
        entities = [_ent(0, 0, 5, 5)]
        # Reversed corners
        sm.select_in_rect(7 * MT, 7 * MT, 4 * MT, 4 * MT, entities, 0)
        assert sm.selected_ids == {0}

    def test_excludes_enemies(self):
        sm = SelectionManager()
        entities = [
            _ent(0, 0, 5, 5),
            _ent(1, 1, 6, 6),  # enemy
        ]
        sm.select_in_rect(4 * MT, 4 * MT, 7 * MT, 7 * MT, entities, 0)
        assert sm.selected_ids == {0}

    def test_excludes_non_selectable(self):
        sm = SelectionManager()
        entities = [
            _ent(0, 0, 5, 5, EntityType.ANT),
            _ent(1, 0, 6, 6, EntityType.HIVE),
            _ent(2, 0, 6, 5, EntityType.QUEEN),
        ]
        sm.select_in_rect(4 * MT, 4 * MT, 7 * MT, 7 * MT, entities, 0)
        assert sm.selected_ids == {0, 2}

    def test_empty_rect_clears(self):
        sm = SelectionManager()
        sm.selected_ids = {0}
        entities = [_ent(0, 0, 5, 5)]
        sm.select_in_rect(20 * MT, 20 * MT, 25 * MT, 25 * MT, entities, 0)
        assert sm.selected_ids == set()


class TestClear:
    def test_clear(self):
        sm = SelectionManager()
        sm.selected_ids = {0, 1, 2}
        sm.clear()
        assert sm.selected_ids == set()
