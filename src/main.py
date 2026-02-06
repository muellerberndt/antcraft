"""AntCraft entry point.

Usage:
    Host a game:    python -m src.main --host 23456
    Join a game:    python -m src.main --join 127.0.0.1:23456
    Local test:     python -m src.main --local
    Fullscreen:     python -m src.main --local --fullscreen
    Toggle fullscreen in-game: F11
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

import pygame

from src.config import SCREEN_HEIGHT, SCREEN_WIDTH
from src.game import Game


def main() -> None:
    parser = argparse.ArgumentParser(description="AntCraft — P2P Ant Colony RTS")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--host", type=int, metavar="PORT",
        help="Host a game on the given port",
    )
    group.add_argument(
        "--join", type=str, metavar="HOST:PORT",
        help="Join a game at HOST:PORT",
    )
    group.add_argument(
        "--local", action="store_true",
        help="Run locally with mock networking (single player test)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--fullscreen", action="store_true",
        help="Start in fullscreen mode (toggle with F11 in-game)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    pygame.init()
    if args.fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("AntCraft")

    if args.local:
        _run_local(screen)
    elif args.host is not None:
        _run_host(screen, args.host)
    elif args.join is not None:
        _run_join(screen, args.join)

    pygame.quit()


def _run_local(screen: pygame.Surface) -> None:
    """Run with MockNetworkPeer for local testing."""
    from src.networking.peer import MockNetworkPeer

    peer = MockNetworkPeer()
    peer.host(0)
    game = Game(screen, peer, player_id=0, seed=42)
    game.run()


def _run_host(screen: pygame.Surface, port: int) -> None:
    """Host a game and wait for a peer to connect."""
    from src.networking.udp_peer import UdpNetworkPeer

    peer = UdpNetworkPeer()
    peer.host(port)

    game = Game(screen, peer, player_id=peer.player_id, seed=peer.seed)
    game.run()


def _run_join(screen: pygame.Surface, addr: str) -> None:
    """Join an existing game."""
    from src.networking.udp_peer import UdpNetworkPeer

    parts = addr.rsplit(":", 1)
    if len(parts) != 2:
        print(f"Invalid address: {addr}. Expected HOST:PORT")
        sys.exit(1)
    host, port = parts[0], int(parts[1])

    peer = UdpNetworkPeer()
    peer.connect(host, port)

    # Wait for CONNECT_ACK to get seed and player_id
    print(f"Connecting to {host}:{port}...")
    deadline = time.monotonic() + 30
    last_retry = time.monotonic()
    while not peer.is_connected():
        peer.poll()
        if time.monotonic() > deadline:
            print("Connection timed out")
            sys.exit(1)
        # Retry CONNECT every second
        now = time.monotonic()
        if now - last_retry >= 1.0:
            peer.connect(host, port)
            last_retry = now
        time.sleep(0.05)

    print(f"Connected! Player {peer.player_id}, seed {peer.seed}")

    game = Game(screen, peer, player_id=peer.player_id, seed=peer.seed)
    game.run()


if __name__ == "__main__":
    main()
