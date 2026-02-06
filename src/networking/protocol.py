"""Network protocol definitions.

Defines message types and their binary format for P2P communication.
Dev B implements the actual send/receive logic; these types are the
shared contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class MessageType(IntEnum):
    """Wire message types exchanged between peers."""
    CONNECT = 1       # Client → Host: request to join
    CONNECT_ACK = 2   # Host → Client: accepted, here are game params
    COMMANDS = 3      # Commands for a tick (sent redundantly, unreliable)
    TICK_ACK = 4      # Confirm readiness to advance a tick
    HASH_CHECK = 5    # State hash for desync detection (reliable)
    DESYNC = 6        # Desync detected (reliable)
    DISCONNECT = 7    # Clean shutdown (reliable)


@dataclass(frozen=True, slots=True)
class ConnectMessage:
    """Sent by the joining player."""
    player_name: str  # for display only


@dataclass(frozen=True, slots=True)
class ConnectAckMessage:
    """Sent by the host after accepting a connection."""
    seed: int          # shared PRNG seed for deterministic simulation
    tick_rate: int     # agreed simulation tick rate
    your_player_id: int  # 0 or 1


@dataclass(frozen=True, slots=True)
class CommandsMessage:
    """Commands for a specific tick from one player."""
    tick: int
    player_id: int
    command_data: bytes  # serialized list of Commands


@dataclass(frozen=True, slots=True)
class HashCheckMessage:
    """State hash for desync detection."""
    tick: int
    state_hash: bytes  # SHA-256 digest


@dataclass(frozen=True, slots=True)
class DesyncMessage:
    """Sent when a hash mismatch is detected."""
    tick: int
    expected_hash: bytes
    actual_hash: bytes
