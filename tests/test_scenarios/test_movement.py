"""Scenario tests for movement and pathfinding."""

from src.simulation.state import EntityState
from tests.scenario import Scenario, ascii_map, open_map


class TestMovement:
    def test_move_straight_no_obstacles(self):
        """Ant moves in a straight line to target on an open map."""
        s = Scenario(open_map(20, 10))
        ant = s.add_ant(player=0, tile=(3, 5))
        s.move(ant, tile=(17, 5))
        s.run(ticks=300)
        s.assert_at(ant, tile=(17, 5))
        s.assert_state(ant, EntityState.IDLE)

    def test_move_around_wall(self):
        """Ant pathfinds around a vertical rock wall."""
        MAP = """
        ............
        ............
        .....X......
        .....X......
        .....X......
        ............
        ............
        """
        s = Scenario(ascii_map(MAP))
        ant = s.add_ant(player=0, tile=(3, 3))
        s.move(ant, tile=(8, 3))
        s.run(ticks=200)
        s.assert_at(ant, tile=(8, 3))

    def test_stop_halts_movement(self):
        """STOP command freezes ant in place."""
        s = Scenario(open_map(20, 10))
        ant = s.add_ant(player=0, tile=(3, 5))
        s.move(ant, tile=(17, 5))
        s.run(ticks=10)
        s.stop(ant)
        s.run(ticks=1)
        pos_after_stop = (s.entity(ant).x, s.entity(ant).y)
        s.run(ticks=50)
        assert s.entity(ant).x == pos_after_stop[0]
        assert s.entity(ant).y == pos_after_stop[1]

    def test_move_diagonal(self):
        """Ant moves diagonally across an open map."""
        s = Scenario(open_map(20, 12))
        ant = s.add_ant(player=0, tile=(2, 2))
        s.move(ant, tile=(15, 8))
        s.run(ticks=300)
        s.assert_at(ant, tile=(15, 8))
