# AntCraft Game Manual

## Overview

AntCraft is a 2-player real-time strategy game where you command ant colonies. Build your economy by spawning ants and harvesting the dead, expand across the map by founding new hives, and destroy your opponent's colony to win.

**Core concept**: Ants are simultaneously your army, your workforce, and your economy. Every ant you lose weakens you. Every ant you kill feeds you.

## Getting Started

```bash
# Local test (single player, no opponent)
python -m src.main --local

# Host a multiplayer game
python -m src.main --host 23456

# Join a multiplayer game
python -m src.main --join 192.168.1.100:23456

# Fullscreen mode
python -m src.main --local --fullscreen
```

## Game Mechanics

### Jelly (Resource)

Jelly is the single resource. It is used to spawn ants and create queens.

**How to get jelly:**
- **Passive income** -- Each hive generates 2 jelly per second automatically
- **Harvesting corpses** -- Dead ants and wildlife drop jelly. Send ants to carry it back to your hive
- **Killing wildlife** -- NPC creatures roam the map. Kill them for jelly

You start with 50 jelly. Jelly is global per player (not per-hive).

### Ants

Your primary unit. Spawned from hives for 10 jelly (2 second cooldown).

| Stat     | Value          |
|----------|----------------|
| HP       | 20             |
| Damage   | 5 DPS          |
| Speed    | 400 milli-tiles/tick |
| Sight    | 12 tiles       |
| Corpse   | 5 jelly        |

Ants auto-attack nearby enemies within 1 tile range. They can move, attack, and carry jelly.

### Spitter Ants

Ranged combat specialists morphed from regular ants. Select an ant near your hive and press T to morph it into a spitter (costs 8 jelly, irreversible). Spitters cannot harvest corpses or merge into queens.

| Stat     | Value          |
|----------|----------------|
| HP       | 10             |
| Damage   | 4 DPS          |
| Range    | 4 tiles        |
| Speed    | 400 milli-tiles/tick |
| Sight    | 12 tiles       |
| Corpse   | 5 jelly        |
| Morph cost | 8 jelly (+ 1 ant consumed) |

Spitters are glass cannons — low HP but high effective DPS at range. Best used behind melee ants in combined-arms formations.

### Queens

Created by merging 5 ants at a hive. Queens are slow, defenseless units whose only purpose is to found new hives.

| Stat     | Value          |
|----------|----------------|
| HP       | 50             |
| Speed    | 30 milli-tiles/tick |
| Sight    | 7 tiles        |
| Damage   | 0 (cannot attack) |

If a queen is killed before reaching a hive site, all 5 ants invested are lost.

### Hives

Each player starts with 1 hive. Hives spawn ants and generate passive income.

| Stat     | Value          |
|----------|----------------|
| HP       | 200            |
| Income   | 2 jelly/sec    |
| Sight    | 16 tiles       |

Hives cannot move or attack. They can be destroyed by enemy ants.

### Hive Sites

Neutral locations on the map where new hives can be founded. Send a queen to a hive site to claim it. Once founded, the queen is consumed and the site becomes your hive.

### Harvesting

When an enemy or wildlife dies, it leaves a corpse containing jelly. Send ants to harvest it:

1. Select ants and right-click a corpse (or press E then right-click)
2. Ants walk to the corpse and extract jelly (5 jelly/sec)
3. When full (10 jelly capacity) or corpse empty, ants auto-return to nearest hive
4. Jelly is deposited at the hive, then ants go back for more
5. When the corpse is empty or decayed, ants go idle

Harvest range is 2 tiles. Corpses decay after 15 seconds, so harvest quickly.

### Combat

- Ants auto-attack the nearest enemy within 1 tile. Spitters auto-attack within 4 tiles
- Use the Attack command (A + right-click on target) to explicitly send ants to chase and fight a specific enemy
- Damage is dealt per-tick using integer math (5 DPS = 1 damage every other tick)
- Dead units leave corpses that can be harvested for jelly
- Corpses decay over 60 seconds
- Attack-mode ants will divert to closer enemies that enter their aggro range

### Wildlife

NPC creatures spawn around the map. Killing them yields jelly.

| Creature | HP  | Damage | Jelly | Behavior |
|----------|-----|--------|-------|----------|
| Aphid    | 5   | 0      | 3     | Passive, stationary |
| Beetle   | 80  | 8 DPS  | 25    | Chases players within 5 tiles |
| Mantis   | 200 | 20 DPS | 80    | Chases players within 5 tiles |

### Fog of War

You can only see areas near your ants and hives. Previously explored areas become fogged (visible terrain but no unit info).

## Win Condition

**Last colony standing.** A player is eliminated when all their hives are destroyed. The last player with at least one hive wins.

## Controls

See [hotkeys.md](hotkeys.md) for the complete controls reference.
