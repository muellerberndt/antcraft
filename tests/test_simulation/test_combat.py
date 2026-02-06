"""Tests for the combat system — auto-attack, death, corpses, decay."""

from src.config import (
    ANT_CORPSE_JELLY,
    ATTACK_RANGE,
    CORPSE_DECAY_TICKS,
    MILLI_TILES_PER_TILE,
    TICK_RATE,
)
from src.simulation.combat import _damage_this_tick, process_combat
from src.simulation.state import EntityState, EntityType, GameState
from src.simulation.tick import advance_tick

# Positions within player 0's starting area (guaranteed walkable for seed=0)
BASE_TILE_CENTER_X = 25 * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
BASE_TILE_CENTER_Y = 50 * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2


class TestDamageDistribution:
    """Verify Bresenham-style DPS-to-per-tick damage distribution."""

    def test_damage_sums_to_dps_over_one_second(self):
        """Total damage across TICK_RATE ticks must equal the DPS value."""
        for dps in [5, 8, 10, 20]:
            total = sum(_damage_this_tick(dps, t) for t in range(TICK_RATE))
            assert total == dps, f"DPS={dps}: expected {dps}, got {total}"

    def test_zero_damage(self):
        """Zero DPS should produce zero damage every tick."""
        for t in range(TICK_RATE):
            assert _damage_this_tick(0, t) == 0

    def test_even_division(self):
        """DPS that divides evenly should give constant per-tick damage."""
        for t in range(TICK_RATE):
            assert _damage_this_tick(10, t) == 1

    def test_periodic(self):
        """Damage pattern should repeat every TICK_RATE ticks."""
        for dps in [5, 8]:
            pattern_a = [_damage_this_tick(dps, t) for t in range(TICK_RATE)]
            pattern_b = [_damage_this_tick(dps, t + TICK_RATE) for t in range(TICK_RATE)]
            assert pattern_a == pattern_b


class TestAutoAttack:
    """Verify auto-attack targeting and damage."""

    def test_ant_damages_enemy_in_range(self):
        """An ant should damage an adjacent enemy ant."""
        state = GameState(seed=0)
        state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        target = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)

        process_combat(state)
        assert target.hp == 19  # 1 damage dealt (10 DPS / 10 ticks)

    def test_no_damage_out_of_range(self):
        """Ants outside attack range should not take damage."""
        state = GameState(seed=0)
        state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        far_x = BASE_TILE_CENTER_X + (ATTACK_RANGE + 1) * MILLI_TILES_PER_TILE
        target = state.create_entity(
            player_id=1, x=far_x, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)

        process_combat(state)
        assert target.hp == 20

    def test_no_friendly_fire(self):
        """Same-team entities should not attack each other."""
        state = GameState(seed=0)
        e1 = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        e2 = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)

        process_combat(state)
        assert e1.hp == 20
        assert e2.hp == 20

    def test_attacks_nearest_enemy(self):
        """Should target the closest enemy when multiple are in range."""
        state = GameState(seed=0)
        state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        far_enemy = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 800, y=BASE_TILE_CENTER_Y,
            damage=0, hp=20, max_hp=20)
        close_enemy = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 200, y=BASE_TILE_CENTER_Y,
            damage=0, hp=20, max_hp=20)

        process_combat(state)
        assert close_enemy.hp == 19  # targeted (closer)
        assert far_enemy.hp == 20    # not targeted

    def test_attacker_state_set_to_attacking(self):
        """Attacker's state should be ATTACKING when it has a target."""
        state = GameState(seed=0)
        attacker = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            damage=0, hp=20, max_hp=20)

        process_combat(state)
        assert attacker.state == EntityState.ATTACKING

    def test_state_resets_when_no_target(self):
        """ATTACKING state should reset when no enemies are in range."""
        state = GameState(seed=0)
        attacker = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        attacker.state = EntityState.ATTACKING

        process_combat(state)
        assert attacker.state == EntityState.IDLE

    def test_mutual_combat(self):
        """Both entities should deal damage to each other on the same tick."""
        state = GameState(seed=0)
        e1 = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        e2 = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)

        process_combat(state)
        assert e1.hp == 19
        assert e2.hp == 19


class TestDeath:
    """Verify entity death and corpse creation."""

    def test_entity_dies_at_zero_hp(self):
        """Entity with hp <= 0 should be removed."""
        state = GameState(seed=0)
        attacker = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        victim = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            damage=0, hp=1, max_hp=1)

        process_combat(state)
        assert state.get_entity(victim.entity_id) is None
        assert state.get_entity(attacker.entity_id) is not None

    def test_corpse_created_on_ant_death(self):
        """Dead ant should leave a corpse with correct jelly value."""
        state = GameState(seed=0)
        state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        victim = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.ANT, damage=0, hp=1, max_hp=1)
        victim_x, victim_y = victim.x, victim.y

        process_combat(state)
        corpses = [e for e in state.entities if e.entity_type == EntityType.CORPSE]
        assert len(corpses) == 1
        corpse = corpses[0]
        assert corpse.x == victim_x
        assert corpse.y == victim_y
        assert corpse.jelly_value == ANT_CORPSE_JELLY
        assert corpse.player_id == -1
        assert corpse.hp == CORPSE_DECAY_TICKS
        assert corpse.speed == 0

    def test_hive_destroyed_no_corpse(self):
        """Destroyed hive should not leave a corpse."""
        state = GameState(seed=0)
        state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        hive = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE, damage=0, hp=1, max_hp=200, speed=0)

        process_combat(state)
        assert state.get_entity(hive.entity_id) is None
        corpses = [e for e in state.entities if e.entity_type == EntityType.CORPSE]
        assert len(corpses) == 0

    def test_both_entities_die_same_tick(self):
        """Two entities killing each other should both die and leave corpses."""
        state = GameState(seed=0)
        e1 = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=1, max_hp=20)
        e2 = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            damage=10, hp=1, max_hp=20)

        process_combat(state)
        assert state.get_entity(e1.entity_id) is None
        assert state.get_entity(e2.entity_id) is None
        corpses = [e for e in state.entities if e.entity_type == EntityType.CORPSE]
        assert len(corpses) == 2


class TestCorpseDecay:
    """Verify corpse decay and removal."""

    def test_corpse_hp_decrements(self):
        """Corpse hp should decrease by 1 each combat tick."""
        state = GameState(seed=0)
        corpse = state.create_entity(
            player_id=-1, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.CORPSE, hp=100, max_hp=100,
            jelly_value=5, speed=0, damage=0)

        process_combat(state)
        assert corpse.hp == 99

    def test_corpse_removed_when_expired(self):
        """Corpse should be removed when hp reaches 0."""
        state = GameState(seed=0)
        corpse = state.create_entity(
            player_id=-1, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.CORPSE, hp=1, max_hp=CORPSE_DECAY_TICKS,
            jelly_value=5, speed=0, damage=0)

        process_combat(state)
        assert state.get_entity(corpse.entity_id) is None

    def test_full_decay_cycle(self):
        """Corpse should survive exactly CORPSE_DECAY_TICKS combat ticks."""
        state = GameState(seed=0)
        corpse = state.create_entity(
            player_id=-1, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.CORPSE, hp=CORPSE_DECAY_TICKS,
            max_hp=CORPSE_DECAY_TICKS, jelly_value=5, speed=0, damage=0)

        for _ in range(CORPSE_DECAY_TICKS - 1):
            process_combat(state)
            assert state.get_entity(corpse.entity_id) is not None

        process_combat(state)
        assert state.get_entity(corpse.entity_id) is None


class TestHiveCombat:
    """Verify hive combat interactions."""

    def test_hive_takes_damage(self):
        """Enemy ants should damage hives."""
        state = GameState(seed=0)
        state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)
        hive = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE, damage=0, hp=200, max_hp=200, speed=0)

        process_combat(state)
        assert hive.hp == 199

    def test_hive_does_not_fight_back(self):
        """Hives should not deal damage."""
        state = GameState(seed=0)
        state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE, damage=0, hp=200, max_hp=200, speed=0)
        ant = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            damage=10, hp=20, max_hp=20)

        process_combat(state)
        assert ant.hp == 20  # hive can't fight back (damage=0)


class TestCombatDeterminism:
    """Verify combat produces identical results for identical inputs."""

    def test_deterministic_combat(self):
        """Same setup must produce identical state after multiple ticks."""
        results = []
        for _ in range(2):
            state = GameState(seed=0)
            state.create_entity(
                player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
                damage=10, hp=20, max_hp=20)
            state.create_entity(
                player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
                damage=10, hp=20, max_hp=20)
            for _ in range(10):
                advance_tick(state, [])
            results.append(state.compute_hash())
        assert results[0] == results[1]

    def test_ant_dies_after_correct_ticks(self):
        """With 10 DPS vs 20 HP, ant should die after 20 ticks (2 seconds)."""
        state = GameState(seed=0)
        state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            damage=10, hp=100, max_hp=100)  # high HP, won't die
        victim = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X + 500, y=BASE_TILE_CENTER_Y,
            damage=0, hp=20, max_hp=20)

        for tick in range(19):
            process_combat(state)
            state.tick += 1
            assert state.get_entity(victim.entity_id) is not None, f"Died too early at tick {tick}"

        process_combat(state)
        assert state.get_entity(victim.entity_id) is None
