"""Tests for hive mechanics — income, spawning, merging, founding, win condition."""

from src.config import (
    ANT_CORPSE_JELLY,
    ANT_DAMAGE,
    ANT_HP,
    ANT_SIGHT,
    ANT_SPAWN_COOLDOWN,
    ANT_SPAWN_COST,
    ANT_SPEED,
    HIVE_HP,
    HIVE_PASSIVE_INCOME,
    HIVE_SIGHT,
    MILLI_TILES_PER_TILE,
    QUEEN_HP,
    QUEEN_MERGE_COST,
    QUEEN_SIGHT,
    QUEEN_SPEED,
    STARTING_JELLY,
    TICK_RATE,
)
from src.simulation.commands import Command, CommandType
from src.simulation.hive import (
    _income_this_tick,
    handle_found_hive,
    handle_merge_queen,
    handle_spawn_ant,
    process_hive_mechanics,
)
from src.simulation.state import EntityState, EntityType, GameState
from src.simulation.tick import advance_tick

# Positions within player 0's starting area (guaranteed walkable for seed=0)
BASE_TILE_CENTER_X = 25 * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
BASE_TILE_CENTER_Y = 50 * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2


def _make_hive(state, player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y):
    """Helper to create a hive entity."""
    return state.create_entity(
        player_id=player_id, x=x, y=y,
        entity_type=EntityType.HIVE,
        speed=0, hp=HIVE_HP, max_hp=HIVE_HP, damage=0, sight=HIVE_SIGHT,
    )


def _make_ant(state, player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y):
    """Helper to create an ant entity."""
    return state.create_entity(
        player_id=player_id, x=x, y=y,
        entity_type=EntityType.ANT,
        speed=ANT_SPEED, hp=ANT_HP, max_hp=ANT_HP,
        damage=ANT_DAMAGE, jelly_value=ANT_CORPSE_JELLY, sight=ANT_SIGHT,
    )


class TestPassiveIncome:
    """Verify hive passive jelly income."""

    def test_income_sums_to_rate_per_second(self):
        """Total income over TICK_RATE ticks must equal HIVE_PASSIVE_INCOME."""
        total = sum(_income_this_tick(HIVE_PASSIVE_INCOME, t) for t in range(TICK_RATE))
        assert total == HIVE_PASSIVE_INCOME

    def test_hive_generates_jelly(self):
        """A hive should generate jelly over a full second."""
        state = GameState(seed=0)
        _make_hive(state, player_id=0)
        initial_jelly = state.player_jelly[0]
        for _ in range(TICK_RATE):
            process_hive_mechanics(state)
            state.tick += 1
        assert state.player_jelly[0] == initial_jelly + HIVE_PASSIVE_INCOME

    def test_multiple_hives_stack_income(self):
        """Two hives for the same player should produce double income."""
        state = GameState(seed=0)
        _make_hive(state, player_id=0, x=BASE_TILE_CENTER_X)
        _make_hive(state, player_id=0, x=BASE_TILE_CENTER_X + 5000)
        initial_jelly = state.player_jelly[0]
        for _ in range(TICK_RATE):
            process_hive_mechanics(state)
            state.tick += 1
        assert state.player_jelly[0] == initial_jelly + HIVE_PASSIVE_INCOME * 2

    def test_neutral_site_no_income(self):
        """HIVE_SITE entities should not generate income."""
        state = GameState(seed=0)
        state.create_entity(
            player_id=-1, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE_SITE, speed=0, hp=0, max_hp=0, damage=0,
        )
        initial_jelly = state.player_jelly[0]
        for _ in range(TICK_RATE):
            process_hive_mechanics(state)
            state.tick += 1
        assert state.player_jelly[0] == initial_jelly


class TestSpawnAnt:
    """Verify ant spawning from hives."""

    def test_spawn_deducts_jelly(self):
        """SPAWN_ANT should deduct ANT_SPAWN_COST from player's jelly."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        initial_jelly = state.player_jelly[0]
        cmd = Command(
            command_type=CommandType.SPAWN_ANT,
            player_id=0, tick=0,
            target_entity_id=hive.entity_id,
        )
        handle_spawn_ant(state, cmd)
        assert state.player_jelly[0] == initial_jelly - ANT_SPAWN_COST

    def test_spawn_sets_cooldown(self):
        """After SPAWN_ANT, hive cooldown should be set."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        cmd = Command(
            command_type=CommandType.SPAWN_ANT,
            player_id=0, tick=0,
            target_entity_id=hive.entity_id,
        )
        handle_spawn_ant(state, cmd)
        assert hive.cooldown == ANT_SPAWN_COOLDOWN

    def test_ant_created_after_cooldown(self):
        """Ant should appear after ANT_SPAWN_COOLDOWN ticks."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        hive.cooldown = ANT_SPAWN_COOLDOWN
        initial_count = len(state.entities)
        for _ in range(ANT_SPAWN_COOLDOWN - 1):
            process_hive_mechanics(state)
            state.tick += 1
            assert len(state.entities) == initial_count  # not yet
        process_hive_mechanics(state)
        assert len(state.entities) == initial_count + 1
        new_ant = state.entities[-1]
        assert new_ant.entity_type == EntityType.ANT
        assert new_ant.player_id == 0

    def test_spawn_rejected_insufficient_jelly(self):
        """Spawn should fail if player can't afford it."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        state.player_jelly[0] = ANT_SPAWN_COST - 1
        cmd = Command(
            command_type=CommandType.SPAWN_ANT,
            player_id=0, tick=0,
            target_entity_id=hive.entity_id,
        )
        handle_spawn_ant(state, cmd)
        assert hive.cooldown == 0
        assert state.player_jelly[0] == ANT_SPAWN_COST - 1

    def test_spawn_rejected_already_spawning(self):
        """Spawn should fail if hive is already on cooldown."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        hive.cooldown = 5
        jelly_before = state.player_jelly[0]
        cmd = Command(
            command_type=CommandType.SPAWN_ANT,
            player_id=0, tick=0,
            target_entity_id=hive.entity_id,
        )
        handle_spawn_ant(state, cmd)
        assert hive.cooldown == 5  # unchanged
        assert state.player_jelly[0] == jelly_before

    def test_spawn_rejected_wrong_player(self):
        """Player 0 cannot spawn from player 1's hive."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=1)
        cmd = Command(
            command_type=CommandType.SPAWN_ANT,
            player_id=0, tick=0,
            target_entity_id=hive.entity_id,
        )
        handle_spawn_ant(state, cmd)
        assert hive.cooldown == 0

    def test_spawn_rejected_not_hive(self):
        """SPAWN_ANT targeting a non-hive entity should fail."""
        state = GameState(seed=0)
        ant = _make_ant(state, player_id=0)
        cmd = Command(
            command_type=CommandType.SPAWN_ANT,
            player_id=0, tick=0,
            target_entity_id=ant.entity_id,
        )
        jelly_before = state.player_jelly[0]
        handle_spawn_ant(state, cmd)
        assert state.player_jelly[0] == jelly_before

    def test_spawned_ant_correct_stats(self):
        """Newly spawned ant should have correct stats."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        hive.cooldown = 1  # will spawn next tick
        process_hive_mechanics(state)
        new_ant = state.entities[-1]
        assert new_ant.entity_type == EntityType.ANT
        assert new_ant.player_id == 0
        assert new_ant.hp == ANT_HP
        assert new_ant.speed == ANT_SPEED
        assert new_ant.damage == ANT_DAMAGE
        assert new_ant.jelly_value == ANT_CORPSE_JELLY
        assert new_ant.sight == ANT_SIGHT
        # Ant spawns adjacent to hive (within 1 tile)
        dx = abs(new_ant.x - hive.x)
        dy = abs(new_ant.y - hive.y)
        assert dx <= MILLI_TILES_PER_TILE and dy <= MILLI_TILES_PER_TILE


class TestMergeQueen:
    """Verify queen merging from ants."""

    def test_merge_creates_queen(self):
        """Merging enough ants should create a queen."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        ant_ids = []
        for i in range(QUEEN_MERGE_COST):
            ant = _make_ant(state, player_id=0,
                            x=hive.x + i * 100, y=hive.y)
            ant_ids.append(ant.entity_id)
        cmd = Command(
            command_type=CommandType.MERGE_QUEEN,
            player_id=0, tick=0,
            entity_ids=tuple(ant_ids),
            target_entity_id=hive.entity_id,
        )
        handle_merge_queen(state, cmd)
        queens = [e for e in state.entities if e.entity_type == EntityType.QUEEN]
        assert len(queens) == 1

    def test_merge_removes_ants(self):
        """Merged ants should be removed from entity list."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        ant_ids = []
        for i in range(QUEEN_MERGE_COST):
            ant = _make_ant(state, player_id=0,
                            x=hive.x + i * 100, y=hive.y)
            ant_ids.append(ant.entity_id)
        cmd = Command(
            command_type=CommandType.MERGE_QUEEN,
            player_id=0, tick=0,
            entity_ids=tuple(ant_ids),
            target_entity_id=hive.entity_id,
        )
        handle_merge_queen(state, cmd)
        for aid in ant_ids:
            assert state.get_entity(aid) is None

    def test_merge_rejected_too_few_ants(self):
        """Merge should fail if fewer than QUEEN_MERGE_COST ants."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        ant_ids = []
        for i in range(QUEEN_MERGE_COST - 1):
            ant = _make_ant(state, player_id=0,
                            x=hive.x + i * 100, y=hive.y)
            ant_ids.append(ant.entity_id)
        cmd = Command(
            command_type=CommandType.MERGE_QUEEN,
            player_id=0, tick=0,
            entity_ids=tuple(ant_ids),
            target_entity_id=hive.entity_id,
        )
        handle_merge_queen(state, cmd)
        queens = [e for e in state.entities if e.entity_type == EntityType.QUEEN]
        assert len(queens) == 0

    def test_merge_rejected_ants_too_far(self):
        """Merge should fail if ants are beyond MERGE_RANGE of hive."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        ant_ids = []
        for i in range(QUEEN_MERGE_COST):
            # Place ants far from hive (10 tiles away)
            ant = _make_ant(state, player_id=0,
                            x=hive.x + 10 * MILLI_TILES_PER_TILE, y=hive.y)
            ant_ids.append(ant.entity_id)
        cmd = Command(
            command_type=CommandType.MERGE_QUEEN,
            player_id=0, tick=0,
            entity_ids=tuple(ant_ids),
            target_entity_id=hive.entity_id,
        )
        handle_merge_queen(state, cmd)
        queens = [e for e in state.entities if e.entity_type == EntityType.QUEEN]
        assert len(queens) == 0

    def test_merge_rejected_wrong_player(self):
        """Cannot merge another player's ants."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        ant_ids = []
        for i in range(QUEEN_MERGE_COST):
            ant = _make_ant(state, player_id=1,
                            x=hive.x + i * 100, y=hive.y)
            ant_ids.append(ant.entity_id)
        cmd = Command(
            command_type=CommandType.MERGE_QUEEN,
            player_id=0, tick=0,
            entity_ids=tuple(ant_ids),
            target_entity_id=hive.entity_id,
        )
        handle_merge_queen(state, cmd)
        queens = [e for e in state.entities if e.entity_type == EntityType.QUEEN]
        assert len(queens) == 0

    def test_queen_stats(self):
        """Created queen should have correct stats."""
        state = GameState(seed=0)
        hive = _make_hive(state, player_id=0)
        ant_ids = []
        for i in range(QUEEN_MERGE_COST):
            ant = _make_ant(state, player_id=0,
                            x=hive.x + i * 100, y=hive.y)
            ant_ids.append(ant.entity_id)
        cmd = Command(
            command_type=CommandType.MERGE_QUEEN,
            player_id=0, tick=0,
            entity_ids=tuple(ant_ids),
            target_entity_id=hive.entity_id,
        )
        handle_merge_queen(state, cmd)
        queen = [e for e in state.entities if e.entity_type == EntityType.QUEEN][0]
        assert queen.hp == QUEEN_HP
        assert queen.max_hp == QUEEN_HP
        assert queen.speed == QUEEN_SPEED
        assert queen.damage == 0
        assert queen.sight == QUEEN_SIGHT
        assert queen.player_id == 0
        assert queen.x == hive.x
        assert queen.y == hive.y


class TestFoundHive:
    """Verify queen founding a hive at a hive site."""

    def test_queen_moves_to_site(self):
        """FOUND_HIVE should set queen target to site and state to FOUNDING."""
        state = GameState(seed=0)
        queen = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.QUEEN, speed=QUEEN_SPEED,
            hp=QUEEN_HP, max_hp=QUEEN_HP, damage=0, sight=QUEEN_SIGHT,
        )
        site = state.create_entity(
            player_id=-1,
            x=BASE_TILE_CENTER_X + 3 * MILLI_TILES_PER_TILE,
            y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE_SITE, speed=0, hp=0, max_hp=0, damage=0,
        )
        cmd = Command(
            command_type=CommandType.FOUND_HIVE,
            player_id=0, tick=0,
            entity_ids=(queen.entity_id,),
            target_entity_id=site.entity_id,
        )
        handle_found_hive(state, cmd)
        assert queen.state == EntityState.FOUNDING
        assert queen.target_x == site.x
        assert queen.target_y == site.y

    def test_queen_founds_hive_on_arrival(self):
        """Queen at a hive site in FOUNDING state should create a hive."""
        state = GameState(seed=0)
        site = state.create_entity(
            player_id=-1, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE_SITE, speed=0, hp=0, max_hp=0, damage=0,
        )
        queen = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.QUEEN, speed=QUEEN_SPEED,
            hp=QUEEN_HP, max_hp=QUEEN_HP, damage=0, sight=QUEEN_SIGHT,
        )
        queen.state = EntityState.FOUNDING

        process_hive_mechanics(state)

        # Queen and site should be removed
        assert state.get_entity(queen.entity_id) is None
        assert state.get_entity(site.entity_id) is None
        # A new hive should exist
        hives = [e for e in state.entities if e.entity_type == EntityType.HIVE]
        assert len(hives) == 1
        hive = hives[0]
        assert hive.player_id == 0
        assert hive.x == site.x
        assert hive.y == site.y

    def test_founded_hive_correct_stats(self):
        """Founded hive should have correct HP and attributes."""
        state = GameState(seed=0)
        site = state.create_entity(
            player_id=-1, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE_SITE, speed=0, hp=0, max_hp=0, damage=0,
        )
        queen = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.QUEEN, speed=QUEEN_SPEED,
            hp=QUEEN_HP, max_hp=QUEEN_HP, damage=0,
        )
        queen.state = EntityState.FOUNDING
        process_hive_mechanics(state)
        hive = [e for e in state.entities if e.entity_type == EntityType.HIVE][0]
        assert hive.hp == HIVE_HP
        assert hive.max_hp == HIVE_HP
        assert hive.speed == 0
        assert hive.damage == 0
        assert hive.sight == HIVE_SIGHT

    def test_founding_rejected_not_queen(self):
        """FOUND_HIVE with an ant should be rejected."""
        state = GameState(seed=0)
        ant = _make_ant(state, player_id=0)
        site = state.create_entity(
            player_id=-1, x=BASE_TILE_CENTER_X + 3000, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE_SITE, speed=0, hp=0, max_hp=0, damage=0,
        )
        cmd = Command(
            command_type=CommandType.FOUND_HIVE,
            player_id=0, tick=0,
            entity_ids=(ant.entity_id,),
            target_entity_id=site.entity_id,
        )
        handle_found_hive(state, cmd)
        assert ant.state == EntityState.IDLE  # unchanged

    def test_founding_rejected_not_site(self):
        """FOUND_HIVE targeting a non-site should be rejected."""
        state = GameState(seed=0)
        queen = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.QUEEN, speed=QUEEN_SPEED,
            hp=QUEEN_HP, max_hp=QUEEN_HP, damage=0,
        )
        other_hive = _make_hive(state, player_id=1,
                                x=BASE_TILE_CENTER_X + 3000)
        cmd = Command(
            command_type=CommandType.FOUND_HIVE,
            player_id=0, tick=0,
            entity_ids=(queen.entity_id,),
            target_entity_id=other_hive.entity_id,
        )
        handle_found_hive(state, cmd)
        assert queen.state == EntityState.IDLE

    def test_queen_not_founding_ignored(self):
        """Queen near site but NOT in FOUNDING state should not found."""
        state = GameState(seed=0)
        state.create_entity(
            player_id=-1, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE_SITE, speed=0, hp=0, max_hp=0, damage=0,
        )
        queen = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.QUEEN, speed=QUEEN_SPEED,
            hp=QUEEN_HP, max_hp=QUEEN_HP, damage=0,
        )
        # State is IDLE, not FOUNDING
        process_hive_mechanics(state)
        assert state.get_entity(queen.entity_id) is not None
        sites = [e for e in state.entities if e.entity_type == EntityType.HIVE_SITE]
        assert len(sites) == 1


class TestWinCondition:
    """Verify win condition checks."""

    def test_player_eliminated_when_no_hives(self):
        """Player with 0 hives should be eliminated."""
        state = GameState(seed=0)
        _make_hive(state, player_id=0)
        # Player 1 has no hive
        process_hive_mechanics(state)
        assert state.game_over is True
        assert state.winner == 0

    def test_no_win_if_both_have_hives(self):
        """Game should not end if both players have hives."""
        state = GameState(seed=0)
        _make_hive(state, player_id=0)
        _make_hive(state, player_id=1, x=BASE_TILE_CENTER_X + 5000)
        process_hive_mechanics(state)
        assert state.game_over is False

    def test_mutual_elimination_draw(self):
        """Both players losing all hives on same tick = draw."""
        state = GameState(seed=0)
        # Neither player has a hive
        process_hive_mechanics(state)
        assert state.game_over is True
        assert state.winner == -1

    def test_hive_site_not_counted(self):
        """HIVE_SITE should not count as a hive for win condition."""
        state = GameState(seed=0)
        _make_hive(state, player_id=0)
        # Player 1 only has a hive site (neutral)
        state.create_entity(
            player_id=-1, x=BASE_TILE_CENTER_X + 5000, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE_SITE, speed=0, hp=0, max_hp=0, damage=0,
        )
        process_hive_mechanics(state)
        assert state.game_over is True
        assert state.winner == 0


class TestHiveDeterminism:
    """Verify hive mechanics are deterministic."""

    def test_deterministic_spawn_cycle(self):
        """Same setup, same commands, identical hash after spawn cycle."""
        results = []
        for _ in range(2):
            state = GameState(seed=0)
            hive = _make_hive(state, player_id=0)
            _make_hive(state, player_id=1, x=BASE_TILE_CENTER_X + 50000)
            cmd = Command(
                command_type=CommandType.SPAWN_ANT,
                player_id=0, tick=0,
                target_entity_id=hive.entity_id,
            )
            advance_tick(state, [cmd])
            for _ in range(ANT_SPAWN_COOLDOWN):
                advance_tick(state, [])
            results.append(state.compute_hash())
        assert results[0] == results[1]

    def test_cooldown_affects_hash(self):
        """Two states identical except hive cooldown should have different hashes."""
        s1 = GameState(seed=0)
        h1 = _make_hive(s1, player_id=0)
        _make_hive(s1, player_id=1, x=BASE_TILE_CENTER_X + 50000)

        s2 = GameState(seed=0)
        h2 = _make_hive(s2, player_id=0)
        _make_hive(s2, player_id=1, x=BASE_TILE_CENTER_X + 50000)

        h2.cooldown = 10  # different
        assert s1.compute_hash() != s2.compute_hash()
