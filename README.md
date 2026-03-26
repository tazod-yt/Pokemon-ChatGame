# Pokemon Chat Game (Portable Local Stream Game)

This project builds a fully standalone, offline, no-install local stream game for Streamer.bot + OBS. It packages a Python game engine into a single Windows EXE and serves overlay visuals via a local Browser Source.

## Folder Structure (Required)

Pokemon Chat Game/
├── GameEngine/
│   └── GameEngine.exe
├── Data/
│   ├── game.db
│   ├── active_spawn.json
│   ├── users_cache.json
│   └── overlay_state.json
├── Config/
│   └── settings.json
├── Overlay/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── Assets/
│   ├── creatures/
│   ├── icons/
│   └── sounds/
├── Logs/
│   └── game.log
├── Streamerbot/
│   └── import_actions.json
├── src/
│   └── game_engine.py
├── tests/
│   └── test_game_engine.py
└── build.ps1

## What Each Folder / File Does

GameEngine/
- `GameEngine.exe`: Standalone engine built with PyInstaller. Streamer.bot calls this.

Data/
- `game.db`: SQLite database (users, creatures, inventory, battles, settings). Auto-created.
- `active_spawn.json`: Current spawn state (one active spawn). Auto-created.
- `users_cache.json`: Reserved for future optimization. Auto-created.
- `overlay_state.json`: Overlay data source read by OBS browser source.

Config/
- `settings.json`: Gameplay settings (spawn interval, cooldowns, catch rate, etc.). Auto-created/merged with defaults.

Overlay/
- `index.html`: OBS overlay HTML (Browser Source).
- `script.js`: Polls `Data/overlay_state.json` and renders state.
- `style.css`: Overlay styling.

Assets/
- `creatures/`: Placeholder creature art (optional; replace later).
- `icons/`: Placeholder icons (optional; replace later).
- `sounds/`: Placeholder sounds (optional; replace later).

Logs/
- `game.log`: Engine log file (commands, spawns, catches, battles, errors).

Streamerbot/
- `import_actions.json`: Streamer.bot actions template wired to `GameEngine.exe`.

src/
- `game_engine.py`: Python source for the game engine CLI.

tests/
- `test_game_engine.py`: Pytest suite for core behavior.

build.ps1
- Build script that produces `GameEngine.exe` and optional `Pokemon Chat Game.zip`.

## First-Run Behavior

When `GameEngine.exe` (or the Python entry) runs the first time, it:
- Creates required folders and data files
- Creates `game.db` with required tables
- Seeds default placeholder creatures
- Writes defaults into `Config/settings.json`
- Creates `Logs/game.log`

## Command-Line Interface (Streamer.bot API)

These commands are the contract between Streamer.bot and the engine.

- `GameEngine.exe spawn`
  - Spawns a random creature (one at a time)
  - Writes to `Data/active_spawn.json` and `Data/overlay_state.json`

- `GameEngine.exe catch <username>`
  - Attempts to catch the active creature
  - Applies cooldown, catch rate, and inventory limit
  - Updates inventory and overlay

- `GameEngine.exe inventory <username>`
  - Returns a text list of the user's creatures

- `GameEngine.exe battle <user1> <user2>`
  - Simulates a turn-based battle
  - Updates stats and records battle history

- `GameEngine.exe reset_spawn`
  - Clears the active spawn and resets overlay state

## Configuration

`Config/settings.json` fields:
- `spawn_interval_seconds`
- `catch_timeout_seconds`
- `base_catch_rate`
- `battle_timeout_seconds`
- `cooldown_seconds`
- `max_inventory_size`

You can edit these values at any time. The engine will merge missing keys with defaults.

## Overlay Setup (OBS)

1. Add a Browser Source in OBS.
2. Point it to the local file:
   - `Pokemon Chat Game/Overlay/index.html`
3. Ensure the overlay can read local files (OBS setting: Local File enabled).

The overlay polls `Data/overlay_state.json` once per second.

## Streamer.bot Setup

1. Import `Streamerbot/import_actions.json`.
2. Update any paths if your Streamer.bot setup uses a different working directory.
3. Wire actions to chat commands (e.g., `!spawn`, `!catch`, `!inventory`, `!battle`).

The current JSON uses placeholders like `${user}` and `${arg1}`. Adjust to your Streamer.bot variable syntax if needed.


## Setup on Another PC (End User)

1. Unzip `Pokemon Chat Game.zip` anywhere (Desktop is fine).
2. Run `GameEngine\GameEngine.exe` once to auto-create the database, config, and logs.
3. In OBS, add a Browser Source with Local File enabled and select:
   - `Pokemon Chat Game/Overlay/index.html`
4. In Streamer.bot, import `Streamerbot/import_actions.json`.
5. Update action paths if your Streamer.bot working directory differs.
6. Bind actions to chat commands (for example `!spawn`, `!catch`, `!inventory`, `!battle`).

No installs required. The entire game runs from the extracted folder.\n## Build Instructions (Windows)

Requirements (build machine only):
- Python 3.10+
- PyInstaller

Build:
```powershell
cd Pokemon Chat Game
.\build.ps1
```

Build and zip:
```powershell
cd Pokemon Chat Game
.\build.ps1 -Zip
```

The zip is created at `Pokemon Chat Game.zip` one folder above `Pokemon Chat Game/`.

## Testing

From `Pokemon Chat Game`:
```powershell
pytest -q
```

Tests cover spawn, catch success/failure, inventory retrieval, battle simulation, and persistence.

## Notes / Gotchas

- The game runs fully offline and stores all data locally.
- Only one active spawn exists at a time.
- Catch and battle cooldowns are enforced globally per user.
- Placeholder creature data is seeded; replace with full Pokémon specs later.



