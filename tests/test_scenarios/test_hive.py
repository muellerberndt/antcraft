"""Scenario tests for hive mechanics (spawn, merge, found, income)."""

from src.config import HIVE_PASSIVE_INCOME
from src.simulation.state import EntityType
from tests.scenario import Scenario, open_map


class TestHiveMechanics:
    def test_spawn_ant(self):
        """Spawn ant from hive deducts jelly and creates ant."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(10, 5))
        s.set_jelly(player=0, amount=50)
        ant_count_before = len(s.entities_of_type(EntityType.ANT, player=0))
        s.spawn_ant(hive, player=0)
        s.run(ticks=100)
        ant_count_after = len(s.entities_of_type(EntityType.ANT, player=0))
        assert ant_count_after == ant_count_before + 1, (
            f"Expected {ant_count_before + 1} ants, got {ant_count_after}"
        )

    def test_merge_queen(self):
        """Merge 5 ants at hive into a queen."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(10, 5))
        ants = [s.add_ant(player=0, tile=(10, 5)) for _ in range(5)]
        s.merge_queen(ants, hive, player=0)
        s.run(ticks=10)
        queens = s.entities_of_type(EntityType.QUEEN, player=0)
        assert len(queens) == 1, (
            f"Expected 1 queen after merge, got {len(queens)}"
        )

    def test_found_hive(self):
        """Queen walks to hive site and founds a new hive."""
        # Map small enough that hive exclusion zone (10 tiles) covers all
        # walkable tiles, preventing wildlife from spawning.
        s = Scenario(open_map(12, 8))
        s.add_hive(player=0, tile=(2, 4))
        queen = s.add_queen(player=0, tile=(3, 4))
        site = s.add_hive_site(tile=(8, 4))
        s.found_hive(queen, site, player=0)
        s.run(ticks=500)
        hives = s.entities_of_type(EntityType.HIVE, player=0)
        assert len(hives) == 2, (
            f"Expected 2 hives (original + founded), got {len(hives)}\n"
            + s.dump()
        )

    def test_passive_income(self):
        """Hive generates passive jelly income over time."""
        s = Scenario(open_map(20, 10))
        s.add_hive(player=0, tile=(10, 5))
        s.run(ticks=10)  # 1 second at TICK_RATE=10
        s.assert_player_jelly_gte(0, HIVE_PASSIVE_INCOME)
