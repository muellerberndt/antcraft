"""A* pathfinding on the tile grid.

Deterministic, integer-only. 8-directional movement with cardinal cost 1000
and diagonal cost 1414 (approximation of 1000 * sqrt(2)).

Tie-breaking: prefer lower f-cost, then lower y, then lower x — ensures
both peers always compute the same path for the same inputs.
"""

from __future__ import annotations

import heapq

from src.simulation.tilemap import TileMap

# Movement costs (integer, scaled by 1000 to avoid floats)
CARDINAL_COST = 1000
DIAGONAL_COST = 1414  # ~1000 * sqrt(2)

# 8-directional neighbors: (dx, dy, cost)
_NEIGHBORS = [
    (1, 0, CARDINAL_COST),
    (-1, 0, CARDINAL_COST),
    (0, 1, CARDINAL_COST),
    (0, -1, CARDINAL_COST),
    (1, 1, DIAGONAL_COST),
    (1, -1, DIAGONAL_COST),
    (-1, 1, DIAGONAL_COST),
    (-1, -1, DIAGONAL_COST),
]


def _heuristic(x: int, y: int, gx: int, gy: int) -> int:
    """Chebyshev-style heuristic scaled to match movement costs.

    Uses octile distance: max(dx, dy) * CARDINAL + (min - 0) * (DIAGONAL - CARDINAL).
    This is admissible and consistent for 8-directional movement.
    """
    dx = abs(x - gx)
    dy = abs(y - gy)
    if dx > dy:
        return dy * DIAGONAL_COST + (dx - dy) * CARDINAL_COST
    return dx * DIAGONAL_COST + (dy - dx) * CARDINAL_COST


def find_path(
    tilemap: TileMap,
    start_x: int,
    start_y: int,
    goal_x: int,
    goal_y: int,
) -> list[tuple[int, int]]:
    """Find a path from (start_x, start_y) to (goal_x, goal_y) in tile coords.

    Returns a list of (tile_x, tile_y) waypoints from start to goal (inclusive
    of goal, exclusive of start). Returns an empty list if no path exists or
    if start == goal.

    Args:
        tilemap: The tile map to pathfind on.
        start_x: Start tile X coordinate.
        start_y: Start tile Y coordinate.
        goal_x: Goal tile X coordinate.
        goal_y: Goal tile Y coordinate.
    """
    if start_x == goal_x and start_y == goal_y:
        return []

    if not tilemap.is_walkable(start_x, start_y):
        return []
    if not tilemap.is_walkable(goal_x, goal_y):
        return []

    # open set: (f_cost, y, x, g_cost) — y before x for deterministic tie-breaking
    start_h = _heuristic(start_x, start_y, goal_x, goal_y)
    open_set: list[tuple[int, int, int, int]] = [(start_h, start_y, start_x, 0)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_costs: dict[tuple[int, int], int] = {(start_x, start_y): 0}

    while open_set:
        _f, _y, _x, g = heapq.heappop(open_set)

        if _x == goal_x and _y == goal_y:
            # Reconstruct path (start excluded, goal included)
            path: list[tuple[int, int]] = []
            cx, cy = goal_x, goal_y
            while (cx, cy) != (start_x, start_y):
                path.append((cx, cy))
                cx, cy = came_from[(cx, cy)]
            path.reverse()
            return path

        # Skip if we already found a better route to this node
        if g > g_costs.get((_x, _y), g + 1):
            continue

        for dx, dy, cost in _NEIGHBORS:
            nx, ny = _x + dx, _y + dy

            if not tilemap.is_walkable(nx, ny):
                continue

            # For diagonal moves, check that both cardinal neighbors are walkable
            # to prevent cutting through diagonal rock corners
            if dx != 0 and dy != 0:
                if not tilemap.is_walkable(_x + dx, _y) or not tilemap.is_walkable(_x, _y + dy):
                    continue

            new_g = g + cost
            if new_g < g_costs.get((nx, ny), new_g + 1):
                g_costs[(nx, ny)] = new_g
                h = _heuristic(nx, ny, goal_x, goal_y)
                f = new_g + h
                came_from[(nx, ny)] = (_x, _y)
                heapq.heappush(open_set, (f, ny, nx, new_g))

    return []  # no path found
