# Phase 4: Iteration, Bots & Polish

## Goal

Make the game **fun**. Phase 3 delivers a functional game; Phase 4 makes it a good one. This phase is open-ended — iterate based on playtesting feedback until matches feel tight, fair, and exciting.

## Key Activities

### 1. Playtesting Protocol

Structured playtesting catches balance and UX issues early.

**Per session:**
1. Play 2–3 full matches.
2. Each player notes: what felt unfair, what was boring, what was confusing.
3. Log match stats automatically: game length, food gathered, units built, units lost, winner.
4. After each session, pick the top 2–3 issues and fix them before next session.

**Checklist of things to test:**
- [ ] Is the early game interesting? (not just waiting for food)
- [ ] Are all unit types worth building?
- [ ] Is there a dominant strategy that beats everything? (bad — means no real choices)
- [ ] Do games end decisively, or drag on?
- [ ] Is the tech tree meaningful? (do upgrade choices matter?)
- [ ] Is fog of war effective? (does scouting matter?)
- [ ] Is the UI clear? (can you tell what's happening?)
- [ ] Does the game feel responsive? (input → action latency)

### 2. Bot / AI Opponent

A bot serves two purposes: solo testing without needing a second human, and automated balance testing.

#### Architecture

```python
class Bot:
    """Replaces a human player — generates commands each tick."""

    def decide(self, state: GameState, player_id: int) -> list[Command]:
        # Analyze game state
        # Return commands for this tick
        ...
```

- The bot plugs into the same command system as a human player.
- It reads GameState and produces Commands — same interface.
- For networked testing, the bot runs as a second process and connects normally.
- For local testing, it runs in-process (skip networking).

#### Bot Difficulty Tiers

| Tier | Behavior |
|------|----------|
| **Passive** | Builds workers, gathers food, never attacks. For testing economy. |
| **Aggressive** | Rushes with soldiers as fast as possible. Tests early defense. |
| **Balanced** | Follows a basic build order: economy → army → attack. The real test. |

#### Implementation Priority

1. **Passive bot** first — validates economy works end-to-end.
2. **Aggressive bot** — validates combat and defense.
3. **Balanced bot** — validates the full game loop.

### 3. Automated Balance Testing

Run bot-vs-bot simulations headlessly (no rendering) to gather data.

```python
def run_simulation(bot_a: Bot, bot_b: Bot, seed: int) -> MatchResult:
    """Run a complete game with no rendering. Return stats."""
    state = GameState(seed=seed)
    while not state.game_over:
        cmds_a = bot_a.decide(state, player_id=0)
        cmds_b = bot_b.decide(state, player_id=1)
        tick(state, cmds_a + cmds_b)
    return MatchResult(
        winner=state.winner,
        duration=state.tick,
        stats_a=state.player_stats[0],
        stats_b=state.player_stats[1],
    )

# Run 100 games with different seeds
results = [run_simulation(BalancedBot(), BalancedBot(), seed=i) for i in range(100)]
# Analyze: win rate should be ~50%, avg game length, most-built unit, etc.
```

**What to look for:**
- Win rate significantly off 50% → map gen or starting positions are unfair.
- One unit type never built → it's underpowered or overpriced.
- Games consistently too short (<5 min) or too long (>30 min) → adjust economy pacing.
- Same opening build every time → not enough viable strategies.

### 4. Balance Knobs

Keep all balance values in a single config, easy to tweak:

```python
# src/config.py or src/balance.py
UNIT_STATS = {
    EntityType.WORKER:  {"hp": 30, "speed": 80, "attack": 5, "cost": 50, ...},
    EntityType.SOLDIER: {"hp": 80, "speed": 60, "attack": 15, "cost": 100, ...},
    ...
}

BUILDING_STATS = { ... }
UPGRADE_STATS = { ... }
```

- All stats in one place makes it easy to tweak between playtests.
- Consider a simple JSON/TOML file for stats so non-programmers can edit.

### 5. UX & Visual Polish

| Area | Improvement |
|------|-------------|
| **Unit feedback** | Health bars, selection circles, rally point indicators |
| **Combat feedback** | Damage numbers, hit flash, death animation |
| **Audio** | Movement sounds, attack sounds, ambient colony noise, music |
| **UI** | Tooltips for buildings/units, hotkey hints, better minimap |
| **Performance** | Profile with cProfile, optimize hot paths (rendering, pathfinding) |
| **Sprites** | Replace placeholder shapes with pixel art or simple sprites |

### 6. Performance Profiling

```bash
python -m cProfile -o profile.dat -m src.main
# Analyze with snakeviz
pip install snakeviz
snakeviz profile.dat
```

Key areas to watch:
- Pathfinding: should be <1ms per unit per request.
- Rendering: should maintain 60fps with 50+ entities.
- Fog of war: recomputing visibility each tick can be expensive — optimize if needed.

---

## Work Split

Phase 4 is more collaborative — both devs playtest together and fix issues as they arise.

### Dev A — Bots & Balance
- Bot architecture and all bot tiers
- Headless simulation runner for automated testing
- Balance analysis tooling (stats aggregation, reports)
- Stat tuning based on data

### Dev B — Polish & UX
- Audio system (`src/audio/manager.py`)
- Visual effects and feedback (damage numbers, animations)
- UI improvements (tooltips, hotkeys, improved HUD)
- Sprite creation or integration
- Performance profiling and optimization

### Shared
- Playtesting (both play together)
- Bug fixes (whoever hits it, fixes it)
- Balance discussions and stat adjustments

---

## Done Criteria

- [ ] A bot opponent exists at 3 difficulty tiers.
- [ ] Headless bot-vs-bot simulation runs and produces stats.
- [ ] 50+ bot-vs-bot games show roughly balanced outcomes.
- [ ] At least 10 human playtest sessions completed with notes.
- [ ] Top UX issues from playtesting are addressed.
- [ ] Game runs at stable 60fps with 50+ units on screen.
- [ ] Sound effects for core actions (move, attack, build, gather).
- [ ] The game is fun to play.
