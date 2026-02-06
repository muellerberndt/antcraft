"""Game state and entity definitions.

GameState is the single source of truth for the simulation. It contains
everything needed to fully describe the game at any point in time. Both
peers maintain an identical GameState — if they ever diverge, it's a desync.

DETERMINISM RULES:
- All values are integers (no floats).
- Entity lists are always ordered by entity_id.
- The PRNG is part of the state and must be advanced identically by both peers.
- Never use Python's random module in simulation code — use GameState.next_random().
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import IntEnum

from src.config import ANT_HP, ANT_SPEED


class EntityType(IntEnum):
    ANT = 0
    QUEEN = 1
    HIVE = 2
    HIVE_SITE = 3  # neutral, unclaimed expansion point
    CORPSE = 4
    APHID = 5      # wildlife tier 1
    BEETLE = 6     # wildlife tier 2
    MANTIS = 7     # wildlife tier 3


class EntityState(IntEnum):
    IDLE = 0
    MOVING = 1
    ATTACKING = 2
    HARVESTING = 3  # carrying jelly from a corpse
    FOUNDING = 4    # queen building a hive


@dataclass(slots=True)
class Entity:
    """A game entity (ant, queen, hive, wildlife, corpse, etc.).

    All positions are in milli-tiles (1 tile = 1000 milli-tiles).
    """
    entity_id: int
    entity_type: EntityType
    player_id: int          # -1 for neutral (wildlife, hive sites, corpses)
    x: int
    y: int
    target_x: int
    target_y: int
    speed: int = ANT_SPEED
    hp: int = ANT_HP
    max_hp: int = ANT_HP
    damage: int = 0         # DPS (converted to per-tick in simulation)
    state: EntityState = EntityState.IDLE
    path: list[tuple[int, int]] = field(default_factory=list)
    carrying: int = 0       # jelly being carried
    jelly_value: int = 0    # jelly dropped on death (corpse value)

    @property
    def is_moving(self) -> bool:
        return self.x != self.target_x or self.y != self.target_y


class GameState:
    """Complete simulation state for a game.

    Attributes:
        tick: Current simulation tick (starts at 0).
        entities: All game entities, ordered by entity_id.
        rng_state: Deterministic PRNG state (LCG).
        next_entity_id: Counter for assigning entity IDs.
        game_over: Whether the game has ended.
        winner: Player ID of the winner, or -1.
    """

    def __init__(self, seed: int = 0) -> None:
        self.tick: int = 0
        self.entities: list[Entity] = []
        self.rng_state: int = seed & 0xFFFFFFFF
        self.next_entity_id: int = 0
        self.game_over: bool = False
        self.winner: int = -1

    def create_entity(
        self,
        player_id: int,
        x: int,
        y: int,
        entity_type: EntityType = EntityType.ANT,
        **kwargs,
    ) -> Entity:
        """Create a new entity with a unique ID."""
        entity = Entity(
            entity_id=self.next_entity_id,
            entity_type=entity_type,
            player_id=player_id,
            x=x,
            y=y,
            target_x=x,
            target_y=y,
            **kwargs,
        )
        self.next_entity_id += 1
        self.entities.append(entity)
        return entity

    def get_entity(self, entity_id: int) -> Entity | None:
        """Look up an entity by ID. Returns None if not found."""
        for entity in self.entities:
            if entity.entity_id == entity_id:
                return entity
        return None

    def next_random(self, bound: int) -> int:
        """Deterministic PRNG (LCG). Returns a value in [0, bound).

        Both peers must call this the same number of times in the same order.
        """
        # LCG parameters (Numerical Recipes)
        self.rng_state = (self.rng_state * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.rng_state % bound

    def compute_hash(self) -> bytes:
        """Compute a deterministic hash of the full game state.

        Used for desync detection: both peers compute this and compare.
        """
        h = hashlib.sha256()
        h.update(self.tick.to_bytes(4, "big"))
        h.update(self.rng_state.to_bytes(4, "big"))
        h.update(len(self.entities).to_bytes(4, "big"))
        for e in self.entities:
            h.update(e.entity_id.to_bytes(4, "big"))
            h.update(e.entity_type.to_bytes(1, "big"))
            h.update(e.player_id.to_bytes(4, "big"))
            h.update(e.x.to_bytes(4, "big", signed=True))
            h.update(e.y.to_bytes(4, "big", signed=True))
            h.update(e.target_x.to_bytes(4, "big", signed=True))
            h.update(e.target_y.to_bytes(4, "big", signed=True))
            h.update(e.speed.to_bytes(4, "big"))
            h.update(e.hp.to_bytes(4, "big"))
            h.update(e.max_hp.to_bytes(4, "big"))
            h.update(e.damage.to_bytes(4, "big"))
            h.update(e.state.to_bytes(1, "big"))
            h.update(e.carrying.to_bytes(4, "big"))
            h.update(e.jelly_value.to_bytes(4, "big"))
        return h.digest()
