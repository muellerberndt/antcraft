"""Scenario tests for combat mechanics."""

from src.simulation.state import EntityType
from tests.scenario import Scenario, open_map


class TestCombat:
    def test_attack_kills_enemy(self):
        """Ant attacks and kills a weak enemy (aphid)."""
        s = Scenario(open_map(20, 10))
        ant = s.add_ant(player=0, tile=(5, 5))
        aphid = s.add_aphid(tile=(7, 5))
        s.attack(ant, aphid)
        s.run(ticks=200)
        s.assert_dead(aphid)

    def test_auto_aggro_diverts_to_closer_enemy(self):
        """Attack-moving ant diverts to enemy that enters aggro range."""
        s = Scenario(open_map(30, 10))
        ant = s.add_ant(player=0, tile=(5, 5))
        far_aphid = s.add_aphid(tile=(25, 5))
        near_aphid = s.add_aphid(tile=(7, 5))
        s.attack(ant, far_aphid)
        s.run(ticks=200)
        s.assert_dead(near_aphid)

    def test_ant_dies_to_beetle(self):
        """Ant attacked by beetle eventually dies, leaves corpse."""
        s = Scenario(open_map(20, 10))
        ant = s.add_ant(player=0, tile=(5, 5), label="doomed")
        beetle = s.add_beetle(tile=(6, 5))
        s.attack(ant, beetle)
        # Ant has 20 HP, beetle does 8 DPS => dies in ~3 sec = 30 ticks.
        # Keep under CORPSE_DECAY_TICKS (150) so corpse still exists.
        s.run(ticks=50)
        s.assert_dead(ant)
        # A corpse should exist somewhere near the fight
        corpses = s.entities_of_type(EntityType.CORPSE)
        assert len(corpses) >= 1, (
            f"Expected at least 1 corpse after ant death, found {len(corpses)}"
        )
