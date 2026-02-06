# AntCraft

P2P multiplayer real-time strategy game with ants, built on PyGame.

## Setup

Requires Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the Game

### Local (single player test)

```bash
python -m src.main --local
```

Runs with a mock network peer — useful for testing movement and rendering without a second player.

### Multiplayer (P2P)

Two players connect directly over UDP. One hosts, the other joins.

**Player 1 — Host:**

```bash
python -m src.main --host 23456
```

This binds to port 23456 and waits for a peer to connect. A random seed is generated and shared with the joining player to ensure both simulations are identical.

**Player 2 — Join:**

```bash
python -m src.main --join <HOST_IP>:23456
```

Replace `<HOST_IP>` with Player 1's IP address (e.g. `192.168.1.42`). For testing on the same machine, use `127.0.0.1`.

### Networking requirements

- Both players must be able to reach each other over UDP on the chosen port.
- **Same LAN:** Works out of the box — use the host's local IP (e.g. `192.168.x.x`).
- **Over the internet:** The host needs to forward the UDP port (default `23456`) on their router to their machine, or both players can use a VPN/tunnel (e.g. Tailscale, ZeroTier) to appear on the same network.

### Options

| Flag | Description |
|------|-------------|
| `--host PORT` | Host a game on the given UDP port |
| `--join HOST:PORT` | Join a hosted game |
| `--local` | Single-player test with mock networking |
| `-v, --verbose` | Enable debug logging |

## Controls

- **Left click** — Move your ant to the clicked position

## Running Tests

```bash
python -m pytest tests/ -v
```
