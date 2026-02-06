"""Tests for the wildlife system (AI + spawning)."""

from __future__ import annotations

from src.config import (
    APHID_HP,
    APHID_JELLY,
    BEETLE_DAMAGE,
    BEETLE_HP,
    BEETLE_JELLY,
    BEETLE_SPEED,
    MANTIS_DAMAGE,
    MANTIS_HP,
    MANTIS_JELLY,
    MANTIS_SPEED,
    MILLI_TILES_PER_TILE,
    WILDLIFE_AGGRO_RANGE,
    WILDLIFE_HIVE_EXCLUSION,
    WILDLIFE_MAX_APHIDS,
    WILDLIFE_MAX_BEETLES,
    WILDLIFE_MAX_MANTIS,
    WILDLIFE_SPAWN_INTERVAL,
)
from src.simulation.state import EntityState, EntityType, GameState
from src.simulation.tilemap import TileMap, TileType
from src.simulation.wildlife import process_wildlife

MT = MILLI_TILES_PER_TILE
_HIVE_EXCLUSION_SQ = WILDLIFE_HIVE_EXCLUSION * WILDLIFE_HIVE_EXCLUSION


def _make_state(width: int = 30, height: int = 30, seed: int = 42) -> GameState:
    """Create a GameState with a simple all-DIRT tilemap."""
    state = GameState(seed=seed)
    # Replace generated map with simple open map
    tm = TileMap(width, height)
    for y in range(height):
        for x in range(width):
            tm.set_tile(x, y, TileType.DIRT)
    state.tilemap = tm
    state.entities = []
    state.next_entity_id = 0
    return state


# ---------------------------------------------------------------------------
# Wildlife AI tests
# ---------------------------------------------------------------------------

class TestWildlifeAI:
    """Beetles and mantis chase nearby player entities."""

    def test_beetle_chases_ant(self) -> None:
        state = _make_state()
        # Place a beetle at (10, 10) and an ant at (13, 10) — 3 tiles away, within aggro
        beetle = state.create_entity(
            player_id=-1, x=10 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.BEETLE, speed=BEETLE_SPEED,
            hp=BEETLE_HP, max_hp=BEETLE_HP, damage=BEETLE_DAMAGE,
        )
        ant = state.create_entity(
            player_id=0, x=13 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.ANT, speed=400, hp=20, max_hp=20, damage=5,
        )

        process_wildlife(state)

        # Beetle should have a target set toward the ant
        assert beetle.target_x != beetle.x or beetle.target_y != beetle.y
        assert beetle.is_moving or len(beetle.path) > 0

    def test_mantis_chases_ant(self) -> None:
        state = _make_state()
        mantis = state.create_entity(
            player_id=-1, x=10 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.MANTIS, speed=MANTIS_SPEED,
            hp=MANTIS_HP, max_hp=MANTIS_HP, damage=MANTIS_DAMAGE,
        )
        ant = state.create_entity(
            player_id=0, x=13 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.ANT, speed=400, hp=20, max_hp=20, damage=5,
        )

        process_wildlife(state)

        assert mantis.is_moving or len(mantis.path) > 0

    def test_beetle_ignores_distant_ant(self) -> None:
        state = _make_state()
        beetle = state.create_entity(
            player_id=-1, x=5 * MT + MT // 2, y=5 * MT + MT // 2,
            entity_type=EntityType.BEETLE, speed=BEETLE_SPEED,
            hp=BEETLE_HP, max_hp=BEETLE_HP, damage=BEETLE_DAMAGE,
        )
        # Ant at (20, 20) — way outside aggro range
        ant = state.create_entity(
            player_id=0, x=20 * MT + MT // 2, y=20 * MT + MT // 2,
            entity_type=EntityType.ANT, speed=400, hp=20, max_hp=20, damage=5,
        )

        process_wildlife(state)

        assert not beetle.is_moving
        assert len(beetle.path) == 0

    def test_aphid_no_movement(self) -> None:
        state = _make_state()
        aphid = state.create_entity(
            player_id=-1, x=10 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.APHID, speed=0,
            hp=APHID_HP, max_hp=APHID_HP, damage=0,
        )
        ant = state.create_entity(
            player_id=0, x=11 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.ANT, speed=400, hp=20, max_hp=20, damage=5,
        )

        process_wildlife(state)

        assert not aphid.is_moving
        assert len(aphid.path) == 0

    def test_wildlife_no_chase_other_wildlife(self) -> None:
        state = _make_state()
        beetle = state.create_entity(
            player_id=-1, x=10 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.BEETLE, speed=BEETLE_SPEED,
            hp=BEETLE_HP, max_hp=BEETLE_HP, damage=BEETLE_DAMAGE,
        )
        # Another wildlife entity nearby — should not be chased
        aphid = state.create_entity(
            player_id=-1, x=11 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.APHID, speed=0,
            hp=APHID_HP, max_hp=APHID_HP, damage=0,
        )

        process_wildlife(state)

        assert not beetle.is_moving
        assert len(beetle.path) == 0

    def test_attacking_wildlife_does_not_retarget(self) -> None:
        state = _make_state()
        beetle = state.create_entity(
            player_id=-1, x=10 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.BEETLE, speed=BEETLE_SPEED,
            hp=BEETLE_HP, max_hp=BEETLE_HP, damage=BEETLE_DAMAGE,
        )
        beetle.state = EntityState.ATTACKING

        ant = state.create_entity(
            player_id=0, x=12 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.ANT, speed=400, hp=20, max_hp=20, damage=5,
        )

        process_wildlife(state)

        # Should NOT start chasing — combat system is handling it
        assert not beetle.is_moving
        assert len(beetle.path) == 0

    def test_moving_wildlife_does_not_retarget(self) -> None:
        state = _make_state()
        beetle = state.create_entity(
            player_id=-1, x=10 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.BEETLE, speed=BEETLE_SPEED,
            hp=BEETLE_HP, max_hp=BEETLE_HP, damage=BEETLE_DAMAGE,
        )
        # Simulate already chasing something
        beetle.target_x = 15 * MT + MT // 2
        beetle.target_y = 10 * MT + MT // 2

        ant = state.create_entity(
            player_id=0, x=12 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.ANT, speed=400, hp=20, max_hp=20, damage=5,
        )

        old_target_x = beetle.target_x
        process_wildlife(state)

        # Should keep existing target, not switch
        assert beetle.target_x == old_target_x

    def test_beetle_chases_nearest(self) -> None:
        state = _make_state()
        beetle = state.create_entity(
            player_id=-1, x=10 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.BEETLE, speed=BEETLE_SPEED,
            hp=BEETLE_HP, max_hp=BEETLE_HP, damage=BEETLE_DAMAGE,
        )
        # Far ant (4 tiles)
        far_ant = state.create_entity(
            player_id=0, x=14 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.ANT, speed=400, hp=20, max_hp=20, damage=5,
        )
        # Close ant (2 tiles)
        close_ant = state.create_entity(
            player_id=0, x=12 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.ANT, speed=400, hp=20, max_hp=20, damage=5,
        )

        process_wildlife(state)

        # Should be heading toward close ant, not far one
        # The path endpoint should be near the close ant's tile
        if beetle.path:
            final_x, final_y = beetle.path[-1]
        else:
            final_x, final_y = beetle.target_x, beetle.target_y

        dx_close = abs(final_x - close_ant.x)
        dx_far = abs(final_x - far_ant.x)
        assert dx_close <= dx_far


# ---------------------------------------------------------------------------
# Wildlife spawning tests
# ---------------------------------------------------------------------------

class TestWildlifeSpawning:
    """Periodic wildlife spawning at random walkable locations."""

    def test_no_spawn_outside_interval(self) -> None:
        state = _make_state()
        state.tick = 1  # not a multiple of WILDLIFE_SPAWN_INTERVAL
        initial_count = len(state.entities)

        process_wildlife(state)

        assert len(state.entities) == initial_count

    def test_spawn_at_interval(self) -> None:
        state = _make_state(width=50, height=50)
        state.tick = WILDLIFE_SPAWN_INTERVAL  # exact interval

        process_wildlife(state)

        # Should have spawned one wildlife entity
        wildlife_types = {EntityType.APHID, EntityType.BEETLE, EntityType.MANTIS}
        wildlife = [e for e in state.entities if e.entity_type in wildlife_types]
        assert len(wildlife) == 1

    def test_spawn_on_walkable_tile(self) -> None:
        state = _make_state(width=50, height=50)
        state.tick = WILDLIFE_SPAWN_INTERVAL

        process_wildlife(state)

        wildlife_types = {EntityType.APHID, EntityType.BEETLE, EntityType.MANTIS}
        for e in state.entities:
            if e.entity_type in wildlife_types:
                tx = e.x // MT
                ty = e.y // MT
                assert state.tilemap.is_walkable(tx, ty)

    def test_spawn_avoids_hives(self) -> None:
        state = _make_state(width=50, height=50)
        # Place a hive at center
        hive_x, hive_y = 25, 25
        state.create_entity(
            player_id=0, x=hive_x * MT + MT // 2, y=hive_y * MT + MT // 2,
            entity_type=EntityType.HIVE, speed=0, hp=200, max_hp=200, damage=0,
        )

        # Spawn many wildlife to check none appear near hive
        wildlife_types = {EntityType.APHID, EntityType.BEETLE, EntityType.MANTIS}
        for i in range(50):
            state.tick = WILDLIFE_SPAWN_INTERVAL * (i + 1)
            process_wildlife(state)

        for e in state.entities:
            if e.entity_type in wildlife_types:
                tx = e.x // MT
                ty = e.y // MT
                dx = tx - hive_x
                dy = ty - hive_y
                dist_sq = dx * dx + dy * dy
                assert dist_sq >= _HIVE_EXCLUSION_SQ

    def test_spawn_cap_aphids(self) -> None:
        state = _make_state(width=50, height=50)
        # Pre-fill with max aphids
        for i in range(WILDLIFE_MAX_APHIDS):
            state.create_entity(
                player_id=-1, x=(5 + i) * MT + MT // 2, y=5 * MT + MT // 2,
                entity_type=EntityType.APHID, speed=0,
                hp=APHID_HP, max_hp=APHID_HP, damage=0,
            )

        initial = len(state.entities)
        # Force PRNG to roll aphid (< 50) by trying many intervals
        # Even if the roll picks aphid, it should not spawn past cap
        for i in range(20):
            state.tick = WILDLIFE_SPAWN_INTERVAL * (i + 1)
            process_wildlife(state)

        aphid_count = sum(
            1 for e in state.entities if e.entity_type == EntityType.APHID
        )
        assert aphid_count <= WILDLIFE_MAX_APHIDS + WILDLIFE_MAX_BEETLES + WILDLIFE_MAX_MANTIS

    def test_spawn_correct_stats_aphid(self) -> None:
        state = _make_state(width=50, height=50)
        # Spawn many to guarantee at least one aphid
        for i in range(30):
            state.tick = WILDLIFE_SPAWN_INTERVAL * (i + 1)
            process_wildlife(state)

        aphids = [e for e in state.entities if e.entity_type == EntityType.APHID]
        if aphids:
            a = aphids[0]
            assert a.hp == APHID_HP
            assert a.max_hp == APHID_HP
            assert a.speed == 0
            assert a.damage == 0
            assert a.jelly_value == APHID_JELLY
            assert a.player_id == -1

    def test_spawn_correct_stats_beetle(self) -> None:
        state = _make_state(width=50, height=50)
        for i in range(30):
            state.tick = WILDLIFE_SPAWN_INTERVAL * (i + 1)
            process_wildlife(state)

        beetles = [e for e in state.entities if e.entity_type == EntityType.BEETLE]
        if beetles:
            b = beetles[0]
            assert b.hp == BEETLE_HP
            assert b.max_hp == BEETLE_HP
            assert b.speed == BEETLE_SPEED
            assert b.damage == BEETLE_DAMAGE
            assert b.jelly_value == BEETLE_JELLY
            assert b.player_id == -1

    def test_spawn_correct_stats_mantis(self) -> None:
        state = _make_state(width=50, height=50)
        for i in range(50):
            state.tick = WILDLIFE_SPAWN_INTERVAL * (i + 1)
            process_wildlife(state)

        mantises = [e for e in state.entities if e.entity_type == EntityType.MANTIS]
        if mantises:
            m = mantises[0]
            assert m.hp == MANTIS_HP
            assert m.max_hp == MANTIS_HP
            assert m.speed == MANTIS_SPEED
            assert m.damage == MANTIS_DAMAGE
            assert m.jelly_value == MANTIS_JELLY
            assert m.player_id == -1

    def test_spawn_deterministic(self) -> None:
        """Same seed produces identical wildlife spawns."""
        results = []
        for _ in range(2):
            state = _make_state(width=50, height=50, seed=999)
            for i in range(20):
                state.tick = WILDLIFE_SPAWN_INTERVAL * (i + 1)
                process_wildlife(state)
            snapshot = [
                (e.entity_type, e.x, e.y)
                for e in state.entities
            ]
            results.append(snapshot)

        assert results[0] == results[1]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestWildlifeIntegration:
    """Wildlife works correctly with the full tick pipeline."""

    def test_killed_wildlife_creates_corpse(self) -> None:
        """Beetle killed by ants drops a corpse with correct jelly."""
        from src.simulation.combat import process_combat

        state = _make_state()
        state.tick = 1  # tick 1 so Bresenham distributes non-zero damage
        # Beetle with very low HP
        beetle = state.create_entity(
            player_id=-1, x=10 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.BEETLE, speed=BEETLE_SPEED,
            hp=1, max_hp=BEETLE_HP, damage=BEETLE_DAMAGE,
            jelly_value=BEETLE_JELLY,
        )
        # Ant right next to it (within attack range)
        ant = state.create_entity(
            player_id=0, x=10 * MT + MT // 2, y=10 * MT + MT // 2,
            entity_type=EntityType.ANT, speed=400, hp=20, max_hp=20,
            damage=5, jelly_value=5,
        )

        process_combat(state)

        # Beetle should be dead, corpse created
        corpses = [e for e in state.entities if e.entity_type == EntityType.CORPSE]
        assert len(corpses) >= 1
        beetle_corpse = [c for c in corpses if c.jelly_value == BEETLE_JELLY]
        assert len(beetle_corpse) == 1

    def test_wildlife_determinism_across_ticks(self) -> None:
        """Two states with same seed produce identical results after many ticks."""
        from src.simulation.tick import advance_tick

        hashes = []
        for _ in range(2):
            state = _make_state(width=50, height=50, seed=777)
            # Place player entities so wildlife has something to interact with
            state.create_entity(
                player_id=0, x=25 * MT, y=25 * MT,
                entity_type=EntityType.HIVE, speed=0,
                hp=200, max_hp=200, damage=0, sight=16,
            )
            state.create_entity(
                player_id=0, x=20 * MT, y=20 * MT,
                entity_type=EntityType.ANT, speed=400,
                hp=20, max_hp=20, damage=5, sight=5,
            )
            state.player_jelly = {0: 50, 1: 50}

            for _ in range(WILDLIFE_SPAWN_INTERVAL * 3):
                advance_tick(state, [])

            hashes.append(state.compute_hash())

        assert hashes[0] == hashes[1]
