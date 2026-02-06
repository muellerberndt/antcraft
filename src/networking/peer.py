"""Network peer interface and mock implementation.

NetworkPeer is the abstract interface between the game loop (Dev A) and
the networking layer (Dev B). Dev A codes against this interface; Dev B
implements the real UDP version.

A MockNetworkPeer is provided so Dev A can test the full game loop locally
without any real networking.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.simulation.commands import Command


class NetworkPeer(ABC):
    """Abstract interface for P2P networking.

    The game loop calls these methods each frame. The networking layer
    handles UDP sockets, reliability, and the lockstep protocol internally.
    """

    @abstractmethod
    def connect(self, host: str, port: int) -> None:
        """Connect to a remote peer (client side)."""
        ...

    @abstractmethod
    def host(self, port: int) -> None:
        """Start listening for an incoming connection (host side)."""
        ...

    @abstractmethod
    def poll(self) -> None:
        """Process incoming network messages. Call once per frame.

        This reads from the socket and populates internal buffers.
        Non-blocking.
        """
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Whether a peer is currently connected and the game is active."""
        ...

    @abstractmethod
    def send_commands(self, tick: int, commands: list[Command]) -> None:
        """Send our commands for the given tick to the peer.

        If commands is empty, sends an empty marker so the peer knows
        we have no actions for this tick (still needed for lockstep).
        """
        ...

    @abstractmethod
    def receive_commands(self, tick: int) -> list[Command] | None:
        """Get the peer's commands for the given tick.

        Returns:
            list[Command] if the peer's commands for this tick have arrived.
            None if we're still waiting (lockstep must block/wait).
        """
        ...

    @abstractmethod
    def send_hash(self, tick: int, state_hash: bytes) -> None:
        """Send our state hash for the given tick to the peer."""
        ...

    @abstractmethod
    def receive_hash(self, tick: int) -> bytes | None:
        """Get the peer's state hash for the given tick.

        Returns:
            bytes if the peer's hash has arrived, None if still waiting.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Cleanly disconnect from the peer."""
        ...

    @abstractmethod
    def get_peer_address(self) -> tuple[str, int] | None:
        """Return the (host, port) of the connected peer, or None."""
        ...


class MockNetworkPeer(NetworkPeer):
    """Loopback mock for local testing without real networking.

    Echoes sent commands back immediately as if they came from a peer.
    Both "players" run in the same process. Useful for Dev A to test
    the game loop and simulation without waiting for the networking layer.
    """

    def __init__(self, mock_player_id: int = 1) -> None:
        self._connected = False
        self._mock_player_id = mock_player_id
        self._command_buffer: dict[int, list[Command]] = {}
        self._hash_buffer: dict[int, bytes] = {}

    def connect(self, host: str, port: int) -> None:
        self._connected = True

    def host(self, port: int) -> None:
        self._connected = True

    def poll(self) -> None:
        pass

    def is_connected(self) -> bool:
        return self._connected

    def send_commands(self, tick: int, commands: list[Command]) -> None:
        # In mock mode, the "peer" sends no commands (idle).
        # Override this in tests to inject mock peer commands.
        self._command_buffer.setdefault(tick, [])

    def receive_commands(self, tick: int) -> list[Command] | None:
        # Always ready immediately — no network delay.
        return self._command_buffer.pop(tick, [])

    def send_hash(self, tick: int, state_hash: bytes) -> None:
        self._hash_buffer[tick] = state_hash

    def receive_hash(self, tick: int) -> bytes | None:
        # Echo back our own hash (no desync possible in mock).
        return self._hash_buffer.pop(tick, None)

    def disconnect(self) -> None:
        self._connected = False

    def get_peer_address(self) -> tuple[str, int] | None:
        return ("127.0.0.1", 0) if self._connected else None

    def inject_peer_commands(self, tick: int, commands: list[Command]) -> None:
        """Test helper: inject commands as if they came from the peer."""
        self._command_buffer[tick] = commands
