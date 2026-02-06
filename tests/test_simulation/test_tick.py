"""Tests for tick logic — determinism, movement, command processing."""

from math import isqrt

from src.simulation.commands import Command, CommandType
from src.simulation.state import GameState
from src.simulation.tick import advance_tick


class TestMovement:
    def test_move_toward_target(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=0, y=0, speed=100)
        e.target_x = 1000
        e.target_y = 0  # straight right
        advance_tick(state, [])
        assert e.x == 100
        assert e.y == 0

    def test_snap_to_target_when_close(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=0, y=0, speed=100)
        e.target_x = 50  # closer than speed
        e.target_y = 0
        advance_tick(state, [])
        assert e.x == 50
        assert e.y == 0
        assert not e.is_moving

    def test_diagonal_movement(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=0, y=0, speed=100)
        e.target_x = 5000
        e.target_y = 5000
        advance_tick(state, [])
        # Should move ~70 in each direction (100 / sqrt(2))
        dist = isqrt(e.x * e.x + e.y * e.y)
        assert 95 <= dist <= 100  # integer rounding
        assert e.x == e.y  # symmetric movement

    def test_no_movement_at_target(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=500, y=500)
        # target == position, no movement
        advance_tick(state, [])
        assert e.x == 500
        assert e.y == 500

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
        e = state.create_entity(player_id=0, x=0, y=0)
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,
            tick=0,
            entity_ids=(e.entity_id,),
            target_x=5000,
            target_y=3000,
        )
        advance_tick(state, [cmd])
        assert e.target_x == 5000
        assert e.target_y == 3000

    def test_cannot_move_other_players_units(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=1, x=0, y=0)
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,  # player 0 tries to move player 1's unit
            tick=0,
            entity_ids=(e.entity_id,),
            target_x=5000,
            target_y=3000,
        )
        advance_tick(state, [cmd])
        # Target should not change
        assert e.target_x == 0
        assert e.target_y == 0

    def test_move_nonexistent_entity(self):
        state = GameState(seed=0)
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,
            tick=0,
            entity_ids=(999,),
            target_x=5000,
            target_y=3000,
        )
        # Should not crash
        advance_tick(state, [cmd])


class TestStopCommand:
    def test_stop_command(self):
        state = GameState(seed=0)
        e = state.create_entity(player_id=0, x=100, y=200)
        e.target_x = 5000
        e.target_y = 5000
        cmd = Command(
            command_type=CommandType.STOP,
            player_id=0,
            tick=0,
            entity_ids=(e.entity_id,),
        )
        advance_tick(state, [cmd])
        assert e.target_x == 100
        assert e.target_y == 200


class TestDeterminism:
    def test_same_inputs_same_output(self):
        """Two GameStates with same seed and same commands must produce
        identical hashes after N ticks."""
        cmds_per_tick = [
            [],
            [Command(CommandType.MOVE, player_id=0, tick=1,
                     entity_ids=(0,), target_x=5000, target_y=3000)],
            [],
            [Command(CommandType.MOVE, player_id=1, tick=3,
                     entity_ids=(1,), target_x=2000, target_y=8000)],
            [],
        ]

        states = []
        for _ in range(2):
            s = GameState(seed=42)
            s.create_entity(player_id=0, x=1000, y=1000)
            s.create_entity(player_id=1, x=50000, y=30000)
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
        s1.create_entity(player_id=0, x=1000, y=1000)

        s2 = GameState(seed=42)
        s2.create_entity(player_id=0, x=1000, y=1000)

        cmd = Command(CommandType.MOVE, player_id=0, tick=0,
                      entity_ids=(0,), target_x=5000, target_y=3000)
        advance_tick(s1, [cmd])
        advance_tick(s2, [])  # no command

        assert s1.compute_hash() != s2.compute_hash()
