# AntCraft — Game Mechanics Spec

## Overview

AntCraft is a 2D multiplayer ant battle arena RTS. Players control ant colonies,
expand across the map, fight wildlife and enemy colonies, and harvest the dead
for resources. Last colony standing wins.

2-4 players. LAN / direct IP multiplayer.

---

## Core Concept: Ants Are the Resource

There is one unit type: the **ant**. Ants are simultaneously your army, your
workforce, and your economy. Every ant you lose weakens you. Every ant you kill
feeds you.

---

## Resources

### Jelly

Jelly is the single resource. It is used to spawn new ants and create queens.

Jelly is acquired by:

1. **Passive income** — Each hive generates a small trickle of jelly over time.
2. **Harvesting corpses** — Dead ants (yours or enemy) and dead wildlife drop
   jelly. Send ants to a corpse to carry jelly back to the nearest hive.
3. **Killing wildlife** — NPC creatures roam the map. Killing them yields jelly.
Jelly is stored globally per player (not per-hive).

---

## Units

### Ant (single unit type)

- Spawned from a hive for a jelly cost
- Can move, attack, carry jelly, and merge into a queen
- Identical stats for all players
- Ants have HP; when HP reaches 0 they die and leave a corpse worth half
  their spawn cost in jelly

### Queen (temporary / special)

- Created by **merging N ants** together at a hive
- The queen is a single slow-moving unit
- Her only purpose: walk to an empty hive site and **found a new hive**
- Once the hive is founded, the queen is consumed (she becomes the hive)
- If the queen is killed before reaching the site, the ants are lost
- Queens cannot attack

---

## Structures

### Hive

- Each player starts with **1 hive**
- Hives spawn ants (costs jelly, has a cooldown/queue)
- Hives generate passive jelly income
- Hives have HP and can be destroyed
- A player is eliminated when all their hives are destroyed
- Hives cannot be rebuilt once destroyed

### Hive Sites (neutral, fixed on map)

- Empty locations on the map where a new hive can be founded
- Visible to all players from the start
- A queen must reach the site to found a new hive
- Once claimed, the site becomes that player's hive
- Limited number of sites per map — expansion is contested

---

## Wildlife (NPC creatures)

Animals spawn randomly on the map. They provide jelly when killed but vary
in difficulty.

### Tier 1: Aphids (passive)

- Small, harmless. Free jelly, no risk.
- Spawn in clusters. Don't fight back.
- Drop a small amount of jelly when killed.

### Tier 2: Beetles (medium)

- Tough, slow. High HP, deal damage to nearby ants.
- Need a few ants to take down safely.
- Drop a moderate amount of jelly.

### Tier 3: Mantis (boss)

- Praying mantis. Massive HP, huge damage, can one-shot individual ants.
- Need a real army to kill. Rare spawn.
- Drop a huge amount of jelly.

Wildlife spawns randomly over time at random locations on the map.

---

## Combat

- Ants auto-attack enemies within range
- Combat is simple: ants deal DPS to each other, HP goes down
- No armor, no abilities — just numbers and positioning
- When an ant dies, it leaves a **corpse** on the ground
- Corpses persist for a limited time, decaying over time and yielding
  less jelly the longer they sit
- Any player's ants can harvest any corpse (including their own dead)

---

## Expansion

1. Player decides to expand
2. Player merges **N ants** (e.g. 5) at an existing hive to create a **queen**
3. Player sends the queen to an unclaimed **hive site**
4. Queen arrives and founds the hive (queen is consumed)
5. New hive starts producing ants and generating income

**Risk/reward**: Creating a queen costs N ants from your army. The queen is
slow and defenseless. Opponents can intercept and kill the queen, wasting
your investment. Expanding early is greedy; expanding late means less income.

---

## Win Condition

**Last colony standing.** A player is eliminated when all their hives are
destroyed. Last player with at least one hive wins.

---

## Map

- Top-down 2D grid
- Fixed map size, procedurally placed features
- Features: hive sites, wildlife spawn points, obstacles (rocks, water)
- Starting hives placed symmetrically for fairness
- Hive sites distributed around the map to encourage expansion and conflict

---

## Numbers

See [balance.md](balance.md) for all unit, structure, wildlife, and economy parameters.

---

## Future Ideas (not in v1)

- **Pheromone trails**: Ants leave trails, longer connected networks increase
  income or movement speed. Enemies can disrupt trails.
- **Ant specialization**: Upgrade hives to spawn soldier ants vs worker ants.
- **Fog of war**: Only see areas near your ants/hives.
- **Map hazards**: Rain floods, falling leaves, etc.
