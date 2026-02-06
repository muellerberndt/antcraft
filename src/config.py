"""Shared constants for AntCraft. All game-wide configuration lives here."""

# --- Display ---
SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 900
FPS = 60
TILE_RENDER_SIZE = 16  # pixels per tile for rendering

# --- Simulation ---
TICK_RATE = 10  # simulation ticks per second
TICK_DURATION_MS = 1000 // TICK_RATE  # ms per tick (100ms)

# --- Coordinate system ---
# 1 tile = 1000 milli-tiles. All simulation positions use milli-tiles (integers).
MILLI_TILES_PER_TILE = 1000

# --- Map ---
MAP_WIDTH_TILES = 100
MAP_HEIGHT_TILES = 100

# --- Ant ---
ANT_HP = 20
ANT_DAMAGE = 5           # DPS (divided by TICK_RATE for per-tick)
ANT_SPEED = 400          # milli-tiles per tick
ANT_SPAWN_COST = 10      # jelly
ANT_SPAWN_COOLDOWN = 20  # ticks (2 sec at 10 Hz)
ANT_CORPSE_JELLY = 5     # jelly dropped on death
DEFAULT_UNIT_SPEED = ANT_SPEED  # backward compat alias

# --- Queen ---
QUEEN_HP = 50
QUEEN_SPEED = 30          # milli-tiles per tick
QUEEN_MERGE_COST = 5      # ants consumed to create a queen

# --- Hive ---
HIVE_HP = 200
HIVE_PASSIVE_INCOME = 2   # jelly per second (converted to per-tick in sim)
MERGE_RANGE = 3           # tiles — ants must be this close to hive to merge
FOUND_HIVE_RANGE = 1      # tiles — queen must be this close to site to found

# --- Wildlife ---
APHID_HP = 5
APHID_DAMAGE = 0
APHID_JELLY = 3

BEETLE_HP = 80
BEETLE_DAMAGE = 8         # DPS
BEETLE_JELLY = 25

MANTIS_HP = 200
MANTIS_DAMAGE = 20        # DPS
MANTIS_JELLY = 80

# Wildlife speeds (milli-tiles per tick)
BEETLE_SPEED = 20
MANTIS_SPEED = 15

# Wildlife spawning
WILDLIFE_SPAWN_INTERVAL = 100    # ticks (10 sec) between spawn attempts
WILDLIFE_HIVE_EXCLUSION = 10     # tiles — don't spawn within this radius of hives
WILDLIFE_MAX_APHIDS = 20
WILDLIFE_MAX_BEETLES = 5
WILDLIFE_MAX_MANTIS = 2
WILDLIFE_AGGRO_RANGE = 5         # tiles — beetles/mantis chase player entities within this

# --- Harvesting ---
HARVEST_RANGE = 2             # tiles — how close to corpse to start harvesting
HARVEST_RATE = 5              # jelly per second (Bresenham distributed across ticks)
ANT_CARRY_CAPACITY = 10       # max jelly an ant can carry per trip

# --- Economy ---
STARTING_JELLY = 50
STARTING_ANTS = 5
CORPSE_DECAY_TICKS = 150  # 15 sec at 10 Hz

# --- Sight radii (tiles) ---
ANT_SIGHT = 12
QUEEN_SIGHT = 7
HIVE_SIGHT = 16

# --- General ---
SIGHT_RADIUS = ANT_SIGHT  # backward compat alias
ATTACK_RANGE = 1          # tiles
SEPARATION_RADIUS = 600   # milli-tiles — entities closer get nudged apart
SEPARATION_FORCE = 80     # push strength per overlapping neighbor per tick

# --- Camera & Input ---
CAMERA_SCROLL_SPEED = 10  # pixels per frame
CAMERA_EDGE_SCROLL_MARGIN = 20  # pixels from screen edge to trigger scroll
MINIMAP_SIZE = 200  # pixels
SELECTION_THRESHOLD = 15  # pixels, click selection radius

# --- Networking ---
DEFAULT_PORT = 23456
INPUT_DELAY_TICKS = 2  # commands execute this many ticks in the future
HASH_CHECK_INTERVAL = 10  # check state hash every N ticks
NET_TIMEOUT_WARNING_MS = 5000  # show "waiting" overlay after this
NET_TIMEOUT_DISCONNECT_MS = 30000  # disconnect after this

# --- Colors (placeholder rendering) ---
COLOR_BG = (40, 30, 20)
COLOR_PLAYER_1 = (220, 80, 60)
COLOR_PLAYER_2 = (60, 120, 220)
COLOR_DEBUG_TEXT = (200, 200, 200)
