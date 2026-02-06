"""Tests for tick logic — determinism, movement, command processing."""

from math import isqrt

from src.simulation.commands import Command, CommandType
from src.simulation.state import GameState
from src.simulation.tick import advance_tick

# All test positions must be on walkable tiles. The tilemap for seed=0 has
# player 0's start at tile (25, 50) with a clear radius of 6, so milli-tile
# positions around (25000-30000, 48000-52000) are guaranteed walkable.
BASE_X = 25000
BASE_Y = 50000


class TestMovement:
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
    def test_move_command_sets_target(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=BASE_X, y=BASE_Y)
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,
            tick=0,
            entity_ids=(e.entity_id,),
            target_x=BASE_X + 3000,
            target_y=BASE_Y + 1000,
        )
        advance_tick(state, [cmd])
        assert e.target_x == BASE_X + 3000
        assert e.target_y == BASE_Y + 1000

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

    def test_move_to_rock_rejected(self):
        """Move commands targeting non-walkable tiles are ignored."""
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=BASE_X, y=BASE_Y)
        # Tile (0, 0) is border rock
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,
            tick=0,
            entity_ids=(e.entity_id,),
            target_x=0,
            target_y=0,
        )
        advance_tick(state, [cmd])
        assert e.target_x == BASE_X  # unchanged
        assert e.target_y == BASE_Y


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
