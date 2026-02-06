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

# --- Map (Phase 1: just a blank arena) ---
MAP_WIDTH_TILES = 60
MAP_HEIGHT_TILES = 40

# --- Units (Phase 1 placeholder) ---
DEFAULT_UNIT_SPEED = 80  # milli-tiles per tick

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
