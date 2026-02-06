"""Tests for tick logic — determinism, movement, command processing."""

from math import isqrt

from src.config import MILLI_TILES_PER_TILE
from src.simulation.commands import Command, CommandType
from src.simulation.state import GameState
from src.simulation.tick import advance_tick

# All test positions must be on walkable tiles. The tilemap for seed=0 has
# player 0's start at tile (25, 50) with a clear radius of 6, so milli-tile
# positions around (25000-30000, 48000-52000) are guaranteed walkable.
BASE_X = 25000
BASE_Y = 50000

# Tile center for the base tile (25, 50)
BASE_TILE_CENTER_X = 25 * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
BASE_TILE_CENTER_Y = 50 * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2


class TestDirectMovement:
    """Tests for direct movement (no path, just target)."""

    def test_move_toward_target(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=BASE_X, y=BASE_Y, speed=100)
        e.target_x = BASE_X + 1000
        e.target_y = BASE_Y  # straight right
        advance_tick(state, [])
        assert e.x == BASE_X + 100
        assert e.y == BASE_Y

    def test_snap_to_target_when_close(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=BASE_X, y=BASE_Y, speed=100)
        e.target_x = BASE_X + 50  # closer than speed
        e.target_y = BASE_Y
        advance_tick(state, [])
        assert e.x == BASE_X + 50
        assert e.y == BASE_Y
        assert not e.is_moving

    def test_diagonal_movement(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=BASE_X, y=BASE_Y, speed=100)
        e.target_x = BASE_X + 5000
        e.target_y = BASE_Y + 5000
        advance_tick(state, [])
        # Should move ~70 in each direction (100 / sqrt(2))
        moved_x = e.x - BASE_X
        moved_y = e.y - BASE_Y
        dist = isqrt(moved_x * moved_x + moved_y * moved_y)
        assert 95 <= dist <= 100  # integer rounding
        assert moved_x == moved_y  # symmetric movement

    def test_no_movement_at_target(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=BASE_X, y=BASE_Y)
        # target == position, no movement
        advance_tick(state, [])
        assert e.x == BASE_X
        assert e.y == BASE_Y

    def test_tick_increments(self):
        state = GameState(seed=0)
        assert state.tick == 0
        advance_tick(state, [])
        assert state.tick == 1
        advance_tick(state, [])
        assert state.tick == 2


class TestMoveCommand:
    def test_move_command_computes_path(self):
        """MOVE command should compute an A* path and set target."""
        state = GameState(seed=0)
        e = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y)
        # Target is 3 tiles to the right
        target_tile_x = 28
        target_tile_y = 50
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,
            tick=0,
            entity_ids=(e.entity_id,),
            target_x=target_tile_x * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2,
            target_y=target_tile_y * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2,
        )
        advance_tick(state, [cmd])
        # Should have a path computed
        assert e.path is not None
        # Target should be set to the destination tile center
        dest_x = target_tile_x * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
        dest_y = target_tile_y * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
        assert e.target_x == dest_x
        assert e.target_y == dest_y

    def test_cannot_move_other_players_units(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=1, x=BASE_X, y=BASE_Y)
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,  # player 0 tries to move player 1's unit
            tick=0,
            entity_ids=(e.entity_id,),
            target_x=BASE_X + 5000,
            target_y=BASE_Y + 3000,
        )
        advance_tick(state, [cmd])
        # Target should not change
        assert e.target_x == BASE_X
        assert e.target_y == BASE_Y

    def test_move_nonexistent_entity(self):
        state = GameState(seed=0)
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,
            tick=0,
            entity_ids=(999,),
            target_x=BASE_X + 5000,
            target_y=BASE_Y + 3000,
        )
        # Should not crash
        advance_tick(state, [cmd])

    def test_move_to_rock_redirects_to_nearest_walkable(self):
        """Move commands targeting non-walkable tiles redirect to nearest walkable."""
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=BASE_X, y=BASE_Y)
        # Tile (0, 0) is border rock — should redirect to nearest walkable
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,
            tick=0,
            entity_ids=(e.entity_id,),
            target_x=0,
            target_y=0,
        )
        advance_tick(state, [cmd])
        # Entity should now be moving (target changed from original position)
        assert e.target_x != BASE_X or e.target_y != BASE_Y


class TestPathFollowing:
    def test_entity_follows_path(self):
        """Entity should move along its path waypoints."""
        state = GameState(seed=0)
        e = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y, speed=100)
        # Assign a simple 3-waypoint path (1 tile right each)
        e.path = [
            (BASE_TILE_CENTER_X + 1000, BASE_TILE_CENTER_Y),
            (BASE_TILE_CENTER_X + 2000, BASE_TILE_CENTER_Y),
            (BASE_TILE_CENTER_X + 3000, BASE_TILE_CENTER_Y),
        ]
        e.target_x = e.path[-1][0]
        e.target_y = e.path[-1][1]

        advance_tick(state, [])
        # Entity should have moved toward first waypoint
        assert e.x > BASE_TILE_CENTER_X

    def test_entity_pops_waypoints(self):
        """Entity should pop waypoints as it reaches them."""
        state = GameState(seed=0)
        # Use high speed so entity reaches waypoints quickly
        e = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y, speed=1500)
        e.path = [
            (BASE_TILE_CENTER_X + 1000, BASE_TILE_CENTER_Y),
            (BASE_TILE_CENTER_X + 2000, BASE_TILE_CENTER_Y),
        ]
        e.target_x = e.path[-1][0]
        e.target_y = e.path[-1][1]

        advance_tick(state, [])
        # With speed=1500, entity should reach first waypoint (1000 away)
        # and move toward second
        assert len(e.path) < 2  # at least one waypoint popped

    def test_entity_stops_at_final_waypoint(self):
        """Entity should stop when it reaches the last waypoint."""
        state = GameState(seed=0)
        e = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y, speed=1500)
        e.path = [
            (BASE_TILE_CENTER_X + 1000, BASE_TILE_CENTER_Y),
        ]
        e.target_x = e.path[-1][0]
        e.target_y = e.path[-1][1]

        advance_tick(state, [])
        # Should have arrived at the waypoint
        assert e.x == BASE_TILE_CENTER_X + 1000
        assert e.y == BASE_TILE_CENTER_Y
        assert len(e.path) == 0
        assert not e.is_moving

    def test_stop_clears_path(self):
        """STOP command should clear path and halt entity."""
        state = GameState(seed=0)
        e = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y, speed=100)
        e.path = [
            (BASE_TILE_CENTER_X + 1000, BASE_TILE_CENTER_Y),
            (BASE_TILE_CENTER_X + 2000, BASE_TILE_CENTER_Y),
        ]
        e.target_x = e.path[-1][0]
        e.target_y = e.path[-1][1]

        cmd = Command(
            command_type=CommandType.STOP,
            player_id=0,
            tick=0,
            entity_ids=(e.entity_id,),
        )
        advance_tick(state, [cmd])
        assert e.path == []
        assert e.target_x == e.x
        assert e.target_y == e.y

    def test_move_command_path_around_rocks(self):
        """MOVE command should pathfind around obstacles."""
        state = GameState(seed=0)
        # Place entity at tile center (25, 50)
        e = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y, speed=100)
        # Target tile (28, 50) — 3 tiles to the right
        target_x = 28 * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
        target_y = 50 * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,
            tick=0,
            entity_ids=(e.entity_id,),
            target_x=target_x,
            target_y=target_y,
        )
        advance_tick(state, [cmd])
        # Should have a path and all waypoints should be on walkable tiles
        for wx, wy in e.path:
            tile_x = wx // MILLI_TILES_PER_TILE
            tile_y = wy // MILLI_TILES_PER_TILE
            assert state.tilemap.is_walkable(tile_x, tile_y)


class TestStopCommand:
    def test_stop_command(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=BASE_X, y=BASE_Y)
        e.target_x = BASE_X + 5000
        e.target_y = BASE_Y + 5000
        cmd = Command(
            command_type=CommandType.STOP,
            player_id=0,
            tick=0,
            entity_ids=(e.entity_id,),
        )
        advance_tick(state, [cmd])
        assert e.target_x == BASE_X
        assert e.target_y == BASE_Y
        assert e.path == []


class TestDeterminism:
    def test_same_inputs_same_output(self):
        """Two GameStates with same seed and same commands must produce
        identical hashes after N ticks."""
        cmds_per_tick = [
            [],
            [Command(CommandType.MOVE, player_id=0, tick=1,
                     entity_ids=(0,), target_x=BASE_X + 3000, target_y=BASE_Y + 1000)],
            [],
            [Command(CommandType.MOVE, player_id=1, tick=3,
                     entity_ids=(1,), target_x=BASE_X + 1000, target_y=BASE_Y + 2000)],
            [],
        ]

        states = []
        for _ in range(2):
            s = GameState(seed=42)
            s.create_entity(player_id=0, x=BASE_X, y=BASE_Y)
            s.create_entity(player_id=1, x=BASE_X + 2000, y=BASE_Y + 1000)
            for tick, cmds in enumerate(cmds_per_tick):
                advance_tick(s, cmds)
            states.append(s)

        assert states[0].compute_hash() == states[1].compute_hash()
        # Also check entity positions match
        for i in range(len(states[0].entities)):
            assert states[0].entities[i].x == states[1].entities[i].x
            assert states[0].entities[i].y == states[1].entities[i].y

    def test_different_inputs_different_output(self):
        s1 = GameState(seed=42)
        s1.create_entity(player_id=0, x=BASE_X, y=BASE_Y)

        s2 = GameState(seed=42)
        s2.create_entity(player_id=0, x=BASE_X, y=BASE_Y)

        cmd = Command(CommandType.MOVE, player_id=0, tick=0,
                      entity_ids=(0,), target_x=BASE_X + 3000, target_y=BASE_Y + 1000)
        advance_tick(s1, [cmd])
        advance_tick(s2, [])  # no command

        assert s1.compute_hash() != s2.compute_hash()


class TestSeparation:
    def test_overlapping_entities_pushed_apart(self):
        """Two entities at the same position should be pushed apart."""
        state = GameState(seed=0)
        e1 = state.create_entity(player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y, speed=100)
        e2 = state.create_entity(player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y, speed=100)
        advance_tick(state, [])
        # They should no longer be at exactly the same position
        assert e1.x != e2.x or e1.y != e2.y

    def test_distant_entities_unaffected(self):
        """Entities far apart should not be pushed."""
        state = GameState(seed=0)
        e1 = state.create_entity(player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y, speed=100)
        e2 = state.create_entity(player_id=0, x=BASE_TILE_CENTER_X + 5000, y=BASE_TILE_CENTER_Y, speed=100)
        x1_before, x2_before = e1.x, e2.x
        advance_tick(state, [])
        # No push — positions unchanged (no movement target either)
        assert e1.x == x1_before
        assert e2.x == x2_before

    def test_stationary_entities_not_pushed(self):
        """Hives (speed=0) should not be affected by separation."""
        from src.simulation.state import EntityType
        state = GameState(seed=0)
        # Two hives at the same spot
        h1 = state.create_entity(
            player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE, speed=0)
        h2 = state.create_entity(
            player_id=1, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y,
            entity_type=EntityType.HIVE, speed=0)
        advance_tick(state, [])
        assert h1.x == BASE_TILE_CENTER_X
        assert h2.x == BASE_TILE_CENTER_X

    def test_not_pushed_into_rocks(self):
        """Separation should not push entities into non-walkable tiles."""
        state = GameState(seed=0)
        # Place entities near a rock border (tile 1,50 is adjacent to border rock at 0,50)
        near_border_x = 1 * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
        near_border_y = 50 * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2
        e1 = state.create_entity(player_id=0, x=near_border_x, y=near_border_y, speed=100)
        # Place second entity to the right, pushing e1 left toward the border
        e2 = state.create_entity(player_id=0, x=near_border_x + 200, y=near_border_y, speed=100)
        advance_tick(state, [])
        # e1 should still be on a walkable tile
        tile_x = e1.x // MILLI_TILES_PER_TILE
        tile_y = e1.y // MILLI_TILES_PER_TILE
        assert state.tilemap.is_walkable(tile_x, tile_y)

    def test_separation_is_deterministic(self):
        """Same setup must produce identical results."""
        results = []
        for _ in range(2):
            state = GameState(seed=0)
            state.create_entity(player_id=0, x=BASE_TILE_CENTER_X, y=BASE_TILE_CENTER_Y, speed=100)
            state.create_entity(player_id=0, x=BASE_TILE_CENTER_X + 200, y=BASE_TILE_CENTER_Y, speed=100)
            state.create_entity(player_id=1, x=BASE_TILE_CENTER_X + 100, y=BASE_TILE_CENTER_Y + 100, speed=100)
            advance_tick(state, [])
            results.append([(e.x, e.y) for e in state.entities])
        assert results[0] == results[1]
