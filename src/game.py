"""Game state machine and lockstep game loop.

Manages the game lifecycle: MENU -> CONNECTING -> PLAYING -> DISCONNECTED.
Runs the fixed-tick lockstep simulation decoupled from the render frame rate.
"""

from __future__ import annotations

import logging
import time
from enum import Enum, auto

import pygame

from src.config import (
    ANT_CORPSE_JELLY,
    ANT_DAMAGE,
    ANT_HP,
    ANT_SIGHT,
    ANT_SPEED,
    APHID_HP,
    APHID_JELLY,
    BEETLE_DAMAGE,
    BEETLE_HP,
    BEETLE_JELLY,
    CAMERA_SCROLL_SPEED,
    FPS,
    HASH_CHECK_INTERVAL,
    HIVE_HP,
    HIVE_SIGHT,
    INPUT_DELAY_TICKS,
    MANTIS_DAMAGE,
    MANTIS_HP,
    MANTIS_JELLY,
    MILLI_TILES_PER_TILE,
    NET_TIMEOUT_DISCONNECT_MS,
    NET_TIMEOUT_WARNING_MS,
    QUEEN_SIGHT,
    STARTING_ANTS,
    TILE_RENDER_SIZE,
    TICK_DURATION_MS,
)
from src.input.handler import InputHandler
from src.networking.peer import NetworkPeer
from src.rendering.renderer import Renderer
from src.simulation.commands import Command, CommandType
from src.simulation.state import EntityType, GameState
from src.simulation.tick import advance_tick

logger = logging.getLogger(__name__)


class GamePhase(Enum):
    CONNECTING = auto()
    PLAYING = auto()
    DISCONNECTED = auto()


class Game:
    """Main game controller. Owns the game state, network peer, and rendering."""

    def __init__(
        self,
        screen: pygame.Surface,
        peer: NetworkPeer,
        player_id: int,
        seed: int,
    ) -> None:
        self._screen = screen
        self._peer = peer
        self._player_id = player_id
        self._clock = pygame.time.Clock()

        # Tile rendering size
        self._tile_size = TILE_RENDER_SIZE

        # Simulation (GameState generates the tilemap internally from the seed)
        self._state = GameState(seed=seed)
        self._setup_initial_state()
        # Compute initial visibility so fog is correct from the start
        self._state.visibility.update(self._state.entities, 0)
        self._state.visibility.update(self._state.entities, 1)

        # Camera (pixel offset into the map surface)
        self._camera_x = 0
        self._camera_y = 0
        tilemap = self._state.tilemap
        self._max_camera_x = max(0, tilemap.width * self._tile_size - screen.get_width())
        self._max_camera_y = max(0, tilemap.height * self._tile_size - screen.get_height())
        # Center camera on player's start position
        self._center_camera_on_start()

        # Lockstep
        self._pending_commands: dict[int, list[Command]] = {}
        self._commands_sent_for_tick: set[int] = set()
        self._peer_commands: dict[int, list[Command]] = {}
        self._waiting_for_peer = False

        # Rendering interpolation
        self._prev_positions: list[tuple[int, int]] | None = None
        self._tick_accumulator_ms: int = 0
        self._last_frame_time_ms: int = pygame.time.get_ticks()

        # Components
        self._renderer = Renderer(screen, tilemap=self._state.tilemap)
        self._input = InputHandler(player_id, self._tile_size)

        # Phase
        self._phase = GamePhase.CONNECTING
        self._desync_detected = False
        self._desync_tick: int = -1

    def _center_camera_on_start(self) -> None:
        """Center camera on this player's starting area."""
        tilemap = self._state.tilemap
        if self._player_id < len(tilemap.start_positions):
            sx, sy = tilemap.start_positions[self._player_id]
            # Convert tile coords to pixel coords, center on screen
            px = sx * self._tile_size - self._screen.get_width() // 2
            py = sy * self._tile_size - self._screen.get_height() // 2
            self._camera_x = max(0, min(px, self._max_camera_x))
            self._camera_y = max(0, min(py, self._max_camera_y))

    def _setup_initial_state(self) -> None:
        """Create starting entities for both players.

        Per balance.md: 1 hive + STARTING_ANTS ants per player,
        plus neutral HIVE_SITE entities at expansion points,
        and wildlife around the map.
        """
        tilemap = self._state.tilemap
        mt = MILLI_TILES_PER_TILE

        # Ant placement offsets (tile offsets from hive, for STARTING_ANTS=5)
        ant_offsets = [(-2, -1), (-1, 1), (0, -2), (1, 1), (2, -1)]

        for player_id, (tx, ty) in enumerate(tilemap.start_positions):
            hive_x = tx * mt + mt // 2
            hive_y = ty * mt + mt // 2

            # Spawn hive
            self._state.create_entity(
                player_id=player_id, x=hive_x, y=hive_y,
                entity_type=EntityType.HIVE,
                speed=0, hp=HIVE_HP, max_hp=HIVE_HP, damage=0,
                sight=HIVE_SIGHT,
            )

            # Spawn starting ants around the hive
            for i in range(STARTING_ANTS):
                dx, dy = ant_offsets[i % len(ant_offsets)]
                ax = hive_x + dx * mt
                ay = hive_y + dy * mt
                self._state.create_entity(
                    player_id=player_id, x=ax, y=ay,
                    entity_type=EntityType.ANT,
                    speed=ANT_SPEED, hp=ANT_HP, max_hp=ANT_HP,
                    damage=ANT_DAMAGE, jelly_value=ANT_CORPSE_JELLY,
                )

        # Place neutral hive sites at expansion points
        for sx, sy in tilemap.hive_site_positions:
            site_x = sx * mt + mt // 2
            site_y = sy * mt + mt // 2
            self._state.create_entity(
                player_id=-1, x=site_x, y=site_y,
                entity_type=EntityType.HIVE_SITE,
                speed=0, hp=0, max_hp=0, damage=0, sight=0,
            )

        # Spawn wildlife around map center
        mcx = (tilemap.width // 2) * mt
        mcy = (tilemap.height // 2) * mt

        # Aphids
        for dx in range(4):
            self._state.create_entity(
                player_id=-1, x=mcx + dx * mt, y=mcy - 8 * mt,
                entity_type=EntityType.APHID, speed=0,
                hp=APHID_HP, max_hp=APHID_HP, jelly_value=APHID_JELLY,
                sight=0)

        # Beetle
        self._state.create_entity(
            player_id=-1, x=mcx + 8 * mt, y=mcy,
            entity_type=EntityType.BEETLE, speed=0,
            hp=BEETLE_HP, max_hp=BEETLE_HP,
            damage=BEETLE_DAMAGE, jelly_value=BEETLE_JELLY,
            sight=0)

        # Mantis
        self._state.create_entity(
            player_id=-1, x=mcx, y=mcy + 8 * mt,
            entity_type=EntityType.MANTIS, speed=0,
            hp=MANTIS_HP, max_hp=MANTIS_HP,
            damage=MANTIS_DAMAGE, jelly_value=MANTIS_JELLY,
            sight=0)

    def run(self) -> None:
        """Main game loop. Returns when the game ends."""
        running = True
        while running:
            # --- Event handling ---
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                    # Update camera bounds for new screen size
                    tm = self._state.tilemap
                    self._max_camera_x = max(
                        0, tm.width * self._tile_size - self._screen.get_width())
                    self._max_camera_y = max(
                        0, tm.height * self._tile_size - self._screen.get_height())

            if not running:
                break

            # --- Network poll ---
            self._peer.poll()

            # --- Phase logic ---
            if self._phase == GamePhase.CONNECTING:
                if self._peer.is_connected():
                    self._phase = GamePhase.PLAYING
                    self._last_frame_time_ms = pygame.time.get_ticks()
                    logger.info("Game started! Player %d", self._player_id)

            if self._phase == GamePhase.PLAYING:
                self._update_playing(events)
            elif self._phase == GamePhase.CONNECTING:
                self._draw_connecting()
            elif self._phase == GamePhase.DISCONNECTED:
                self._draw_disconnected()

            self._clock.tick(FPS)

        self._peer.disconnect()

    def _update_camera(self) -> None:
        """Scroll camera based on held arrow keys."""
        keys = pygame.key.get_pressed()
        dx = 0
        dy = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= CAMERA_SCROLL_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += CAMERA_SCROLL_SPEED
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= CAMERA_SCROLL_SPEED
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += CAMERA_SCROLL_SPEED

        self._camera_x = max(0, min(self._camera_x + dx, self._max_camera_x))
        self._camera_y = max(0, min(self._camera_y + dy, self._max_camera_y))

    def _update_playing(self, events: list[pygame.event.Event]) -> None:
        """Main gameplay update: process input, lockstep, render."""
        now_ms = pygame.time.get_ticks()
        dt_ms = now_ms - self._last_frame_time_ms
        self._last_frame_time_ms = now_ms

        # --- Camera ---
        self._update_camera()

        # --- Input -> Commands ---
        new_commands = self._input.process_events(
            events, self._state, self._state.tick,
            camera_x=self._camera_x, camera_y=self._camera_y,
        )
        for cmd in new_commands:
            self._pending_commands.setdefault(cmd.tick, []).append(cmd)

        # --- Send commands for upcoming ticks ---
        self._send_pending_commands()

        # --- Try to advance simulation (lockstep) ---
        self._tick_accumulator_ms += dt_ms
        ticks_to_run = self._tick_accumulator_ms // TICK_DURATION_MS

        for _ in range(ticks_to_run):
            if not self._try_advance_tick():
                break  # waiting for peer
            self._tick_accumulator_ms -= TICK_DURATION_MS

        # Cap accumulator to prevent spiral of death
        if self._tick_accumulator_ms > TICK_DURATION_MS * 5:
            self._tick_accumulator_ms = TICK_DURATION_MS * 5

        # --- Check for timeout ---
        from src.networking.udp_peer import UdpNetworkPeer
        if isinstance(self._peer, UdpNetworkPeer):
            elapsed = self._peer.time_since_last_recv() * 1000
            if elapsed > NET_TIMEOUT_DISCONNECT_MS:
                self._phase = GamePhase.DISCONNECTED
                return
            self._waiting_for_peer = elapsed > NET_TIMEOUT_WARNING_MS

        # --- Render ---
        interp = self._tick_accumulator_ms / TICK_DURATION_MS
        self._render(interp)

    def _send_pending_commands(self) -> None:
        """Send commands for ticks we haven't sent yet."""
        for tick in range(self._state.tick, self._state.tick + INPUT_DELAY_TICKS):
            if tick not in self._commands_sent_for_tick:
                cmds = self._pending_commands.get(tick, [])
                self._peer.send_commands(tick, cmds)
                self._commands_sent_for_tick.add(tick)

    def _try_advance_tick(self) -> bool:
        """Try to advance the simulation by one tick. Returns False if blocked."""
        tick = self._state.tick

        # Get our commands for this tick
        our_cmds = self._pending_commands.pop(tick, [])

        # Ensure we've sent commands for this tick
        if tick not in self._commands_sent_for_tick:
            self._peer.send_commands(tick, our_cmds)
            self._commands_sent_for_tick.add(tick)

        # Get peer's commands for this tick
        if tick not in self._peer_commands:
            peer_cmds = self._peer.receive_commands(tick)
            if peer_cmds is None:
                # Not ready yet — put our commands back and wait
                if our_cmds:
                    self._pending_commands[tick] = our_cmds
                return False
            self._peer_commands[tick] = peer_cmds

        peer_cmds = self._peer_commands.pop(tick)

        # Save positions for interpolation
        self._prev_positions = [(e.x, e.y) for e in self._state.entities]

        # Merge and sort all commands deterministically
        all_cmds = our_cmds + peer_cmds
        all_cmds.sort(key=lambda c: c.sort_key())

        # Advance simulation
        advance_tick(self._state, all_cmds)

        # Clean up sent tracking for old ticks
        self._commands_sent_for_tick.discard(tick)

        # Desync detection
        if self._state.tick % HASH_CHECK_INTERVAL == 0:
            self._check_hash()

        return True

    def _check_hash(self) -> None:
        """Exchange and compare state hashes for desync detection."""
        tick = self._state.tick
        our_hash = self._state.compute_hash()
        self._peer.send_hash(tick, our_hash)

        peer_hash = self._peer.receive_hash(tick)
        if peer_hash is not None and peer_hash != our_hash:
            self._desync_detected = True
            self._desync_tick = tick
            logger.error(
                "DESYNC at tick %d! Our hash: %s, Peer hash: %s",
                tick,
                our_hash.hex()[:16],
                peer_hash.hex()[:16],
            )

    def _render(self, interp: float) -> None:
        """Draw the current frame."""
        jelly = self._state.player_jelly.get(self._player_id, 0)
        ant_count = sum(
            1 for e in self._state.entities
            if e.entity_type == EntityType.ANT and e.player_id == self._player_id
        )
        debug_info = {
            "Tick": str(self._state.tick),
            "Player": str(self._player_id),
            "Jelly": str(jelly),
            "Ants": str(ant_count),
            "FPS": str(int(self._clock.get_fps())),
            "Connected": str(self._peer.is_connected()),
        }
        if self._waiting_for_peer:
            debug_info["Status"] = "Waiting for opponent..."
        if self._desync_detected:
            debug_info["DESYNC"] = f"at tick {self._desync_tick}"

        peer_addr = self._peer.get_peer_address()
        if peer_addr:
            debug_info["Peer"] = f"{peer_addr[0]}:{peer_addr[1]}"

        self._renderer.draw(
            self._state, self._prev_positions, interp, debug_info,
            camera_x=self._camera_x, camera_y=self._camera_y,
            player_id=self._player_id,
        )

    def _draw_connecting(self) -> None:
        """Draw the connecting/waiting screen."""
        sw = self._screen.get_width()
        sh = self._screen.get_height()
        self._screen.fill((20, 20, 30))
        font = pygame.font.SysFont("monospace", 24)
        text = font.render("Waiting for opponent to connect...", True, (200, 200, 200))
        rect = text.get_rect(center=(sw // 2, sh // 2))
        self._screen.blit(text, rect)

        sub_font = pygame.font.SysFont("monospace", 16)
        if self._peer.get_peer_address():
            addr = self._peer.get_peer_address()
            info = f"Peer: {addr[0]}:{addr[1]}"
        else:
            info = "Listening for connections..."
        sub_text = sub_font.render(info, True, (150, 150, 150))
        sub_rect = sub_text.get_rect(center=(sw // 2, sh // 2 + 40))
        self._screen.blit(sub_text, sub_rect)

        pygame.display.flip()

    def _draw_disconnected(self) -> None:
        """Draw the disconnected screen."""
        sw = self._screen.get_width()
        sh = self._screen.get_height()
        self._screen.fill((40, 20, 20))
        font = pygame.font.SysFont("monospace", 24)
        text = font.render("Disconnected from peer", True, (220, 80, 60))
        rect = text.get_rect(center=(sw // 2, sh // 2))
        self._screen.blit(text, rect)
        pygame.display.flip()
