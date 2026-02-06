"""Binary serialization for commands and network messages.

All encoding uses struct for compact, deterministic binary format.
Network byte order (big-endian) throughout.

Wire format for a full message:
    [msg_type:u8][payload_len:u16][payload:bytes]

Command format within COMMANDS payload:
    [tick:u32][n_commands:u16]
    per command:
        [type:u8][player:u8][tick:u32][n_entities:u16]
        [entity_ids:u32 * n_entities][target_x:i32][target_y:i32][target_entity_id:u32]
"""

from __future__ import annotations

import struct

from src.networking.protocol import MessageType
from src.simulation.commands import Command, CommandType


# --- Message framing ---

MSG_HEADER = struct.Struct("!BH")  # msg_type (u8), payload_len (u16)


def encode_message(msg_type: MessageType, payload: bytes) -> bytes:
    """Wrap a payload in a message frame."""
    return MSG_HEADER.pack(msg_type, len(payload)) + payload


def decode_message(data: bytes) -> tuple[MessageType, bytes]:
    """Unwrap a message frame into (type, payload).

    Raises ValueError if the data is too short or malformed.
    """
    if len(data) < MSG_HEADER.size:
        raise ValueError("Message too short")
    msg_type_raw, payload_len = MSG_HEADER.unpack_from(data)
    msg_type = MessageType(msg_type_raw)
    payload = data[MSG_HEADER.size:MSG_HEADER.size + payload_len]
    if len(payload) < payload_len:
        raise ValueError("Payload truncated")
    return msg_type, payload


# --- Command serialization ---

CMD_HEADER = struct.Struct("!BBIH")   # type(u8), player(u8), tick(u32), n_entities(u16)
CMD_ENTITY = struct.Struct("!I")      # entity_id (u32)
CMD_TARGET = struct.Struct("!iiI")    # target_x(i32), target_y(i32), target_entity_id(u32)


def encode_commands(commands: list[Command], tick: int | None = None) -> bytes:
    """Encode a list of Commands into binary.

    Wire format: [tick:u32][n_commands:u16][per-command data...]
    The tick header allows empty command lists to carry their tick number.
    """
    parts: list[bytes] = []
    if tick is None:
        tick = commands[0].tick if commands else 0
    parts.append(struct.pack("!I", tick))
    parts.append(struct.pack("!H", len(commands)))
    for cmd in commands:
        parts.append(CMD_HEADER.pack(
            cmd.command_type, cmd.player_id, cmd.tick, len(cmd.entity_ids),
        ))
        for eid in cmd.entity_ids:
            parts.append(CMD_ENTITY.pack(eid))
        parts.append(CMD_TARGET.pack(cmd.target_x, cmd.target_y, cmd.target_entity_id))
    return b"".join(parts)


def decode_commands(data: bytes) -> tuple[int, list[Command]]:
    """Decode binary data into (tick, list of Commands)."""
    offset = 0
    (msg_tick,) = struct.unpack_from("!I", data, offset)
    offset += 4
    (n_commands,) = struct.unpack_from("!H", data, offset)
    offset += 2
    commands: list[Command] = []
    for _ in range(n_commands):
        cmd_type, player_id, tick, n_entities = CMD_HEADER.unpack_from(data, offset)
        offset += CMD_HEADER.size
        entity_ids: list[int] = []
        for _ in range(n_entities):
            (eid,) = CMD_ENTITY.unpack_from(data, offset)
            offset += CMD_ENTITY.size
            entity_ids.append(eid)
        target_x, target_y, target_entity_id = CMD_TARGET.unpack_from(data, offset)
        offset += CMD_TARGET.size
        commands.append(Command(
            command_type=CommandType(cmd_type),
            player_id=player_id,
            tick=tick,
            entity_ids=tuple(entity_ids),
            target_x=target_x,
            target_y=target_y,
            target_entity_id=target_entity_id,
        ))
    return msg_tick, commands


# --- Connect/ConnectAck ---

CONNECT_ACK_FMT = struct.Struct("!IIB")  # seed(u32), tick_rate(u32), player_id(u8)


def encode_connect_ack(seed: int, tick_rate: int, player_id: int) -> bytes:
    return CONNECT_ACK_FMT.pack(seed, tick_rate, player_id)


def decode_connect_ack(data: bytes) -> tuple[int, int, int]:
    """Returns (seed, tick_rate, player_id)."""
    return CONNECT_ACK_FMT.unpack(data)


# --- Hash check ---

HASH_CHECK_HEADER = struct.Struct("!I")  # tick (u32)


def encode_hash_check(tick: int, state_hash: bytes) -> bytes:
    return HASH_CHECK_HEADER.pack(tick) + state_hash


def decode_hash_check(data: bytes) -> tuple[int, bytes]:
    """Returns (tick, state_hash)."""
    (tick,) = HASH_CHECK_HEADER.unpack_from(data)
    state_hash = data[HASH_CHECK_HEADER.size:]
    return tick, state_hash
