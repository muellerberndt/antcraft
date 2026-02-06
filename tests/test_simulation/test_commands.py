"""Tests for Command types and CommandQueue."""

from src.simulation.commands import Command, CommandType, CommandQueue


class TestCommand:
    def test_command_equality(self):
        c1 = Command(CommandType.MOVE, player_id=0, tick=5, target_x=100, target_y=200)
        c2 = Command(CommandType.MOVE, player_id=0, tick=5, target_x=100, target_y=200)
        assert c1 == c2

    def test_command_immutable(self):
        c = Command(CommandType.MOVE, player_id=0, tick=5)
        try:
            c.player_id = 1  # type: ignore
            assert False, "Should not be able to mutate frozen dataclass"
        except AttributeError:
            pass

    def test_sort_key_ordering(self):
        c_p1_move = Command(CommandType.MOVE, player_id=1, tick=5)
        c_p0_move = Command(CommandType.MOVE, player_id=0, tick=5)
        c_p0_stop = Command(CommandType.STOP, player_id=0, tick=5)
        cmds = [c_p1_move, c_p0_stop, c_p0_move]
        cmds.sort(key=lambda c: c.sort_key())
        assert cmds[0].player_id == 0  # player 0 first
        assert cmds[2].player_id == 1  # player 1 last


class TestCommandQueue:
    def test_add_and_pop(self):
        q = CommandQueue()
        c = Command(CommandType.MOVE, player_id=0, tick=3, target_x=100, target_y=200)
        q.add(c)
        result = q.pop_tick(3)
        assert result == [c]
        assert q.pop_tick(3) == []  # already popped

    def test_deduplication(self):
        q = CommandQueue()
        c = Command(CommandType.MOVE, player_id=0, tick=3, target_x=100, target_y=200)
        q.add(c)
        q.add(c)  # duplicate
        q.add(c)  # duplicate
        assert len(q.pop_tick(3)) == 1

    def test_deterministic_ordering(self):
        q = CommandQueue()
        q.add(Command(CommandType.MOVE, player_id=1, tick=5, target_x=0, target_y=0))
        q.add(Command(CommandType.MOVE, player_id=0, tick=5, target_x=0, target_y=0))
        result = q.pop_tick(5)
        assert result[0].player_id == 0  # player 0 always first
        assert result[1].player_id == 1

    def test_has_tick(self):
        q = CommandQueue()
        assert not q.has_tick(5, player_id=0)
        q.add(Command(CommandType.MOVE, player_id=0, tick=5))
        assert q.has_tick(5, player_id=0)
        assert not q.has_tick(5, player_id=1)  # no commands from player 1

    def test_mark_empty(self):
        q = CommandQueue()
        assert not q.has_tick(5, player_id=1)
        q.mark_empty(5, player_id=1)
        assert q.has_tick(5, player_id=1)
