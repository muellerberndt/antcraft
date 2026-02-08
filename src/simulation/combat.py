"""Combat system — auto-attack, death/corpse creation, corpse decay.

All combat logic is deterministic and uses integer math only.
Damage is specified as DPS (damage per second) and distributed
across ticks using Bresenham-style integer distribution.
"""

from __future__ import annotations

from src.config import (
    ANT_CORPSE_JELLY,
    APHID_JELLY,
    ATTACK_RANGE,
    BEETLE_JELLY,
    CORPSE_DECAY_TICKS,
    MANTIS_JELLY,
    MILLI_TILES_PER_TILE,
    TICK_RATE,
)
from src.simulation.state import EntityState, EntityType, GameState

# Attack range in milli-tiles (squared for distance comparison)
_ATTACK_RANGE_MT = ATTACK_RANGE * MILLI_TILES_PER_TILE
_ATTACK_RANGE_SQ = _ATTACK_RANGE_MT * _ATTACK_RANGE_MT

# Entity types that can be attacked
_ATTACKABLE_TYPES = frozenset({
    EntityType.ANT, EntityType.QUEEN, EntityType.HIVE,
    EntityType.APHID, EntityType.BEETLE, EntityType.MANTIS,
})

# Jelly value dropped as corpse on death (types not listed leave no corpse)
_CORPSE_JELLY = {
    EntityType.ANT: ANT_CORPSE_JELLY,
    EntityType.APHID: APHID_JELLY,
    EntityType.BEETLE: BEETLE_JELLY,
    EntityType.MANTIS: MANTIS_JELLY,
}


def process_combat(state: GameState) -> None:
    """Run all combat logic for one tick.

    Order: decay corpses -> auto-attack -> process deaths.
    Decay runs first so newly created corpses aren't decayed on their first tick.
    """
    _decay_corpses(state)
    _auto_attack(state)
    _process_deaths(state)


def _damage_this_tick(dps: int, tick: int) -> int:
    """Distribute DPS across ticks using Bresenham-style integer math.

    Guarantees exactly ``dps`` total damage over every TICK_RATE ticks.
    For example, 5 DPS at 10 ticks/sec deals 1 damage on 5 of the 10 ticks.
    """
    t = tick % TICK_RATE
    return (dps * (t + 1)) // TICK_RATE - (dps * t) // TICK_RATE


def _is_enemy(attacker, target) -> bool:
    """Check if target is a valid attack target for attacker."""
    if target.entity_type not in _ATTACKABLE_TYPES:
        return False
    if target.player_id == attacker.player_id:
        return False
    # Wildlife doesn't attack other wildlife
    if attacker.player_id == -1 and target.player_id == -1:
        return False
    return True


def _auto_attack(state: GameState) -> None:
    """Each entity with damage > 0 attacks nearest enemy in range.

    Two-phase: compute all attacks from snapshot, then apply damage.
    This ensures combat is order-independent and deterministic.
    """
    attacks: list[tuple[int, int]] = []  # (target_entity_id, damage)

    for attacker in state.entities:
        if attacker.damage <= 0:
            continue

        dmg = _damage_this_tick(attacker.damage, state.tick)
        if dmg <= 0:
            # Rest tick — don't change state to avoid visual flickering
            continue

        # Find nearest enemy within attack range
        best_target = None
        best_dist_sq = _ATTACK_RANGE_SQ + 1

        for target in state.entities:
            if not _is_enemy(attacker, target):
                continue
            dx = attacker.x - target.x
            dy = attacker.y - target.y
            dist_sq = dx * dx + dy * dy
            if dist_sq > _ATTACK_RANGE_SQ:
                continue
            if dist_sq < best_dist_sq or (
                dist_sq == best_dist_sq
                and (best_target is None or target.entity_id < best_target.entity_id)
            ):
                best_dist_sq = dist_sq
                best_target = target

        if best_target is not None:
            attacks.append((best_target.entity_id, dmg))
            attacker.state = EntityState.ATTACKING
        elif attacker.state == EntityState.ATTACKING:
            attacker.state = EntityState.IDLE

    # Apply all damage (snapshot-based, order-independent)
    for target_id, dmg in attacks:
        target = state.get_entity(target_id)
        if target is not None:
            target.hp -= dmg


def _process_deaths(state: GameState) -> None:
    """Remove dead entities and create corpses for those that drop jelly."""
    dead = []
    alive = []
    for entity in state.entities:
        if entity.hp <= 0 and entity.entity_type not in (
            EntityType.CORPSE, EntityType.HIVE_SITE,
        ):
            dead.append(entity)
        else:
            alive.append(entity)

    state.entities = alive

    for entity in dead:
        jelly = _CORPSE_JELLY.get(entity.entity_type, 0)
        if jelly > 0:
            state.create_entity(
                player_id=-1,
                x=entity.x,
                y=entity.y,
                entity_type=EntityType.CORPSE,
                hp=CORPSE_DECAY_TICKS,
                max_hp=CORPSE_DECAY_TICKS,
                jelly_value=jelly,
                speed=0,
                damage=0,
            )


def _decay_corpses(state: GameState) -> None:
    """Decrement corpse hp each tick and remove expired corpses."""
    for entity in state.entities:
        if entity.entity_type == EntityType.CORPSE:
            entity.hp -= 1

    state.entities = [
        e for e in state.entities
        if not (e.entity_type == EntityType.CORPSE and e.hp <= 0)
    ]
