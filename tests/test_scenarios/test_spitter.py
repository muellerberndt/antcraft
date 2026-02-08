"""Scenario tests for the Spitter ant unit.

Tests cover: morphing, ranged attack, harvesting restriction,
merge restriction, and balance (spitter shouldn't solo a beetle).
"""

from tests.scenario import Scenario, open_map
from src.simulation.state import EntityState, EntityType
from src.config import SPITTER_MORPH_COST


def test_morph_ant_to_spitter():
    """An ant at a hive morphs into a spitter, consuming jelly."""
    s = Scenario(open_map(12, 8))
    hive = s.add_hive(player=0, tile=(3, 4), label="hive")
    ant = s.add_ant(player=0, tile=(3, 4), label="ant")
    s.set_jelly(0, 20)

    s.morph_spitter(ant, hive, player=0)
    s.run(ticks=5)

    # Ant should be gone, replaced by a spitter
    s.assert_dead(ant)
    spitters = s.entities_of_type(EntityType.SPITTER, player=0)
    assert len(spitters) == 1, f"Expected 1 spitter, got {len(spitters)}\n{s.dump()}"

    # Jelly should be deducted
    expected_jelly = 20 - SPITTER_MORPH_COST
    # Passive income from hive adds jelly, so use gte
    s.assert_player_jelly_gte(0, expected_jelly)


def test_morph_fails_without_jelly():
    """Morphing should fail if player doesn't have enough jelly."""
    s = Scenario(open_map(12, 8))
    hive = s.add_hive(player=0, tile=(3, 4), label="hive")
    ant = s.add_ant(player=0, tile=(3, 4), label="ant")
    s.set_jelly(0, SPITTER_MORPH_COST - 1)

    s.morph_spitter(ant, hive, player=0)
    s.run(ticks=5)

    # Ant should still be alive (morph failed)
    s.assert_alive(ant)
    spitters = s.entities_of_type(EntityType.SPITTER, player=0)
    assert len(spitters) == 0, f"Expected 0 spitters, got {len(spitters)}\n{s.dump()}"


def test_morph_fails_ant_too_far():
    """Morphing should fail if ant is not near the hive."""
    s = Scenario(open_map(20, 8))
    hive = s.add_hive(player=0, tile=(3, 4), label="hive")
    ant = s.add_ant(player=0, tile=(15, 4), label="far ant")
    s.set_jelly(0, 20)

    s.morph_spitter(ant, hive, player=0)
    s.run(ticks=5)

    # Ant should still be alive (too far from hive)
    s.assert_alive(ant)
    spitters = s.entities_of_type(EntityType.SPITTER, player=0)
    assert len(spitters) == 0, f"Expected 0 spitters, got {len(spitters)}\n{s.dump()}"


def test_spitter_attacks_at_range():
    """A spitter should attack enemies from 4 tiles away."""
    s = Scenario(open_map(12, 8))
    # Add a hive to suppress wildlife spawning (exclusion zone)
    s.add_hive(player=0, tile=(2, 4))
    # Place spitter and aphid 3 tiles apart (within 4-tile range)
    spitter = s.add_spitter(player=0, tile=(5, 4), label="spitter")
    aphid = s.add_aphid(tile=(8, 4), label="aphid")

    s.run(ticks=30)

    # Aphid should be dead (killed at range, 4 DPS vs 5 HP)
    s.assert_dead(aphid)
    # Spitter should still be alive (aphid has 0 damage)
    s.assert_alive(spitter)


def test_spitter_does_not_attack_out_of_range():
    """A spitter should not attack enemies beyond its 4-tile range."""
    s = Scenario(open_map(20, 8))
    # Place spitter and aphid 6 tiles apart (beyond 4-tile range)
    spitter = s.add_spitter(player=0, tile=(3, 4), label="spitter")
    aphid = s.add_aphid(tile=(10, 4), label="aphid")

    s.run(ticks=30)

    # Aphid should still be alive (out of range)
    s.assert_alive(aphid)
    s.assert_alive(spitter)


def test_spitter_cannot_harvest():
    """A spitter should not be able to harvest corpses."""
    s = Scenario(open_map(12, 8))
    hive = s.add_hive(player=0, tile=(3, 4), label="hive")
    spitter = s.add_spitter(player=0, tile=(5, 4), label="spitter")
    corpse = s.add_corpse(tile=(5, 4), jelly=10, label="corpse")

    # Try to harvest with the spitter
    s.harvest(spitter, corpse)
    s.run(ticks=30)

    # Spitter should not be carrying anything (can't harvest)
    e = s.entity(spitter)
    assert e.carrying == 0, (
        f"Spitter should not be able to harvest, but is carrying {e.carrying}\n{s.dump()}"
    )


def test_spitter_cannot_merge():
    """Spitters should not count toward queen merge."""
    s = Scenario(open_map(12, 8))
    hive = s.add_hive(player=0, tile=(3, 4), label="hive")
    # 4 ants + 1 spitter = 5 entities, but only 4 are ants
    ants = [s.add_ant(player=0, tile=(3, 4)) for _ in range(4)]
    spitter = s.add_spitter(player=0, tile=(3, 4), label="spitter")

    # Try to merge all 5 into a queen (needs 5 ants, but only 4 are ants)
    s.merge_queen(ants + [spitter], hive, player=0)
    s.run(ticks=5)

    # Queen should NOT exist (only 4 valid ants, need 5)
    queens = s.entities_of_type(EntityType.QUEEN, player=0)
    assert len(queens) == 0, (
        f"Expected no queen (spitters can't merge), got {len(queens)}\n{s.dump()}"
    )


def test_spitter_dies_to_beetle():
    """A single spitter (10 HP, 4 DPS) should not solo a beetle (80 HP, 8 DPS).

    Beetle does 8 DPS, spitter has 10 HP → spitter dies in ~1.25 sec (13 ticks).
    Spitter does 4 DPS, beetle has 80 HP → needs 20 sec to kill beetle.
    Spitter should die first.
    """
    s = Scenario(open_map(12, 8))
    spitter = s.add_spitter(player=0, tile=(3, 4), label="spitter")
    beetle = s.add_beetle(tile=(5, 4), label="beetle")

    # Attack the beetle
    s.attack(spitter, beetle)
    s.run(ticks=40)

    # Spitter should be dead, beetle should be alive
    s.assert_dead(spitter)
    s.assert_alive(beetle)


def test_combined_arms_vs_beetle():
    """3 melee ants + 2 spitters should beat a beetle with combined-arms.

    Melee ants tank at the beetle's position while spitters deal DPS from behind.
    Total DPS: 3*5 + 2*4 = 23 DPS. Beetle has 80 HP → ~3.5 sec.
    Beetle does 8 DPS to one melee ant at a time.
    """
    s = Scenario(open_map(12, 8))
    # Add hive to suppress wildlife
    s.add_hive(player=0, tile=(2, 4))
    # Place beetle and units — ants on top of beetle for instant engagement
    beetle = s.add_beetle(tile=(6, 4), label="beetle")
    ants = [s.add_ant(player=0, tile=(6, 4)) for _ in range(3)]
    # Spitters 3 tiles behind — within 4-tile range, auto-attack kicks in
    spitters = [s.add_spitter(player=0, tile=(3, 4)) for _ in range(2)]

    # Ants auto-attack at melee range. Spitters auto-attack at 4-tile range.
    s.run(ticks=50)

    # Beetle should be dead
    s.assert_dead(beetle)
    # At least some units should survive
    alive_count = sum(
        1 for e in s.state.entities
        if e.player_id == 0 and e.entity_type in (EntityType.ANT, EntityType.SPITTER)
    )
    assert alive_count > 0, f"All player units died!\n{s.dump()}"
