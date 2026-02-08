"""Input handler — converts PyGame events to Commands.

Left click/drag: select units (delegates to SelectionManager).
Right click: issue MOVE command for selected units.
"""

from __future__ import annotations

import pygame

from src.config import INPUT_DELAY_TICKS, MILLI_TILES_PER_TILE, SELECTION_THRESHOLD
from src.input.selection import SelectionManager
from src.simulation.commands import Command, CommandType
from src.simulation.state import Entity, EntityType, GameState


class InputHandler:
    """Converts PyGame mouse/keyboard events into simulation Commands."""

    def __init__(self, player_id: int, tile_size: int) -> None:
        self._player_id = player_id
        self._tile_size = tile_size
        self.selection = SelectionManager()
        # Drag state (screen coords)
        self._drag_start: tuple[int, int] | None = None
        self._drag_current: tuple[int, int] | None = None
        self._dragging = False
        # Command mode: None = default (move), "attack" = A-click, "move" = M-click
        self._command_mode: str | None = None

    @property
    def drag_rect(self) -> tuple[int, int, int, int] | None:
        """Return the current drag rectangle in screen coords, or None."""
        if self._dragging and self._drag_start and self._drag_current:
            return (*self._drag_start, *self._drag_current)
        return None

    _CURSOR_MAP = {
        "attack": pygame.SYSTEM_CURSOR_CROSSHAIR,
        "harvest": pygame.SYSTEM_CURSOR_HAND,
        "found": pygame.SYSTEM_CURSOR_HAND,
        "move": pygame.SYSTEM_CURSOR_ARROW,
    }

    def _set_command_mode(self, mode: str | None) -> None:
        self._command_mode = mode
        cursor = self._CURSOR_MAP.get(mode, pygame.SYSTEM_CURSOR_ARROW)
        pygame.mouse.set_cursor(cursor)

    def _screen_to_world(self, sx: int, sy: int, camera_x: int, camera_y: int) -> tuple[int, int]:
        """Convert screen pixel coords to milli-tile world coords."""
        wx = (sx + camera_x) * MILLI_TILES_PER_TILE // self._tile_size
        wy = (sy + camera_y) * MILLI_TILES_PER_TILE // self._tile_size
        return wx, wy

    def process_events(
        self,
        events: list[pygame.event.Event],
        state: GameState,
        current_tick: int,
        camera_x: int = 0,
        camera_y: int = 0,
    ) -> list[Command]:
        """Process PyGame events and return any Commands generated."""
        commands: list[Command] = []
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._drag_start = event.pos
                self._drag_current = event.pos
                self._dragging = False

            elif event.type == pygame.MOUSEMOTION and self._drag_start is not None:
                self._drag_current = event.pos
                dx = event.pos[0] - self._drag_start[0]
                dy = event.pos[1] - self._drag_start[1]
                if dx * dx + dy * dy > SELECTION_THRESHOLD * SELECTION_THRESHOLD:
                    self._dragging = True

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self._drag_start is not None:
                    if self._dragging:
                        self._box_select(
                            self._drag_start, event.pos, state,
                            camera_x, camera_y,
                        )
                    else:
                        self._click_select(
                            event.pos, state, camera_x, camera_y,
                        )
                self._drag_start = None
                self._drag_current = None
                self._dragging = False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                cmds = self._handle_right_click(
                    event.pos, state, current_tick, camera_x, camera_y,
                )
                commands.extend(cmds)

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_a:
                self._set_command_mode("attack")

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                self._set_command_mode("move")

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                self._set_command_mode("harvest")

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                self._set_command_mode("found")

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_s:
                cmd = self._handle_stop(state, current_tick)
                if cmd is not None:
                    commands.append(cmd)

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_n:
                cmd = self._handle_spawn_ant(state, current_tick, camera_x, camera_y)
                if cmd is not None:
                    commands.append(cmd)

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                cmd = self._handle_merge_queen(state, current_tick)
                if cmd is not None:
                    commands.append(cmd)

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_h:
                cmd = self._handle_found_hive(state, current_tick)
                if cmd is not None:
                    commands.append(cmd)

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_t:
                cmds = self._handle_morph_spitter(state, current_tick)
                commands.extend(cmds)

        return commands

    def _click_select(
        self,
        screen_pos: tuple[int, int],
        state: GameState,
        camera_x: int,
        camera_y: int,
    ) -> None:
        """Click-select at screen position."""
        wx, wy = self._screen_to_world(screen_pos[0], screen_pos[1], camera_x, camera_y)
        # Convert pixel threshold to milli-tile threshold
        threshold_mt = SELECTION_THRESHOLD * MILLI_TILES_PER_TILE // self._tile_size
        self.selection.select_at(wx, wy, state.entities, self._player_id, threshold_mt)

    def _box_select(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        state: GameState,
        camera_x: int,
        camera_y: int,
    ) -> None:
        """Box-select from drag start to end."""
        wx1, wy1 = self._screen_to_world(start[0], start[1], camera_x, camera_y)
        wx2, wy2 = self._screen_to_world(end[0], end[1], camera_x, camera_y)
        self.selection.select_in_rect(wx1, wy1, wx2, wy2, state.entities, self._player_id)

    def _handle_right_click(
        self,
        screen_pos: tuple[int, int],
        state: GameState,
        current_tick: int,
        camera_x: int,
        camera_y: int,
    ) -> list[Command]:
        """Right click: issue command based on current mode or auto-detect target."""
        if not self.selection.selected_ids:
            self._set_command_mode(None)
            return []

        wx, wy = self._screen_to_world(screen_pos[0], screen_pos[1], camera_x, camera_y)
        mode = self._command_mode
        self._set_command_mode(None)

        # Explicit mode overrides auto-detect
        if mode == "attack":
            return self._right_click_attack(wx, wy, state, current_tick)
        if mode == "harvest":
            # Harvest-move: move to position, auto-harvest corpses in range
            ant_ids = self._filter_selected(state, lambda e: e.entity_type == EntityType.ANT)
            if not ant_ids:
                return [self._make_move_cmd(wx, wy, current_tick)]
            return [Command(
                command_type=CommandType.HARVEST,
                player_id=self._player_id,
                tick=current_tick + INPUT_DELAY_TICKS,
                entity_ids=tuple(sorted(ant_ids)),
                target_x=wx,
                target_y=wy,
                target_entity_id=-1,
            )]
        if mode == "found":
            return self._right_click_found(wx, wy, state, current_tick)
        if mode == "move":
            return [self._make_move_cmd(wx, wy, current_tick)]

        # Auto-detect: find entity under cursor
        target = self._find_entity_at(wx, wy, state)
        if target is not None:
            if target.entity_type == EntityType.CORPSE:
                return self._right_click_harvest(wx, wy, state, current_tick, target)
            if target.entity_type == EntityType.HIVE_SITE:
                return self._right_click_found(wx, wy, state, current_tick, target)
            if target.player_id != self._player_id:
                return self._right_click_attack(wx, wy, state, current_tick, target)

        return [self._make_move_cmd(wx, wy, current_tick)]

    def _make_move_cmd(self, wx: int, wy: int, current_tick: int) -> Command:
        return Command(
            command_type=CommandType.MOVE,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=tuple(sorted(self.selection.selected_ids)),
            target_x=wx,
            target_y=wy,
        )

    def _find_entity_at(self, wx: int, wy: int, state: GameState) -> Entity | None:
        """Find the nearest non-friendly entity under cursor within click radius."""
        threshold_mt = SELECTION_THRESHOLD * MILLI_TILES_PER_TILE // self._tile_size
        threshold_sq = threshold_mt * threshold_mt
        best: Entity | None = None
        best_dist_sq = threshold_sq + 1
        for e in state.entities:
            if e.player_id == self._player_id:
                continue
            dx = e.x - wx
            dy = e.y - wy
            dist_sq = dx * dx + dy * dy
            if dist_sq < best_dist_sq:
                best = e
                best_dist_sq = dist_sq
        return best

    def _right_click_attack(
        self, wx: int, wy: int, state: GameState, current_tick: int,
        target: Entity | None = None,
    ) -> list[Command]:
        """Attack: find enemy entity near cursor and issue ATTACK."""
        if target is None:
            target = self._find_entity_at(wx, wy, state)
            # Filter out non-attackable types
            if target is not None and target.entity_type in (EntityType.CORPSE, EntityType.HIVE_SITE):
                target = None
        if target is None:
            return [self._make_move_cmd(wx, wy, current_tick)]

        # Filter to entities that can deal damage
        attack_ids = self._filter_selected(state, lambda e: e.damage > 0)
        if not attack_ids:
            return [self._make_move_cmd(wx, wy, current_tick)]

        return [Command(
            command_type=CommandType.ATTACK,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=tuple(sorted(attack_ids)),
            target_entity_id=target.entity_id,
        )]

    def _right_click_harvest(
        self, wx: int, wy: int, state: GameState, current_tick: int,
        target: Entity | None = None,
    ) -> list[Command]:
        """Harvest: find corpse near cursor and issue HARVEST."""
        if target is None:
            threshold_mt = SELECTION_THRESHOLD * MILLI_TILES_PER_TILE // self._tile_size
            threshold_sq = threshold_mt * threshold_mt
            best_dist_sq = threshold_sq + 1
            for e in state.entities:
                if e.entity_type != EntityType.CORPSE:
                    continue
                dx = e.x - wx
                dy = e.y - wy
                dist_sq = dx * dx + dy * dy
                if dist_sq < best_dist_sq:
                    target = e
                    best_dist_sq = dist_sq
        if target is None:
            return [self._make_move_cmd(wx, wy, current_tick)]

        # Only ants can harvest
        ant_ids = self._filter_selected(state, lambda e: e.entity_type == EntityType.ANT)
        if not ant_ids:
            return [self._make_move_cmd(wx, wy, current_tick)]

        return [Command(
            command_type=CommandType.HARVEST,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=tuple(sorted(ant_ids)),
            target_entity_id=target.entity_id,
        )]

    def _right_click_found(
        self, wx: int, wy: int, state: GameState, current_tick: int,
        target: Entity | None = None,
    ) -> list[Command]:
        """Found hive: find hive site near cursor and issue FOUND_HIVE per queen."""
        if target is None:
            threshold_mt = SELECTION_THRESHOLD * MILLI_TILES_PER_TILE // self._tile_size
            threshold_sq = threshold_mt * threshold_mt
            best_dist_sq = threshold_sq + 1
            for e in state.entities:
                if e.entity_type != EntityType.HIVE_SITE:
                    continue
                dx = e.x - wx
                dy = e.y - wy
                dist_sq = dx * dx + dy * dy
                if dist_sq < best_dist_sq:
                    target = e
                    best_dist_sq = dist_sq
        if target is None:
            return [self._make_move_cmd(wx, wy, current_tick)]

        # Only queens can found hives — one command per queen
        queen_ids = self._filter_selected(state, lambda e: e.entity_type == EntityType.QUEEN)
        if not queen_ids:
            return [self._make_move_cmd(wx, wy, current_tick)]

        return [Command(
            command_type=CommandType.FOUND_HIVE,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=(qid,),
            target_entity_id=target.entity_id,
        ) for qid in sorted(queen_ids)]

    def _filter_selected(
        self, state: GameState, predicate: object,
    ) -> set[int]:
        """Return selected entity IDs that match the predicate."""
        result: set[int] = set()
        for eid in self.selection.selected_ids:
            e = state.get_entity(eid)
            if e is not None and e.player_id == self._player_id and predicate(e):
                result.add(eid)
        return result

    def _handle_stop(self, state: GameState, current_tick: int) -> Command | None:
        """S key: STOP command for selected units."""
        if not self.selection.selected_ids:
            return None

        return Command(
            command_type=CommandType.STOP,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=tuple(sorted(self.selection.selected_ids)),
        )

    def _handle_spawn_ant(
        self, state: GameState, current_tick: int, camera_x: int, camera_y: int,
    ) -> Command | None:
        """N key: SPAWN_ANT from selected hive or nearest own hive."""
        # If a hive is selected, use it
        for eid in self.selection.selected_ids:
            e = state.get_entity(eid)
            if e is not None and e.entity_type == EntityType.HIVE and e.player_id == self._player_id:
                return Command(
                    command_type=CommandType.SPAWN_ANT,
                    player_id=self._player_id,
                    tick=current_tick + INPUT_DELAY_TICKS,
                    target_entity_id=e.entity_id,
                )

        # Otherwise find nearest own hive to camera center
        sw = pygame.display.get_surface().get_width()
        sh = pygame.display.get_surface().get_height()
        cx = (camera_x + sw // 2) * MILLI_TILES_PER_TILE // self._tile_size
        cy = (camera_y + sh // 2) * MILLI_TILES_PER_TILE // self._tile_size
        hive = self._find_nearest(state, EntityType.HIVE, self._player_id, cx, cy)
        if hive is None:
            return None

        return Command(
            command_type=CommandType.SPAWN_ANT,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            target_entity_id=hive.entity_id,
        )

    def _handle_merge_queen(self, state: GameState, current_tick: int) -> Command | None:
        """Q key: MERGE_QUEEN — merge selected ants at nearest own hive."""
        ant_ids = []
        sum_x, sum_y = 0, 0
        for eid in self.selection.selected_ids:
            e = state.get_entity(eid)
            if e is not None and e.entity_type == EntityType.ANT and e.player_id == self._player_id:
                ant_ids.append(eid)
                sum_x += e.x
                sum_y += e.y

        if not ant_ids:
            return None

        centroid_x = sum_x // len(ant_ids)
        centroid_y = sum_y // len(ant_ids)
        hive = self._find_nearest(state, EntityType.HIVE, self._player_id, centroid_x, centroid_y)
        if hive is None:
            return None

        return Command(
            command_type=CommandType.MERGE_QUEEN,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=tuple(sorted(ant_ids)),
            target_entity_id=hive.entity_id,
        )

    def _handle_found_hive(self, state: GameState, current_tick: int) -> Command | None:
        """H key: FOUND_HIVE — send selected queen to nearest hive site."""
        queen = None
        for eid in self.selection.selected_ids:
            e = state.get_entity(eid)
            if e is not None and e.entity_type == EntityType.QUEEN and e.player_id == self._player_id:
                queen = e
                break

        if queen is None:
            return None

        site = self._find_nearest(state, EntityType.HIVE_SITE, -1, queen.x, queen.y)
        if site is None:
            return None

        return Command(
            command_type=CommandType.FOUND_HIVE,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=(queen.entity_id,),
            target_entity_id=site.entity_id,
        )

    def _handle_morph_spitter(self, state: GameState, current_tick: int) -> list[Command]:
        """T key: MORPH_SPITTER — morph selected ants into spitters at nearest hive."""
        ant_ids = []
        for eid in self.selection.selected_ids:
            e = state.get_entity(eid)
            if e is not None and e.entity_type == EntityType.ANT and e.player_id == self._player_id:
                ant_ids.append(eid)

        if not ant_ids:
            return []

        # Find nearest own hive to first ant
        first_ant = state.get_entity(ant_ids[0])
        if first_ant is None:
            return []
        hive = self._find_nearest(state, EntityType.HIVE, self._player_id, first_ant.x, first_ant.y)
        if hive is None:
            return []

        # Issue one MORPH_SPITTER per selected ant
        return [Command(
            command_type=CommandType.MORPH_SPITTER,
            player_id=self._player_id,
            tick=current_tick + INPUT_DELAY_TICKS,
            entity_ids=(aid,),
            target_entity_id=hive.entity_id,
        ) for aid in sorted(ant_ids)]

    @staticmethod
    def _find_nearest(
        state: GameState, entity_type: EntityType, player_id: int, ref_x: int, ref_y: int,
    ) -> Entity | None:
        """Find the nearest entity of given type and owner to a reference point."""
        best: Entity | None = None
        best_dist_sq = -1
        for e in state.entities:
            if e.entity_type != entity_type or e.player_id != player_id:
                continue
            dx = e.x - ref_x
            dy = e.y - ref_y
            dist_sq = dx * dx + dy * dy
            if best is None or dist_sq < best_dist_sq:
                best = e
                best_dist_sq = dist_sq
        return best
