"""Hive mechanics — passive income, ant spawning, queen merging, founding, win condition.

All logic is deterministic and uses integer math only.
Income uses Bresenham-style distribution (same as combat damage).
"""

from __future__ import annotations

from src.config import (
    ANT_CORPSE_JELLY,
    ANT_DAMAGE,
    ANT_HP,
    ANT_SIGHT,
    ANT_SPAWN_COOLDOWN,
    ANT_SPAWN_COST,
    ANT_SPEED,
    ATTACK_RANGE,
    FOUND_HIVE_RANGE,
    HIVE_HP,
    HIVE_PASSIVE_INCOME,
    HIVE_SIGHT,
    MERGE_RANGE,
    MILLI_TILES_PER_TILE,
    QUEEN_HP,
    QUEEN_MERGE_COST,
    QUEEN_SIGHT,
    QUEEN_SPEED,
    SPITTER_ATTACK_RANGE,
    SPITTER_CORPSE_JELLY,
    SPITTER_DAMAGE,
    SPITTER_HP,
    SPITTER_MORPH_COST,
    SPITTER_SIGHT,
    SPITTER_SPEED,
    TICK_RATE,
)
from src.simulation.commands import Command
from src.simulation.pathfinding import find_path
from src.simulation.state import EntityState, EntityType, GameState

# Merge range in milli-tiles (squared for distance comparison)
_MERGE_RANGE_MT = MERGE_RANGE * MILLI_TILES_PER_TILE
_MERGE_RANGE_SQ = _MERGE_RANGE_MT * _MERGE_RANGE_MT

# Founding arrival range in milli-tiles (squared)
_FOUND_RANGE_MT = FOUND_HIVE_RANGE * MILLI_TILES_PER_TILE
_FOUND_RANGE_SQ = _FOUND_RANGE_MT * _FOUND_RANGE_MT


def process_hive_mechanics(state: GameState) -> None:
    """Run all hive mechanics for one tick.

    Called from advance_tick() after combat.
    Order: income -> spawning -> founding -> win condition.
    """
    _apply_passive_income(state)
    _tick_spawn_cooldowns(state)
    _check_founding(state)
    _check_win_condition(state)


# -- Passive income ----------------------------------------------------------

def _income_this_tick(income_per_sec: int, tick: int) -> int:
    """Distribute per-second income across ticks using Bresenham integer math."""
    t = tick % TICK_RATE
    return (income_per_sec * (t + 1)) // TICK_RATE - (income_per_sec * t) // TICK_RATE


def _apply_passive_income(state: GameState) -> None:
    """Each hive generates HIVE_PASSIVE_INCOME jelly per second for its owner."""
    income = _income_this_tick(HIVE_PASSIVE_INCOME, state.tick)
    if income <= 0:
        return
    for entity in state.entities:
        if entity.entity_type == EntityType.HIVE and entity.player_id >= 0:
            state.player_jelly[entity.player_id] = (
                state.player_jelly.get(entity.player_id, 0) + income
            )


# -- Ant spawning -------------------------------------------------------------

_SPAWN_DIRS = [
    (0, -MILLI_TILES_PER_TILE),                        # N
    (MILLI_TILES_PER_TILE, -MILLI_TILES_PER_TILE),     # NE
    (MILLI_TILES_PER_TILE, 0),                          # E
    (MILLI_TILES_PER_TILE, MILLI_TILES_PER_TILE),       # SE
    (0, MILLI_TILES_PER_TILE),                          # S
    (-MILLI_TILES_PER_TILE, MILLI_TILES_PER_TILE),      # SW
    (-MILLI_TILES_PER_TILE, 0),                          # W
    (-MILLI_TILES_PER_TILE, -MILLI_TILES_PER_TILE),     # NW
]


def _tick_spawn_cooldowns(state: GameState) -> None:
    """Decrement hive cooldowns and spawn ants when cooldown reaches 0."""
    spawns: list[tuple[int, int, int]] = []  # (player_id, x, y)
    for entity in state.entities:
        if entity.entity_type == EntityType.HIVE and entity.cooldown > 0:
            entity.cooldown -= 1
            if entity.cooldown == 0:
                spawns.append((entity.player_id, entity.x, entity.y))

    for player_id, hx, hy in spawns:
        sx, sy = _pick_spawn_pos(state, hx, hy)
        state.create_entity(
            player_id=player_id,
            x=sx,
            y=sy,
            entity_type=EntityType.ANT,
            speed=ANT_SPEED,
            hp=ANT_HP,
            max_hp=ANT_HP,
            damage=ANT_DAMAGE,
            jelly_value=ANT_CORPSE_JELLY,
            sight=ANT_SIGHT,
        )


def _pick_spawn_pos(state: GameState, hx: int, hy: int) -> tuple[int, int]:
    """Pick a walkable position adjacent to the hive for spawning."""
    start = state.next_random(8)
    for i in range(8):
        dx, dy = _SPAWN_DIRS[(start + i) % 8]
        nx, ny = hx + dx, hy + dy
        tile_x = nx // MILLI_TILES_PER_TILE
        tile_y = ny // MILLI_TILES_PER_TILE
        if state.tilemap.is_walkable(tile_x, tile_y):
            return nx, ny
    return hx, hy


# -- Founding ------------------------------------------------------------------

def _check_founding(state: GameState) -> None:
    """Check if any FOUNDING queen has arrived at a hive site."""
    hive_sites = [
        e for e in state.entities if e.entity_type == EntityType.HIVE_SITE
    ]
    if not hive_sites:
        return

    queens_to_remove: list[int] = []
    sites_to_convert: list[tuple[int, int, int, int]] = []  # (site_id, player_id, x, y)

    for queen in state.entities:
        if queen.entity_type != EntityType.QUEEN:
            continue
        if queen.state != EntityState.FOUNDING:
            continue

        for site in hive_sites:
            dx = queen.x - site.x
            dy = queen.y - site.y
            if dx * dx + dy * dy <= _FOUND_RANGE_SQ:
                queens_to_remove.append(queen.entity_id)
                sites_to_convert.append(
                    (site.entity_id, queen.player_id, site.x, site.y)
                )
                break

    if not queens_to_remove:
        return

    remove_ids = set(queens_to_remove)
    remove_site_ids = {s[0] for s in sites_to_convert}
    state.entities = [
        e for e in state.entities
        if e.entity_id not in remove_ids and e.entity_id not in remove_site_ids
    ]

    for _site_id, player_id, sx, sy in sites_to_convert:
        state.create_entity(
            player_id=player_id,
            x=sx,
            y=sy,
            entity_type=EntityType.HIVE,
            speed=0,
            hp=HIVE_HP,
            max_hp=HIVE_HP,
            damage=0,
            sight=HIVE_SIGHT,
        )


# -- Win condition -------------------------------------------------------------

def _check_win_condition(state: GameState) -> None:
    """Eliminate players with 0 hives. Last player standing wins."""
    if state.game_over:
        return

    player_hives: dict[int, int] = {}
    for entity in state.entities:
        if entity.entity_type == EntityType.HIVE and entity.player_id >= 0:
            player_hives[entity.player_id] = (
                player_hives.get(entity.player_id, 0) + 1
            )

    eliminated = []
    alive = []
    for player_id in sorted(state.player_jelly):
        if player_hives.get(player_id, 0) == 0:
            eliminated.append(player_id)
        else:
            alive.append(player_id)

    if eliminated and len(alive) == 1:
        state.game_over = True
        state.winner = alive[0]
    elif eliminated and len(alive) == 0:
        state.game_over = True
        state.winner = -1


# -- Command handlers (called from tick.py _process_commands) ------------------

def handle_spawn_ant(state: GameState, cmd: Command) -> None:
    """SPAWN_ANT: validate hive, deduct jelly, set cooldown."""
    hive = state.get_entity(cmd.target_entity_id)
    if hive is None:
        return
    if hive.entity_type != EntityType.HIVE:
        return
    if hive.player_id != cmd.player_id:
        return
    if hive.cooldown > 0:
        return
    jelly = state.player_jelly.get(cmd.player_id, 0)
    if jelly < ANT_SPAWN_COST:
        return
    state.player_jelly[cmd.player_id] = jelly - ANT_SPAWN_COST
    hive.cooldown = ANT_SPAWN_COOLDOWN


def handle_merge_queen(state: GameState, cmd: Command) -> None:
    """MERGE_QUEEN: validate ants near hive, remove ants, create queen."""
    hive = state.get_entity(cmd.target_entity_id)
    if hive is None:
        return
    if hive.entity_type != EntityType.HIVE:
        return
    if hive.player_id != cmd.player_id:
        return

    valid_ants = []
    for eid in cmd.entity_ids:
        ant = state.get_entity(eid)
        if ant is None:
            continue
        if ant.entity_type != EntityType.ANT:
            continue
        if ant.player_id != cmd.player_id:
            continue
        dx = ant.x - hive.x
        dy = ant.y - hive.y
        if dx * dx + dy * dy > _MERGE_RANGE_SQ:
            continue
        valid_ants.append(ant)

    if len(valid_ants) < QUEEN_MERGE_COST:
        return

    ants_to_merge = valid_ants[:QUEEN_MERGE_COST]
    merged_ids = {a.entity_id for a in ants_to_merge}
    state.entities = [e for e in state.entities if e.entity_id not in merged_ids]

    state.create_entity(
        player_id=cmd.player_id,
        x=hive.x,
        y=hive.y,
        entity_type=EntityType.QUEEN,
        speed=QUEEN_SPEED,
        hp=QUEEN_HP,
        max_hp=QUEEN_HP,
        damage=0,
        sight=QUEEN_SIGHT,
    )


def handle_found_hive(state: GameState, cmd: Command) -> None:
    """FOUND_HIVE: pathfind queen to hive site, set state=FOUNDING."""
    if len(cmd.entity_ids) != 1:
        return
    queen = state.get_entity(cmd.entity_ids[0])
    if queen is None:
        return
    if queen.entity_type != EntityType.QUEEN:
        return
    if queen.player_id != cmd.player_id:
        return

    site = state.get_entity(cmd.target_entity_id)
    if site is None:
        return
    if site.entity_type != EntityType.HIVE_SITE:
        return

    # Compute path from queen to hive site
    start_tx = queen.x // MILLI_TILES_PER_TILE
    start_ty = queen.y // MILLI_TILES_PER_TILE
    target_tx = site.x // MILLI_TILES_PER_TILE
    target_ty = site.y // MILLI_TILES_PER_TILE

    tile_path = find_path(state.tilemap, start_tx, start_ty, target_tx, target_ty)
    if tile_path:
        milli_path = [
            (tx * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2,
             ty * MILLI_TILES_PER_TILE + MILLI_TILES_PER_TILE // 2)
            for tx, ty in tile_path
        ]
        queen.path = milli_path
        queen.target_x = milli_path[-1][0]
        queen.target_y = milli_path[-1][1]
    else:
        queen.target_x = site.x
        queen.target_y = site.y
        queen.path = []

    queen.state = EntityState.FOUNDING


def handle_morph_spitter(state: GameState, cmd: Command) -> None:
    """MORPH_SPITTER: validate ant near hive, deduct jelly, replace ant with spitter."""
    if len(cmd.entity_ids) != 1:
        return
    ant = state.get_entity(cmd.entity_ids[0])
    if ant is None:
        return
    if ant.entity_type != EntityType.ANT:
        return
    if ant.player_id != cmd.player_id:
        return

    hive = state.get_entity(cmd.target_entity_id)
    if hive is None:
        return
    if hive.entity_type != EntityType.HIVE:
        return
    if hive.player_id != cmd.player_id:
        return

    # Check ant is near hive
    dx = ant.x - hive.x
    dy = ant.y - hive.y
    if dx * dx + dy * dy > _MERGE_RANGE_SQ:
        return

    # Check jelly
    jelly = state.player_jelly.get(cmd.player_id, 0)
    if jelly < SPITTER_MORPH_COST:
        return

    # Deduct jelly
    state.player_jelly[cmd.player_id] = jelly - SPITTER_MORPH_COST

    # Remove the ant, create spitter at the ant's position
    sx, sy = ant.x, ant.y
    state.entities = [e for e in state.entities if e.entity_id != ant.entity_id]

    state.create_entity(
        player_id=cmd.player_id,
        x=sx,
        y=sy,
        entity_type=EntityType.SPITTER,
        speed=SPITTER_SPEED,
        hp=SPITTER_HP,
        max_hp=SPITTER_HP,
        damage=SPITTER_DAMAGE,
        jelly_value=SPITTER_CORPSE_JELLY,
        sight=SPITTER_SIGHT,
        attack_range=SPITTER_ATTACK_RANGE,
    )
