"""Selection manager — tracks which entities the player has selected.

Selection is LOCAL ONLY — not synced, not part of GameState.
Only own ANT and QUEEN entities can be selected.
"""

from __future__ import annotations

from src.simulation.state import Entity, EntityType

SELECTABLE_TYPES = {EntityType.ANT, EntityType.QUEEN, EntityType.HIVE}


class SelectionManager:
    """Tracks the set of currently selected entity IDs."""

    def __init__(self) -> None:
        self.selected_ids: set[int] = set()

    def select_at(
        self,
        world_x: int,
        world_y: int,
        entities: list[Entity],
        player_id: int,
        threshold: int,
    ) -> None:
        """Click-select the nearest own selectable unit within threshold.

        Args:
            world_x: Click position in milli-tiles.
            world_y: Click position in milli-tiles.
            entities: All game entities.
            player_id: The local player's ID.
            threshold: Maximum distance in milli-tiles.
        """
        threshold_sq = threshold * threshold
        best_id = -1
        best_dist_sq = threshold_sq + 1

        for e in entities:
            if e.player_id != player_id:
                continue
            if e.entity_type not in SELECTABLE_TYPES:
                continue
            dx = e.x - world_x
            dy = e.y - world_y
            dist_sq = dx * dx + dy * dy
            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_id = e.entity_id

        self.selected_ids.clear()
        if best_id >= 0:
            self.selected_ids.add(best_id)

    def select_in_rect(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        entities: list[Entity],
        player_id: int,
    ) -> None:
        """Box-select all own selectable units within a rectangle.

        Args:
            x1, y1: One corner of the rectangle (milli-tiles).
            x2, y2: Opposite corner (milli-tiles).
            entities: All game entities.
            player_id: The local player's ID.
        """
        min_x = min(x1, x2)
        max_x = max(x1, x2)
        min_y = min(y1, y2)
        max_y = max(y1, y2)

        self.selected_ids.clear()
        for e in entities:
            if e.player_id != player_id:
                continue
            if e.entity_type not in SELECTABLE_TYPES:
                continue
            if min_x <= e.x <= max_x and min_y <= e.y <= max_y:
                self.selected_ids.add(e.entity_id)

    def clear(self) -> None:
        """Deselect all."""
        self.selected_ids.clear()
