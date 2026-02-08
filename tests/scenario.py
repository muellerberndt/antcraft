"""Scenario test harness for high-level gameplay flow testing.

Provides a declarative API for setting up game scenarios, issuing commands,
advancing the simulation, and asserting outcomes. Designed to produce
rich failure messages that an AI coding agent can read and act on.

Usage:
    s = Scenario(open_map(20, 10))
    ant = s.add_ant(player=0, tile=(3, 5), label="scout")
    s.move(ant, tile=(17, 5))
    s.run(ticks=300)
    s.assert_at(ant, tile=(17, 5))
"""

from __future__ import annotations

import textwrap

from src.config import (
    ANT_CORPSE_JELLY,
    ANT_DAMAGE,
    ANT_HP,
    ANT_SIGHT,
    ANT_SPEED,
    APHID_DAMAGE,
    APHID_HP,
    APHID_JELLY,
    ATTACK_RANGE,
    BEETLE_DAMAGE,
    BEETLE_HP,
    BEETLE_JELLY,
    BEETLE_SPEED,
    CORPSE_DECAY_TICKS,
    HIVE_HP,
    HIVE_SIGHT,
    MANTIS_DAMAGE,
    MANTIS_HP,
    MANTIS_JELLY,
    MANTIS_SPEED,
    MILLI_TILES_PER_TILE,
    QUEEN_HP,
    QUEEN_SIGHT,
    QUEEN_SPEED,
    SPITTER_ATTACK_RANGE,
    SPITTER_CORPSE_JELLY,
    SPITTER_DAMAGE,
    SPITTER_HP,
    SPITTER_SIGHT,
    SPITTER_SPEED,
    WILDLIFE_AGGRO_RANGE,
)
from src.simulation.commands import Command, CommandType
from src.simulation.state import Entity, EntityState, EntityType, GameState
from src.simulation.tick import advance_tick
from src.simulation.tilemap import TileMap, TileType


# ---------------------------------------------------------------------------
# Map helpers
# ---------------------------------------------------------------------------

def ascii_map(text: str) -> TileMap:
    """Parse ASCII art into a TileMap. '.' = dirt, 'X' = rock.

    Leading/trailing blank lines and common indentation are stripped.
    """
    lines = textwrap.dedent(text).strip().splitlines()
    height = len(lines)
    width = max(len(line) for line in lines)
    tilemap = TileMap(width, height)
    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch == "X":
                tilemap.set_tile(x, y, TileType.ROCK)
    return tilemap


def open_map(width: int, height: int) -> TileMap:
    """All-dirt map with 1-tile rock border."""
    tilemap = TileMap(width, height)
    for x in range(width):
        tilemap.set_tile(x, 0, TileType.ROCK)
        tilemap.set_tile(x, height - 1, TileType.ROCK)
    for y in range(height):
        tilemap.set_tile(0, y, TileType.ROCK)
        tilemap.set_tile(width - 1, y, TileType.ROCK)
    return tilemap


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def _tile_center(tx: int, ty: int) -> tuple[int, int]:
    """Convert tile coords to milli-tile center position."""
    return (
        tx * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2,
        ty * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2,
    )


def _milli_to_tile(mx: int, my: int) -> tuple[int, int]:
    """Convert milli-tile position to tile coordinates."""
    return mx // MILLI_TILES_PER_TILE, my // MILLI_TILES_PER_TILE


# ---------------------------------------------------------------------------
# Entity display markers for ASCII maps
# ---------------------------------------------------------------------------

# (player0_marker, player1_marker, neutral_marker)
_MARKERS: dict[EntityType, tuple[str, str, str]] = {
    EntityType.ANT:       ("a", "A", "a"),
    EntityType.QUEEN:     ("q", "Q", "q"),
    EntityType.HIVE:      ("h", "H", "h"),
    EntityType.HIVE_SITE: ("s", "S", "s"),
    EntityType.CORPSE:    ("c", "C", "c"),
    EntityType.APHID:     ("p", "P", "p"),
    EntityType.BEETLE:    ("b", "B", "b"),
    EntityType.MANTIS:    ("m", "M", "m"),
    EntityType.SPITTER:   ("t", "T", "t"),
}

# Higher = drawn on top when entities share a tile
_DISPLAY_PRIORITY: dict[EntityType, int] = {
    EntityType.HIVE_SITE: 0,
    EntityType.CORPSE:    1,
    EntityType.APHID:     2,
    EntityType.BEETLE:    3,
    EntityType.MANTIS:    4,
    EntityType.ANT:       5,
    EntityType.SPITTER:   5,
    EntityType.QUEEN:     6,
    EntityType.HIVE:      7,
}


def _entity_marker(e: Entity) -> str:
    """Return the single-character marker for an entity."""
    markers = _MARKERS.get(e.entity_type, ("?", "?", "?"))
    if e.player_id == 0:
        return markers[0]
    elif e.player_id == 1:
        return markers[1]
    return markers[2]


# ---------------------------------------------------------------------------
# Scenario class
# ---------------------------------------------------------------------------

class Scenario:
    """High-level test harness wrapping GameState."""

    def __init__(self, tilemap: TileMap, seed: int = 42) -> None:
        self.state = GameState(seed=seed, tilemap=tilemap)
        self._pending_commands: list[Command] = []
        self._labels: dict[int, str] = {}

    # --- Entity creation -------------------------------------------------

    def add_ant(self, player: int, tile: tuple[int, int],
                label: str | None = None) -> int:
        mx, my = _tile_center(tile[0], tile[1])
        e = self.state.create_entity(
            player_id=player, x=mx, y=my,
            entity_type=EntityType.ANT,
            speed=ANT_SPEED, hp=ANT_HP, max_hp=ANT_HP,
            damage=ANT_DAMAGE, jelly_value=ANT_CORPSE_JELLY,
            sight=ANT_SIGHT,
        )
        if label:
            self._labels[e.entity_id] = label
        return e.entity_id

    def add_hive(self, player: int, tile: tuple[int, int],
                 label: str | None = None) -> int:
        mx, my = _tile_center(tile[0], tile[1])
        e = self.state.create_entity(
            player_id=player, x=mx, y=my,
            entity_type=EntityType.HIVE,
            speed=0, hp=HIVE_HP, max_hp=HIVE_HP,
            damage=0, sight=HIVE_SIGHT,
        )
        if label:
            self._labels[e.entity_id] = label
        return e.entity_id

    def add_corpse(self, tile: tuple[int, int], jelly: int,
                   label: str | None = None) -> int:
        mx, my = _tile_center(tile[0], tile[1])
        e = self.state.create_entity(
            player_id=-1, x=mx, y=my,
            entity_type=EntityType.CORPSE,
            speed=0, hp=CORPSE_DECAY_TICKS, max_hp=CORPSE_DECAY_TICKS,
            damage=0, jelly_value=jelly, sight=0,
        )
        if label:
            self._labels[e.entity_id] = label
        return e.entity_id

    def add_queen(self, player: int, tile: tuple[int, int],
                  label: str | None = None) -> int:
        mx, my = _tile_center(tile[0], tile[1])
        e = self.state.create_entity(
            player_id=player, x=mx, y=my,
            entity_type=EntityType.QUEEN,
            speed=QUEEN_SPEED, hp=QUEEN_HP, max_hp=QUEEN_HP,
            damage=0, sight=QUEEN_SIGHT,
        )
        if label:
            self._labels[e.entity_id] = label
        return e.entity_id

    def add_hive_site(self, tile: tuple[int, int],
                      label: str | None = None) -> int:
        mx, my = _tile_center(tile[0], tile[1])
        e = self.state.create_entity(
            player_id=-1, x=mx, y=my,
            entity_type=EntityType.HIVE_SITE,
            speed=0, hp=0, max_hp=0, damage=0, sight=0,
        )
        # Also register it in the tilemap's hive_site_positions list
        self.state.tilemap.hive_site_positions.append(tile)
        if label:
            self._labels[e.entity_id] = label
        return e.entity_id

    def add_aphid(self, tile: tuple[int, int],
                  label: str | None = None) -> int:
        mx, my = _tile_center(tile[0], tile[1])
        e = self.state.create_entity(
            player_id=-1, x=mx, y=my,
            entity_type=EntityType.APHID,
            speed=0, hp=APHID_HP, max_hp=APHID_HP,
            damage=APHID_DAMAGE, jelly_value=APHID_JELLY, sight=0,
        )
        if label:
            self._labels[e.entity_id] = label
        return e.entity_id

    def add_beetle(self, tile: tuple[int, int],
                   label: str | None = None) -> int:
        mx, my = _tile_center(tile[0], tile[1])
        e = self.state.create_entity(
            player_id=-1, x=mx, y=my,
            entity_type=EntityType.BEETLE,
            speed=BEETLE_SPEED, hp=BEETLE_HP, max_hp=BEETLE_HP,
            damage=BEETLE_DAMAGE, jelly_value=BEETLE_JELLY,
            sight=WILDLIFE_AGGRO_RANGE,
        )
        if label:
            self._labels[e.entity_id] = label
        return e.entity_id

    def add_mantis(self, tile: tuple[int, int],
                   label: str | None = None) -> int:
        mx, my = _tile_center(tile[0], tile[1])
        e = self.state.create_entity(
            player_id=-1, x=mx, y=my,
            entity_type=EntityType.MANTIS,
            speed=MANTIS_SPEED, hp=MANTIS_HP, max_hp=MANTIS_HP,
            damage=MANTIS_DAMAGE, jelly_value=MANTIS_JELLY,
            sight=WILDLIFE_AGGRO_RANGE,
        )
        if label:
            self._labels[e.entity_id] = label
        return e.entity_id

    def add_spitter(self, player: int, tile: tuple[int, int],
                    label: str | None = None) -> int:
        mx, my = _tile_center(tile[0], tile[1])
        e = self.state.create_entity(
            player_id=player, x=mx, y=my,
            entity_type=EntityType.SPITTER,
            speed=SPITTER_SPEED, hp=SPITTER_HP, max_hp=SPITTER_HP,
            damage=SPITTER_DAMAGE, jelly_value=SPITTER_CORPSE_JELLY,
            sight=SPITTER_SIGHT, attack_range=SPITTER_ATTACK_RANGE,
        )
        if label:
            self._labels[e.entity_id] = label
        return e.entity_id

    # --- Commands --------------------------------------------------------

    def move(self, entity_id: int, tile: tuple[int, int]) -> None:
        e = self.entity(entity_id)
        mx, my = _tile_center(tile[0], tile[1])
        self._pending_commands.append(Command(
            command_type=CommandType.MOVE,
            player_id=e.player_id,
            tick=self.state.tick + 1,
            entity_ids=(entity_id,),
            target_x=mx,
            target_y=my,
        ))

    def attack(self, entity_id: int, target_entity_id: int) -> None:
        e = self.entity(entity_id)
        self._pending_commands.append(Command(
            command_type=CommandType.ATTACK,
            player_id=e.player_id,
            tick=self.state.tick + 1,
            entity_ids=(entity_id,),
            target_entity_id=target_entity_id,
        ))

    def harvest(self, entity_id: int, corpse_entity_id: int) -> None:
        e = self.entity(entity_id)
        self._pending_commands.append(Command(
            command_type=CommandType.HARVEST,
            player_id=e.player_id,
            tick=self.state.tick + 1,
            entity_ids=(entity_id,),
            target_entity_id=corpse_entity_id,
        ))

    def harvest_move(self, entity_ids: list[int],
                     tile: tuple[int, int]) -> None:
        first = self.entity(entity_ids[0])
        mx, my = _tile_center(tile[0], tile[1])
        self._pending_commands.append(Command(
            command_type=CommandType.HARVEST,
            player_id=first.player_id,
            tick=self.state.tick + 1,
            entity_ids=tuple(entity_ids),
            target_x=mx,
            target_y=my,
            target_entity_id=-1,
        ))

    def stop(self, entity_id: int) -> None:
        e = self.entity(entity_id)
        self._pending_commands.append(Command(
            command_type=CommandType.STOP,
            player_id=e.player_id,
            tick=self.state.tick + 1,
            entity_ids=(entity_id,),
        ))

    def spawn_ant(self, hive_entity_id: int, player: int) -> None:
        self._pending_commands.append(Command(
            command_type=CommandType.SPAWN_ANT,
            player_id=player,
            tick=self.state.tick + 1,
            target_entity_id=hive_entity_id,
        ))

    def merge_queen(self, ant_ids: list[int], hive_entity_id: int,
                    player: int) -> None:
        self._pending_commands.append(Command(
            command_type=CommandType.MERGE_QUEEN,
            player_id=player,
            tick=self.state.tick + 1,
            entity_ids=tuple(ant_ids),
            target_entity_id=hive_entity_id,
        ))

    def found_hive(self, queen_id: int, site_id: int,
                   player: int) -> None:
        self._pending_commands.append(Command(
            command_type=CommandType.FOUND_HIVE,
            player_id=player,
            tick=self.state.tick + 1,
            entity_ids=(queen_id,),
            target_entity_id=site_id,
        ))

    def morph_spitter(self, ant_id: int, hive_entity_id: int,
                      player: int) -> None:
        self._pending_commands.append(Command(
            command_type=CommandType.MORPH_SPITTER,
            player_id=player,
            tick=self.state.tick + 1,
            entity_ids=(ant_id,),
            target_entity_id=hive_entity_id,
        ))

    # --- Simulation ------------------------------------------------------

    def run(self, ticks: int) -> None:
        """Advance the simulation by N ticks.

        Pending commands are injected on the first tick, then cleared.
        """
        for i in range(ticks):
            if i == 0 and self._pending_commands:
                cmds = sorted(
                    self._pending_commands, key=lambda c: c.sort_key(),
                )
                advance_tick(self.state, cmds)
                self._pending_commands.clear()
            else:
                advance_tick(self.state, [])

    def set_jelly(self, player: int, amount: int) -> None:
        """Set a player's jelly count directly."""
        self.state.player_jelly[player] = amount

    # --- Queries ---------------------------------------------------------

    def entity(self, entity_id: int) -> Entity:
        """Get an entity by ID. Raises KeyError if not found."""
        e = self.state.get_entity(entity_id)
        if e is None:
            raise KeyError(
                f"Entity {self._entity_label(entity_id)} not found "
                f"(dead or never existed). Tick: {self.state.tick}"
            )
        return e

    def entity_at(self, tile: tuple[int, int]) -> Entity | None:
        """Find an entity at the given tile (1-tile tolerance)."""
        tx, ty = tile
        for e in self.state.entities:
            ex, ey = _milli_to_tile(e.x, e.y)
            if abs(ex - tx) <= 1 and abs(ey - ty) <= 1:
                return e
        return None

    def get_player_jelly(self, player_id: int) -> int:
        """Return a player's current jelly count."""
        return self.state.player_jelly.get(player_id, 0)

    def entities_of_type(self, etype: EntityType,
                         player: int | None = None) -> list[int]:
        """Return entity IDs matching the given type and optional player."""
        result = []
        for e in self.state.entities:
            if e.entity_type == etype:
                if player is None or e.player_id == player:
                    result.append(e.entity_id)
        return result

    # --- Assertions ------------------------------------------------------

    def assert_at(self, entity_id: int, tile: tuple[int, int],
                  tolerance: int = 1) -> None:
        """Assert entity is within `tolerance` tiles of the target tile."""
        e = self.entity(entity_id)
        ex, ey = _milli_to_tile(e.x, e.y)
        tx, ty = tile
        if abs(ex - tx) <= tolerance and abs(ey - ty) <= tolerance:
            return
        raise AssertionError(self._format_assertion(
            "assert_at", entity_id,
            details=[
                f"Expected tile: ({tx}, {ty}) +/- {tolerance} tile(s)",
                f"Actual tile:   ({ex}, {ey})",
                f"Actual milli:  ({e.x}, {e.y})",
            ],
        ))

    def assert_state(self, entity_id: int, expected: EntityState) -> None:
        """Assert entity is in the expected state."""
        e = self.entity(entity_id)
        if e.state == expected:
            return
        raise AssertionError(self._format_assertion(
            "assert_state", entity_id,
            details=[
                f"Expected state: {expected.name}",
                f"Actual state:   {e.state.name}",
            ],
        ))

    def assert_carrying(self, entity_id: int, amount: int) -> None:
        """Assert entity is carrying exactly `amount` jelly."""
        e = self.entity(entity_id)
        if e.carrying == amount:
            return
        raise AssertionError(self._format_assertion(
            "assert_carrying", entity_id,
            details=[
                f"Expected carrying: {amount}",
                f"Actual carrying:   {e.carrying}",
            ],
        ))

    def assert_carrying_gte(self, entity_id: int, amount: int) -> None:
        """Assert entity is carrying at least `amount` jelly."""
        e = self.entity(entity_id)
        if e.carrying >= amount:
            return
        raise AssertionError(self._format_assertion(
            "assert_carrying_gte", entity_id,
            details=[
                f"Expected carrying >= {amount}",
                f"Actual carrying:     {e.carrying}",
            ],
        ))

    def assert_alive(self, entity_id: int) -> None:
        """Assert entity exists and has HP > 0."""
        e = self.state.get_entity(entity_id)
        if e is not None and e.hp > 0:
            return
        if e is None:
            raise AssertionError(self._format_assertion(
                "assert_alive", entity_id,
                details=["Entity not found (removed from game)."],
            ))
        raise AssertionError(self._format_assertion(
            "assert_alive", entity_id,
            details=[f"Entity HP is {e.hp} (expected > 0)."],
        ))

    def assert_dead(self, entity_id: int) -> None:
        """Assert entity is dead (removed or HP <= 0)."""
        e = self.state.get_entity(entity_id)
        if e is None or e.hp <= 0:
            return
        raise AssertionError(self._format_assertion(
            "assert_dead", entity_id,
            details=[
                f"Expected entity to be dead, but it is alive.",
                f"HP: {e.hp}/{e.max_hp}",
            ],
        ))

    def assert_player_jelly(self, player_id: int, amount: int) -> None:
        """Assert player has exactly `amount` jelly."""
        actual = self.state.player_jelly.get(player_id, 0)
        if actual == amount:
            return
        raise AssertionError(self._format_assertion(
            "assert_player_jelly", entity_id=None,
            details=[
                f"Player {player_id} jelly:",
                f"  Expected: {amount}",
                f"  Actual:   {actual}",
            ],
        ))

    def assert_player_jelly_gte(self, player_id: int, amount: int) -> None:
        """Assert player has at least `amount` jelly."""
        actual = self.state.player_jelly.get(player_id, 0)
        if actual >= amount:
            return
        raise AssertionError(self._format_assertion(
            "assert_player_jelly_gte", entity_id=None,
            details=[
                f"Player {player_id} jelly:",
                f"  Expected >= {amount}",
                f"  Actual:     {actual}",
            ],
        ))

    # --- Debugging -------------------------------------------------------

    def dump(self) -> str:
        """Return a human-readable ASCII dump of the current game state.

        Shows the map with entity markers, an entity legend table,
        jelly counts, and the current tick. Designed for AI agent debugging.
        """
        tm = self.state.tilemap
        w, h = tm.width, tm.height

        # Build 2D character grid from tilemap
        grid: list[list[str]] = []
        for y in range(h):
            row = []
            for x in range(w):
                row.append("X" if tm.get_tile(x, y) == TileType.ROCK else ".")
            grid.append(row)

        # Place entity markers (higher priority wins)
        tile_entities: dict[tuple[int, int], Entity] = {}
        for e in self.state.entities:
            tx, ty = _milli_to_tile(e.x, e.y)
            key = (tx, ty)
            existing = tile_entities.get(key)
            if existing is None or _DISPLAY_PRIORITY.get(
                e.entity_type, 0
            ) > _DISPLAY_PRIORITY.get(existing.entity_type, 0):
                tile_entities[key] = e

        for (tx, ty), e in tile_entities.items():
            if 0 <= tx < w and 0 <= ty < h:
                grid[ty][tx] = _entity_marker(e)

        # Render map
        lines: list[str] = []
        lines.append(f"=== Scenario State at tick {self.state.tick} ===")
        lines.append("")

        # Column header
        col_header = "  " + "".join(str(x % 10) for x in range(w))
        lines.append(f"Map ({w}x{h}):")
        lines.append(col_header)
        for y in range(h):
            row_str = "".join(grid[y])
            lines.append(f"{y:2d} {row_str}")

        lines.append("")
        lines.append(
            "Markers: lowercase=p0 UPPERCASE=p1 "
            "a/A=ant t/T=spitter q/Q=queen h/H=hive s=site c=corpse "
            "p=aphid b=beetle m=mantis"
        )

        # Entity legend table
        lines.append("")
        lines.append(
            f"  {'ID':>3}  {'Type':<10} {'Player':<7} {'Tile':<8} "
            f"{'State':<12} {'HP':<8} {'Carry':<6} {'Label'}"
        )
        lines.append("  " + "-" * 72)
        for e in self.state.entities:
            tx, ty = _milli_to_tile(e.x, e.y)
            label = self._labels.get(e.entity_id, "-")
            player_str = f"p{e.player_id}" if e.player_id >= 0 else "neutral"
            lines.append(
                f"  {e.entity_id:>3}  {e.entity_type.name:<10} "
                f"{player_str:<7} ({tx},{ty}){'':<{max(0, 4 - len(str(tx)) - len(str(ty)))}} "
                f"{e.state.name:<12} {e.hp}/{e.max_hp:<5} "
                f"{e.carrying:<6} {label}"
            )

        # Jelly
        jelly_parts = [
            f"p{pid}={j}" for pid, j in sorted(self.state.player_jelly.items())
        ]
        lines.append("")
        lines.append(f"Jelly: {', '.join(jelly_parts)}")
        lines.append(f"Tick: {self.state.tick}")

        return "\n".join(lines)

    # --- Internal helpers ------------------------------------------------

    def _entity_label(self, entity_id: int) -> str:
        """Return a display string like 'ant#3 \"scout\"' for messages."""
        e = self.state.get_entity(entity_id)
        type_name = e.entity_type.name.lower() if e else "???"
        label = self._labels.get(entity_id)
        if label:
            return f"{type_name}#{entity_id} '{label}'"
        return f"{type_name}#{entity_id}"

    def _mini_map(self, center_tile: tuple[int, int],
                  radius: int = 7) -> str:
        """Render a small ASCII map centered on a tile with entities."""
        tm = self.state.tilemap
        cx, cy = center_tile

        # Collect entity positions
        tile_entities: dict[tuple[int, int], Entity] = {}
        for e in self.state.entities:
            tx, ty = _milli_to_tile(e.x, e.y)
            key = (tx, ty)
            existing = tile_entities.get(key)
            if existing is None or _DISPLAY_PRIORITY.get(
                e.entity_type, 0
            ) > _DISPLAY_PRIORITY.get(existing.entity_type, 0):
                tile_entities[key] = e

        lines: list[str] = []
        for dy in range(-radius, radius + 1):
            row: list[str] = []
            for dx in range(-radius, radius + 1):
                tx, ty = cx + dx, cy + dy
                key = (tx, ty)
                if key in tile_entities:
                    row.append(_entity_marker(tile_entities[key]))
                elif 0 <= tx < tm.width and 0 <= ty < tm.height:
                    row.append(
                        "X" if tm.get_tile(tx, ty) == TileType.ROCK else "."
                    )
                else:
                    row.append(" ")
            lines.append("".join(row))
        return "\n".join(lines)

    def _format_assertion(
        self,
        assertion: str,
        entity_id: int | None = None,
        details: list[str] | None = None,
    ) -> str:
        """Build a rich assertion failure message with full context."""
        parts: list[str] = [f"\nASSERTION FAILED: {assertion}"]

        e: Entity | None = None
        if entity_id is not None:
            e = self.state.get_entity(entity_id)
            parts.append(f"  Entity: {self._entity_label(entity_id)}")
            if e is not None:
                ex, ey = _milli_to_tile(e.x, e.y)
                parts.append(f"  Tile:     ({ex}, {ey})")
                parts.append(f"  Milli:    ({e.x}, {e.y})")
                parts.append(f"  State:    {e.state.name}")
                parts.append(f"  HP:       {e.hp}/{e.max_hp}")
                parts.append(f"  Carrying: {e.carrying}")
                if e.target_entity_id >= 0:
                    parts.append(f"  Target:   entity #{e.target_entity_id}")
            else:
                parts.append("  (entity not found — dead or removed)")

        if details:
            parts.append("")
            for d in details:
                parts.append(f"  {d}")

        # Mini-map centered on the entity
        if e is not None:
            parts.append("")
            parts.append("  Mini-map (15x15 centered on entity):")
            mini = self._mini_map(_milli_to_tile(e.x, e.y))
            for line in mini.splitlines():
                parts.append(f"    {line}")

        # Footer: tick and jelly
        parts.append("")
        jelly_parts = [
            f"p{pid}={j}"
            for pid, j in sorted(self.state.player_jelly.items())
        ]
        parts.append(f"  Tick: {self.state.tick}")
        parts.append(f"  Jelly: {', '.join(jelly_parts)}")

        return "\n".join(parts)
