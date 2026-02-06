"""UDP-based NetworkPeer implementation.

Implements the P2P lockstep networking protocol over UDP sockets.
Commands are sent with redundancy (3x). Connection handshake and
hash checks use simple retry-based reliability.
"""

from __future__ import annotations

import logging
import socket
import time

from src.networking.peer import NetworkPeer
from src.networking.protocol import MessageType
from src.networking.serialization import (
    decode_commands,
    decode_connect_ack,
    decode_hash_check,
    decode_message,
    encode_commands,
    encode_connect_ack,
    encode_hash_check,
    encode_message,
)
from src.simulation.commands import Command

logger = logging.getLogger(__name__)

SEND_REDUNDANCY = 3  # send each command message this many times
MAX_PACKET_SIZE = 4096
CONNECT_RETRY_MS = 1000
CONNECT_TIMEOUT_MS = 30000


class UdpNetworkPeer(NetworkPeer):
    """Real UDP network peer for P2P games."""

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._peer_addr: tuple[str, int] | None = None
        self._connected = False
        self._player_id: int = -1
        self._seed: int = 0
        self._tick_rate: int = 10

        # Buffers for received data
        self._received_commands: dict[int, list[Command]] = {}
        self._received_hashes: dict[int, bytes] = {}

        # Connection state
        self._is_host = False
        self._connect_ack_sent = False
        self._last_recv_time: float = 0.0

    @property
    def player_id(self) -> int:
        return self._player_id

    @property
    def seed(self) -> int:
        return self._seed

    def host(self, port: int) -> None:
        """Bind a UDP socket and wait for a peer to connect."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", port))
        self._sock.setblocking(False)
        self._is_host = True
        self._player_id = 0
        # Generate a random seed from system time
        self._seed = int(time.time() * 1000) & 0xFFFFFFFF
        logger.info("Hosting on port %d, seed=%d", port, self._seed)

    def connect(self, host: str, port: int) -> None:
        """Send a connect request to a host.

        Safe to call multiple times for retry — only creates the socket once.
        """
        if self._sock is None:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setblocking(False)
            self._is_host = False
        self._peer_addr = (host, port)
        # Send CONNECT message
        msg = encode_message(MessageType.CONNECT, b"")
        self._send_raw(msg)
        logger.info("Connecting to %s:%d", host, port)

    def poll(self) -> None:
        """Read all pending UDP packets and process them."""
        if self._sock is None:
            return
        while True:
            try:
                data, addr = self._sock.recvfrom(MAX_PACKET_SIZE)
            except BlockingIOError:
                break
            except OSError:
                break
            self._last_recv_time = time.monotonic()
            self._handle_packet(data, addr)

    def _handle_packet(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            msg_type, payload = decode_message(data)
        except (ValueError, KeyError):
            logger.warning("Malformed packet from %s", addr)
            return

        if msg_type == MessageType.CONNECT:
            self._handle_connect(addr)
        elif msg_type == MessageType.CONNECT_ACK:
            self._handle_connect_ack(payload)
        elif msg_type == MessageType.COMMANDS:
            self._handle_commands(payload)
        elif msg_type == MessageType.HASH_CHECK:
            self._handle_hash_check(payload)
        elif msg_type == MessageType.DISCONNECT:
            logger.info("Peer disconnected")
            self._connected = False

    def _handle_connect(self, addr: tuple[str, int]) -> None:
        if not self._is_host:
            return
        self._peer_addr = addr
        self._connected = True
        self._last_recv_time = time.monotonic()
        # Send CONNECT_ACK
        payload = encode_connect_ack(self._seed, self._tick_rate, 1)
        msg = encode_message(MessageType.CONNECT_ACK, payload)
        # Send multiple times for reliability
        for _ in range(SEND_REDUNDANCY):
            self._send_raw(msg)
        logger.info("Peer connected from %s:%d", addr[0], addr[1])

    def _handle_connect_ack(self, payload: bytes) -> None:
        if self._is_host:
            return
        seed, tick_rate, player_id = decode_connect_ack(payload)
        self._seed = seed
        self._tick_rate = tick_rate
        self._player_id = player_id
        self._connected = True
        self._last_recv_time = time.monotonic()
        logger.info("Connected! seed=%d, player_id=%d", seed, player_id)

    def _handle_commands(self, payload: bytes) -> None:
        tick, commands = decode_commands(payload)
        # Deduplicate: only store if we don't already have commands for this tick
        if tick not in self._received_commands:
            self._received_commands[tick] = commands

    def _handle_hash_check(self, payload: bytes) -> None:
        tick, state_hash = decode_hash_check(payload)
        self._received_hashes[tick] = state_hash

    def is_connected(self) -> bool:
        return self._connected

    def send_commands(self, tick: int, commands: list[Command]) -> None:
        if not self._connected:
            return
        payload = encode_commands(commands, tick=tick)
        msg = encode_message(MessageType.COMMANDS, payload)
        for _ in range(SEND_REDUNDANCY):
            self._send_raw(msg)

    def receive_commands(self, tick: int) -> list[Command] | None:
        cmds = self._received_commands.pop(tick, None)
        return cmds

    def send_hash(self, tick: int, state_hash: bytes) -> None:
        if not self._connected:
            return
        payload = encode_hash_check(tick, state_hash)
        msg = encode_message(MessageType.HASH_CHECK, payload)
        for _ in range(SEND_REDUNDANCY):
            self._send_raw(msg)

    def receive_hash(self, tick: int) -> bytes | None:
        return self._received_hashes.pop(tick, None)

    def disconnect(self) -> None:
        if self._sock is not None and self._connected:
            msg = encode_message(MessageType.DISCONNECT, b"")
            for _ in range(SEND_REDUNDANCY):
                self._send_raw(msg)
        self._connected = False
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def get_peer_address(self) -> tuple[str, int] | None:
        return self._peer_addr if self._connected else None

    def time_since_last_recv(self) -> float:
        """Seconds since last packet received. Used for timeout detection."""
        if self._last_recv_time == 0.0:
            return 0.0
        return time.monotonic() - self._last_recv_time

    def _send_raw(self, data: bytes) -> None:
        if self._sock is None or self._peer_addr is None:
            return
        try:
            self._sock.sendto(data, self._peer_addr)
        except OSError as e:
            logger.warning("Send failed: %s", e)
