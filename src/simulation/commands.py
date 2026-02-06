"""Command types and command queue.

Commands are the ONLY way players affect the simulation. All player inputs
are converted to commands, tagged with the tick they execute on, and shared
with the peer over the network. Both peers process the same commands on
the same tick, keeping the simulation in sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class CommandType(IntEnum):
    """All possible player actions."""
    MOVE = 1
    STOP = 2
    HARVEST = 3      # send ants to harvest a corpse
    SPAWN_ANT = 4    # spawn an ant from a hive
    MERGE_QUEEN = 5  # merge N ants into a queen at a hive
    FOUND_HIVE = 6   # queen founds a hive at a hive site
    ATTACK = 7       # explicitly attack a target entity (chase + fight)


@dataclass(frozen=True, slots=True)
class Command:
    """A single player action to be executed on a specific tick.

    Commands are immutable and comparable — two Commands with the same fields
    are equal. This matters for deduplication (network sends commands redundantly).

    Attributes:
        command_type: What action to perform.
        player_id: Which player issued the command (0 or 1).
        tick: The simulation tick this command executes on.
        entity_ids: Which entities this command targets (e.g. selected units).
        target_x: Target x position in milli-tiles (for MOVE).
        target_y: Target y position in milli-tiles (for MOVE).
        target_entity_id: Target entity (for HARVEST — corpse, SPAWN — hive, etc.).
    """
    command_type: CommandType
    player_id: int
    tick: int
    entity_ids: tuple[int, ...] = ()
    target_x: int = 0
    target_y: int = 0
    target_entity_id: int = 0

    def sort_key(self) -> tuple[int, int, int]:
        """Deterministic ordering: by player, then type, then tick."""
        return (self.player_id, self.command_type, self.tick)


class CommandQueue:
    """Collects commands from both players, keyed by tick.

    Usage:
        queue = CommandQueue()
        queue.add(command)
        cmds = queue.pop_tick(tick=5)  # returns all commands for tick 5
    """

    def __init__(self) -> None:
        self._commands: dict[int, list[Command]] = {}

    def add(self, command: Command) -> None:
        """Add a command to the queue."""
        tick_cmds = self._commands.setdefault(command.tick, [])
        # Deduplicate (network may send the same command multiple times)
        if command not in tick_cmds:
            tick_cmds.append(command)

    def has_tick(self, tick: int, player_id: int) -> bool:
        """Check if we have received ANY command (or empty marker) for a
        player on a given tick. Used by lockstep to know if the peer is ready."""
        # We store an empty list as a marker when a player sends no commands
        if tick not in self._commands:
            return False
        return any(c.player_id == player_id for c in self._commands[tick])

    def mark_empty(self, tick: int, player_id: int) -> None:
        """Mark that a player explicitly sent no commands for this tick.

        We insert a sentinel so has_tick() returns True.
        """
        sentinel = Command(
            command_type=CommandType.STOP,
            player_id=player_id,
            tick=tick,
            entity_ids=(),
        )
        self.add(sentinel)

    def pop_tick(self, tick: int) -> list[Command]:
        """Remove and return all commands for a tick, sorted deterministically."""
        cmds = self._commands.pop(tick, [])
        cmds.sort(key=lambda c: c.sort_key())
        return cmds
