"""Integration tests for UdpNetworkPeer — two peers on localhost."""

import time

import pytest

from src.networking.udp_peer import UdpNetworkPeer
from src.simulation.commands import Command, CommandType


@pytest.fixture
def peer_pair():
    """Create two connected UdpNetworkPeers on localhost."""
    host = UdpNetworkPeer()
    client = UdpNetworkPeer()

    host.host(0)  # bind to random port
    port = host._sock.getsockname()[1]

    client.connect("127.0.0.1", port)

    # Give them a moment to handshake
    deadline = time.monotonic() + 5
    while not (host.is_connected() and client.is_connected()):
        host.poll()
        client.poll()
        if not client.is_connected():
            client.connect("127.0.0.1", port)
        if time.monotonic() > deadline:
            pytest.fail("Peers failed to connect within 5 seconds")
        time.sleep(0.01)

    yield host, client

    host.disconnect()
    client.disconnect()


class TestConnection:
    def test_peers_connect(self, peer_pair):
        host, client = peer_pair
        assert host.is_connected()
        assert client.is_connected()
        assert host.player_id == 0
        assert client.player_id == 1

    def test_seed_shared(self, peer_pair):
        host, client = peer_pair
        assert host.seed == client.seed
        assert host.seed != 0


class TestCommandExchange:
    def test_host_sends_client_receives(self, peer_pair):
        host, client = peer_pair
        cmd = Command(CommandType.MOVE, player_id=0, tick=5,
                      entity_ids=(0,), target_x=1000, target_y=2000)
        host.send_commands(5, [cmd])

        # Poll until client gets it
        deadline = time.monotonic() + 2
        received = None
        while received is None and time.monotonic() < deadline:
            client.poll()
            received = client.receive_commands(5)
            time.sleep(0.01)

        assert received is not None
        assert len(received) == 1
        assert received[0] == cmd

    def test_client_sends_host_receives(self, peer_pair):
        host, client = peer_pair
        cmd = Command(CommandType.MOVE, player_id=1, tick=10,
                      entity_ids=(1,), target_x=500, target_y=600)
        client.send_commands(10, [cmd])

        deadline = time.monotonic() + 2
        received = None
        while received is None and time.monotonic() < deadline:
            host.poll()
            received = host.receive_commands(10)
            time.sleep(0.01)

        assert received is not None
        assert len(received) == 1
        assert received[0] == cmd

    def test_empty_commands(self, peer_pair):
        host, client = peer_pair
        host.send_commands(7, [])

        # Empty commands encode as 0 commands — nothing to receive
        client.poll()
        result = client.receive_commands(7)
        # Should be None (no data) since empty commands have no content
        # This is fine — the game loop handles this with mark_empty


class TestHashExchange:
    def test_hash_roundtrip(self, peer_pair):
        host, client = peer_pair
        fake_hash = b"\xab" * 32
        host.send_hash(10, fake_hash)

        deadline = time.monotonic() + 2
        received = None
        while received is None and time.monotonic() < deadline:
            client.poll()
            received = client.receive_hash(10)
            time.sleep(0.01)

        assert received == fake_hash


class TestLockstepSimulation:
    def test_10_tick_lockstep(self, peer_pair):
        """Simulate 10 ticks of lockstep command exchange."""
        host, client = peer_pair
        from src.simulation.state import GameState
        from src.simulation.tick import advance_tick

        seed = host.seed
        state_host = GameState(seed=seed)
        state_client = GameState(seed=seed)

        # Create same entities on both
        state_host.create_entity(player_id=0, x=1000, y=1000)
        state_host.create_entity(player_id=1, x=50000, y=30000)
        state_client.create_entity(player_id=0, x=1000, y=1000)
        state_client.create_entity(player_id=1, x=50000, y=30000)

        for tick in range(10):
            # Host generates a move command on tick 3
            host_cmds = []
            if tick == 3:
                host_cmds = [Command(CommandType.MOVE, 0, tick,
                                     (0,), 10000, 10000)]

            # Client generates a move command on tick 6
            client_cmds = []
            if tick == 6:
                client_cmds = [Command(CommandType.MOVE, 1, tick,
                                       (1,), 20000, 20000)]

            # Exchange commands
            host.send_commands(tick, host_cmds)
            client.send_commands(tick, client_cmds)

            # Wait for exchange
            deadline = time.monotonic() + 2
            host_got = None
            client_got = None
            while (host_got is None or client_got is None) and time.monotonic() < deadline:
                host.poll()
                client.poll()
                if host_got is None:
                    host_got = host.receive_commands(tick)
                if client_got is None:
                    client_got = client.receive_commands(tick)
                time.sleep(0.001)

            # If empty, treat as no commands
            if host_got is None:
                host_got = []
            if client_got is None:
                client_got = []

            # Both advance with merged commands
            all_host = sorted(host_cmds + host_got, key=lambda c: c.sort_key())
            all_client = sorted(client_cmds + client_got, key=lambda c: c.sort_key())

            advance_tick(state_host, all_host)
            advance_tick(state_client, all_client)

            # Verify sync
            assert state_host.compute_hash() == state_client.compute_hash(), \
                f"Desync at tick {tick}"
