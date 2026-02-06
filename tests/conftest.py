"""Shared test fixtures for AntCraft."""

from __future__ import annotations

import pytest

from src.simulation.state import GameState
from src.networking.peer import MockNetworkPeer


@pytest.fixture
def game_state() -> GameState:
    """A fresh game state with seed 42."""
    return GameState(seed=42)


@pytest.fixture
def mock_peer() -> MockNetworkPeer:
    """A mock network peer, already connected."""
    peer = MockNetworkPeer(mock_player_id=1)
    peer.host(0)
    return peer
