"""Scenario tests for the harvest loop."""

from src.simulation.state import EntityState
from tests.scenario import Scenario, open_map


class TestHarvest:
    def test_harvest_specific_corpse(self):
        """Ant walks to corpse, extracts jelly, returns to hive, deposits."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(3, 5))
        ant = s.add_ant(player=0, tile=(4, 5))
        corpse = s.add_corpse(tile=(10, 5), jelly=10)
        s.harvest(ant, corpse)
        s.run(ticks=500)
        s.assert_player_jelly_gte(0, 10)

    def test_harvest_multiple_trips(self):
        """Corpse has more jelly than carry capacity — ant makes multiple trips."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(3, 5))
        ant = s.add_ant(player=0, tile=(4, 5))
        corpse = s.add_corpse(tile=(10, 5), jelly=25)
        s.harvest(ant, corpse)
        s.run(ticks=1500)
        s.assert_player_jelly_gte(0, 25)

    def test_harvest_move_finds_corpse(self):
        """Harvest-move: ant walks to area and auto-detects corpse nearby."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(3, 5))
        ant = s.add_ant(player=0, tile=(4, 5))
        corpse = s.add_corpse(tile=(10, 5), jelly=10)
        s.harvest_move([ant], tile=(9, 5))
        s.run(ticks=500)
        s.assert_player_jelly_gte(0, 5)

    def test_ant_idles_after_corpse_empty(self):
        """Ant goes idle when corpse jelly is depleted."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(3, 5))
        ant = s.add_ant(player=0, tile=(4, 5))
        corpse = s.add_corpse(tile=(6, 5), jelly=3)
        s.harvest(ant, corpse)
        s.run(ticks=500)
        s.assert_state(ant, EntityState.IDLE)
        s.assert_player_jelly_gte(0, 3)
