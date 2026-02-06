# AntCraft

P2P multiplayer real-time strategy game built with PyGame. Players control ant colonies, managing resources, building structures, and commanding units in real time.

## Tech Stack

- **Language:** Python 3.12
- **Game engine:** PyGame
- **Networking:** P2P multiplayer (protocol TBD)

## Project Structure

```
antcraft/
├── CLAUDE.md          # This file — project context for AI agents
├── AGENTS.md          # Guidelines for AI coding agents
├── README.md
├── requirements.txt   # Python dependencies
└── src/               # Game source code (TBD)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
python -m src.main    # (once implemented)
```

## Development Commands

```bash
# Run the game
python -m src.main

# Run tests
python -m pytest tests/

# Lint
python -m flake8 src/
```

## Architecture Notes

- This is a real-time strategy game — game loop timing and frame-rate independence matter.
- P2P networking means no authoritative server; synchronization and determinism are key concerns.
- PyGame handles rendering, input, and audio.
