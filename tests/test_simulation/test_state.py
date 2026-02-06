"""Tests for GameState — determinism, hashing, entity management."""

from src.simulation.state import GameState


class TestGameStateCreation:
    def test_initial_state(self):
        state = GameState(seed=123)
        assert state.tick == 0
        assert state.entities == []
        assert state.rng_state == 123
        assert state.game_over is False

    def test_create_entity(self, game_state: GameState):
        e = game_state.create_entity(player_id=0, x=5000, y=3000)
        assert e.entity_id == 0
        assert e.player_id == 0
        assert e.x == 5000
        assert e.y == 3000
        assert e.target_x == 5000  # starts at current position
        assert e.target_y == 3000

    def test_entity_ids_increment(self, game_state: GameState):
        e0 = game_state.create_entity(player_id=0, x=0, y=0)
        e1 = game_state.create_entity(player_id=1, x=1000, y=1000)
        assert e0.entity_id == 0
        assert e1.entity_id == 1

    def test_get_entity(self, game_state: GameState):
        game_state.create_entity(player_id=0, x=0, y=0)
        e1 = game_state.create_entity(player_id=1, x=1000, y=1000)
        assert game_state.get_entity(1) is e1
        assert game_state.get_entity(99) is None


class TestDeterministicPRNG:
    def test_same_seed_same_sequence(self):
        s1 = GameState(seed=42)
        s2 = GameState(seed=42)
        for _ in range(100):
            assert s1.next_random(1000) == s2.next_random(1000)

    def test_different_seed_different_sequence(self):
        s1 = GameState(seed=1)
        s2 = GameState(seed=2)
        results1 = [s1.next_random(1000) for _ in range(10)]
        results2 = [s2.next_random(1000) for _ in range(10)]
        assert results1 != results2

    def test_bound_respected(self):
        state = GameState(seed=99)
        for _ in range(200):
            val = state.next_random(10)
            assert 0 <= val < 10


class TestStateHashing:
    def test_same_state_same_hash(self):
        s1 = GameState(seed=42)
        s2 = GameState(seed=42)
        s1.create_entity(player_id=0, x=1000, y=2000)
        s2.create_entity(player_id=0, x=1000, y=2000)
        assert s1.compute_hash() == s2.compute_hash()

    def test_different_state_different_hash(self):
        s1 = GameState(seed=42)
        s2 = GameState(seed=42)
        s1.create_entity(player_id=0, x=1000, y=2000)
        s2.create_entity(player_id=0, x=1000, y=2001)  # 1 milli-tile off
        assert s1.compute_hash() != s2.compute_hash()

    def test_tick_affects_hash(self):
        s1 = GameState(seed=42)
        s2 = GameState(seed=42)
        s1.tick = 0
        s2.tick = 1
        assert s1.compute_hash() != s2.compute_hash()
