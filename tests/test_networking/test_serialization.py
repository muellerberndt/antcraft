"""Tests for command and message serialization."""

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
from src.simulation.commands import Command, CommandType


class TestCommandSerialization:
    def test_roundtrip_move(self):
        cmd = Command(
            command_type=CommandType.MOVE,
            player_id=0,
            tick=42,
            entity_ids=(1, 2, 3),
            target_x=5000,
            target_y=-3000,
        )
        data = encode_commands([cmd], tick=42)
        tick, result = decode_commands(data)
        assert tick == 42
        assert len(result) == 1
        assert result[0] == cmd

    def test_roundtrip_stop(self):
        cmd = Command(
            command_type=CommandType.STOP,
            player_id=1,
            tick=100,
            entity_ids=(7,),
        )
        data = encode_commands([cmd], tick=100)
        tick, result = decode_commands(data)
        assert tick == 100
        assert result[0] == cmd

    def test_roundtrip_empty(self):
        data = encode_commands([], tick=5)
        tick, result = decode_commands(data)
        assert tick == 5
        assert result == []

    def test_roundtrip_multiple(self):
        cmds = [
            Command(CommandType.MOVE, 0, 10, (1,), 100, 200),
            Command(CommandType.STOP, 1, 10, (2, 3)),
            Command(CommandType.MOVE, 0, 11, (), -500, -600),
        ]
        data = encode_commands(cmds, tick=10)
        tick, result = decode_commands(data)
        assert tick == 10
        assert result == cmds

    def test_no_entity_ids(self):
        cmd = Command(CommandType.MOVE, 0, 5, (), 100, 200)
        data = encode_commands([cmd], tick=5)
        tick, result = decode_commands(data)
        assert result[0].entity_ids == ()

    def test_negative_coordinates(self):
        cmd = Command(CommandType.MOVE, 0, 0, (0,), -2147483648, 2147483647)
        data = encode_commands([cmd], tick=0)
        tick, result = decode_commands(data)
        assert result[0].target_x == -2147483648
        assert result[0].target_y == 2147483647


class TestMessageFraming:
    def test_roundtrip(self):
        payload = b"hello"
        msg = encode_message(MessageType.COMMANDS, payload)
        msg_type, decoded_payload = decode_message(msg)
        assert msg_type == MessageType.COMMANDS
        assert decoded_payload == payload

    def test_empty_payload(self):
        msg = encode_message(MessageType.DISCONNECT, b"")
        msg_type, payload = decode_message(msg)
        assert msg_type == MessageType.DISCONNECT
        assert payload == b""


class TestConnectAck:
    def test_roundtrip(self):
        data = encode_connect_ack(seed=12345, tick_rate=10, player_id=1)
        seed, tick_rate, player_id = decode_connect_ack(data)
        assert seed == 12345
        assert tick_rate == 10
        assert player_id == 1


class TestHashCheck:
    def test_roundtrip(self):
        fake_hash = b"\x01" * 32
        data = encode_hash_check(tick=50, state_hash=fake_hash)
        tick, state_hash = decode_hash_check(data)
        assert tick == 50
        assert state_hash == fake_hash
