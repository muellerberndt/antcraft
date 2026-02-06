# Phase 1: Core Game Loop + P2P Networking

## Goal

Two players connect over the network and each control a placeholder ant on a shared blank map. Ants move deterministically — both screens show the same state.

This phase produces the **foundation** everything else builds on. Getting lockstep determinism right here means the rest of development is "just adding game logic."

## Milestone Deliverable

A runnable demo where:
- Player 1 starts a game (host) and Player 2 joins via IP address.
- Each player sees a blank map with two colored circles (ants).
- Click to move your ant. The command is sent to the peer.
- Both clients advance in lockstep. Ants move identically on both screens.
- A desync is detected and logged if state hashes diverge.

---

## 1. Deterministic Game Loop

### Fixed-Tick Simulation

```
TICK_RATE = 10  # simulation ticks per second
TICK_DURATION = 1000 // TICK_RATE  # ms per tick (integer)

while running:
    # 1. Process input → enqueue commands
    # 2. Network: send our commands, receive peer commands
    # 3. If both peers ready for tick N → advance simulation
    # 4. Render current state (decoupled from tick rate)
```

- The simulation advances in fixed steps (e.g., 10 ticks/sec = 100ms per tick).
- Rendering runs at the display refresh rate and **interpolates** between ticks for smooth movement.
- All simulation values use **integer math** (positions in sub-pixel units, e.g., 1 tile = 1000 units).

### Coordinate System

- Positions stored as integer "milli-tiles": 1 tile = 1000 units.
- Movement speed expressed as milli-tiles per tick.
- This avoids floating-point non-determinism entirely.

## 2. Command System

Commands are the **only way** players affect the simulation. No direct state mutation.

```python
@dataclass
class Command:
    command_type: CommandType  # MOVE, STOP, BUILD, ATTACK, etc.
    player_id: int
    tick: int                  # which tick this executes on
    payload: dict              # type-specific data (target_x, target_y, unit_id, etc.)
```

### Command Flow

1. Player clicks → `InputHandler` creates a `Command`.
2. Command is tagged with `current_tick + INPUT_DELAY` (e.g., +2 ticks latency buffer).
3. Command is added to local queue AND sent to peer.
4. On tick N, simulation consumes all commands for tick N from both players.

### Input Delay

A small delay buffer (2–4 ticks) allows time for commands to reach the peer before the tick they execute on. This hides network latency from the player.

## 3. P2P Networking

### Connection

- **Transport:** UDP with a lightweight reliability layer for critical messages (connect/disconnect, hash checks). Game commands are sent unreliably with redundancy (send each command 3x).
- **Discovery:** Direct IP:port entry for now. Player 1 hosts (binds a port), Player 2 connects.
- **Handshake:** Exchange player IDs, agree on random seed, confirm tick rate, start game.

### Message Types

| Message | Purpose | Reliable? |
|---------|---------|-----------|
| `CONNECT` | Join request | Yes |
| `CONNECT_ACK` | Accept + game params (seed, tick rate) | Yes |
| `COMMANDS` | Commands for tick N | No (redundant) |
| `TICK_ACK` | Confirm ready to advance tick N | No (redundant) |
| `HASH_CHECK` | State hash for tick N (every K ticks) | Yes |
| `DESYNC` | Desync detected, includes debug info | Yes |
| `DISCONNECT` | Clean shutdown | Yes |

### Lockstep Protocol

```
Tick N:
  1. Collect local commands for tick N
  2. Send COMMANDS(tick=N, cmds=[...]) to peer
  3. Wait until we have peer's commands for tick N
  4. Execute all commands for tick N (sorted by player_id for determinism)
  5. Advance simulation
  6. Every 10 ticks: compute state hash, exchange HASH_CHECK
```

If a peer's commands haven't arrived, the simulation **waits** (the game freezes briefly). This is the fundamental lockstep tradeoff: consistency over smoothness.

### Timeout & Recovery

- If no message from peer for 5 seconds → show "Waiting for opponent..." overlay.
- If no message for 30 seconds → disconnect.
- No reconnection in Phase 1 (add later if needed).

## 4. Simulation State

```python
@dataclass
class GameState:
    tick: int
    entities: list[Entity]
    rng_state: int  # deterministic PRNG state

@dataclass
class Entity:
    entity_id: int
    player_id: int
    x: int  # milli-tiles
    y: int  # milli-tiles
    target_x: int
    target_y: int
    speed: int  # milli-tiles per tick
```

### State Hashing

Every K ticks, compute a hash of the full game state and exchange it with the peer. If hashes differ → desync detected → log full state for debugging.

```python
def hash_state(state: GameState) -> int:
    # Hash tick + all entity fields in deterministic order
    ...
```

## 5. Rendering (Minimal)

- Blank colored background (the "map").
- Each ant is a colored circle at its interpolated position.
- Text overlay: current tick, connection status, latency.
- No sprites, no tiles, no UI beyond debug info.

---

## Shared Interfaces (DONE)

The shared interfaces have been implemented and tested. Both devs branch from here.

- **`src/config.py`** — all shared constants (tick rate, screen size, coordinate system, networking params)
- **`src/simulation/commands.py`** — `Command` (frozen dataclass), `CommandType` enum, `CommandQueue`
- **`src/simulation/state.py`** — `Entity` dataclass, `GameState` with deterministic PRNG and state hashing
- **`src/networking/peer.py`** — `NetworkPeer` ABC (the interface contract) + `MockNetworkPeer` for local testing
- **`src/networking/protocol.py`** — `MessageType` enum and message dataclasses

Tests: `tests/test_simulation/test_state.py`, `tests/test_simulation/test_commands.py` (18 tests, all passing).

---

## Work Split & Todo Lists

This phase has a clean interface boundary at **NetworkPeer**. Dev A calls it; Dev B implements it.

### Dev A — Simulation & Game Loop

| # | Task | Files | Details |
|---|------|-------|---------|
| A1 | Implement tick logic | `src/simulation/tick.py` | `advance_tick(state, commands)`: process MOVE commands, update entity positions (integer movement toward target). Must be pure and deterministic. |
| A2 | Write tick determinism tests | `tests/test_simulation/test_tick.py` | Create two GameStates with same seed, apply same commands, assert state hashes match after N ticks. Test edge cases: diagonal movement, reaching target exactly, zero-length move. |
| A3 | Build the main game loop | `src/main.py`, `src/game.py` | PyGame init, main loop with fixed-tick simulation decoupled from render FPS. Use `MockNetworkPeer` initially. State machine: MENU → CONNECTING → PLAYING. |
| A4 | Input handling | `src/input/handler.py` | Convert mouse clicks to MOVE commands. Tag commands with `current_tick + INPUT_DELAY`. Map screen coords to milli-tile coords. |
| A5 | Placeholder renderer | `src/rendering/renderer.py` | Draw background, draw entities as colored circles (interpolate positions between ticks for smoothness). Show debug overlay: tick count, connection status. |
| A6 | Game initialization | `src/game.py` | On game start: create GameState with agreed seed, spawn 1 entity per player at starting positions. |
| A7 | Desync detection | `src/game.py` | Every `HASH_CHECK_INTERVAL` ticks: compute state hash, send via `NetworkPeer.send_hash()`, compare with peer's hash. Log full state dump on mismatch. |
| A8 | Integration with real NetworkPeer | `src/main.py` | Swap `MockNetworkPeer` for Dev B's `UdpNetworkPeer`. Add CLI args: `--host PORT` and `--join HOST:PORT`. |

**Dev A can start immediately** using `MockNetworkPeer` — no dependency on Dev B until task A8.

### Dev B — Networking

| # | Task | Files | Details |
|---|------|-------|---------|
| B1 | Command serialization | `src/networking/serialization.py` | Binary encode/decode `Command` objects using `struct`. Format: `[type:u8][player:u8][tick:u32][n_entities:u16][entity_ids:u32*n][target_x:i32][target_y:i32]`. Must be deterministic and compact. |
| B2 | Serialization tests | `tests/test_networking/test_serialization.py` | Round-trip tests: encode → decode for every CommandType. Test edge cases: empty entity_ids, negative coordinates, max values. |
| B3 | Message framing | `src/networking/serialization.py` | Wrap serialized commands into messages with header: `[msg_type:u8][payload_len:u16][payload:bytes]`. Implement for all MessageType variants. |
| B4 | UDP socket layer | `src/networking/peer.py` | `UdpNetworkPeer(NetworkPeer)`: non-blocking UDP socket, send/receive with buffering. Handle partial reads, out-of-order delivery. |
| B5 | Connection handshake | `src/networking/peer.py` | Host binds port and waits. Client sends CONNECT. Host replies CONNECT_ACK with seed + tick rate. Implement with retry (resend CONNECT every 1s until ACK). |
| B6 | Command exchange | `src/networking/peer.py` | `send_commands()`: serialize + send COMMANDS message 3x (redundancy for UDP). `receive_commands()`: buffer incoming commands by tick, deduplicate, return when available. |
| B7 | Hash exchange | `src/networking/peer.py` | `send_hash()` / `receive_hash()`: reliable delivery (resend until ACK). Buffer received hashes by tick. |
| B8 | Timeout & disconnect | `src/networking/peer.py` | Track last-message timestamp. Surface "waiting" state after 5s. Disconnect after 30s. Handle DISCONNECT message for clean shutdown. |
| B9 | Protocol integration test | `tests/test_networking/test_protocol.py` | Spin up two UdpNetworkPeer instances on localhost. Run a simulated 100-tick exchange. Verify all commands arrive, hashes match, no dropped data. |

**Dev B can test independently** by writing a simple script that sends/receives mock commands between two local peers.

### Integration Checklist

Once both devs are ready, merge and verify:

1. [ ] Dev A switches from `MockNetworkPeer` to `UdpNetworkPeer` (task A8)
2. [ ] Start two game instances: `python -m src.main --host 23456` and `python -m src.main --join 127.0.0.1:23456`
3. [ ] Both windows show two colored circles (ants)
4. [ ] Clicking in either window moves that player's ant on BOTH screens
5. [ ] Debug overlay shows matching tick counts
6. [ ] Let it run for 100+ ticks — hash checks all pass
7. [ ] Intentionally break determinism (e.g., add +1 to one client's position) → desync detected and logged
8. [ ] Close one client cleanly → other shows disconnect message

---

## Done Criteria

- [ ] Two game instances connect over LAN (localhost is fine).
- [ ] Each player controls an ant via click-to-move.
- [ ] Both screens show identical ant positions at all times.
- [ ] State hash checks pass (no desync on normal operation).
- [ ] Intentionally injecting different inputs on one peer triggers desync detection.
- [ ] Tests pass: simulation determinism, command serialization, protocol messages.
