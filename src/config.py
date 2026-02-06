"""Shared constants for AntCraft. All game-wide configuration lives here."""

# --- Display ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

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
ANT_SPEED = 60           # milli-tiles per tick
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

# --- Economy ---
STARTING_JELLY = 50
STARTING_ANTS = 5
CORPSE_DECAY_TICKS = 150  # 15 sec at 10 Hz

# --- General ---
SIGHT_RADIUS = 5          # tiles
ATTACK_RANGE = 1          # tiles

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
