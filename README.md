# Pokemon Chat Game (Portable Local Stream Game)

This project builds a fully standalone, offline, no-install local stream game for Streamer.bot + OBS. It packages a Python game engine into a single Windows EXE and serves overlay visuals via a local Browser Source.

## Folder Structure (Required)

```text
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
│   └── import_actions.txt
├── src/
│   └── game_engine.py
├── tests/
│   └── test_game_engine.py
└── build.ps1
```

## What Each Folder / File Does

GameEngine/
- `GameEngine.exe`: Standalone engine built with PyInstaller. Streamer.bot calls this.

Data/
- `game.db`: SQLite database (users, creatures, inventory, battles, pending_battles, settings). Auto-created.
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
- `import_actions.txt`: Streamer.bot actions C# runner import template (handles chat commands and executes the game engine).

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

- `GameEngine.exe auto_spawn`
  - Automates wild Pokémon spawning based on configuration. If the active spawn has expired and the auto-spawn interval cooldown has elapsed, it spawns a new wild Pokémon.

- `GameEngine.exe catch <username>`
  - Attempts to catch the active creature
  - Applies cooldown, catch rate, and inventory limit
  - Updates inventory and overlay

- `GameEngine.exe pokedex <username>`
  - Returns a text list of the user's creatures (level, XP, trait, ELO, wins/losses)

- `GameEngine.exe stats <username> <pokemon>`
  - Returns detailed stats (base stats + IVs), ELO, and records for a user's Pokémon. If a Discord webhook is configured, it sends a beautifully formatted stats card to Discord.

- `GameEngine.exe battle <challenger> <opponent> <pokemon>`
  - Challenges another user with a specific Pokémon (name or inventory slot number)
  - Creates a pending battle that expires after `battle_timeout_seconds` (default 120s)
  - Opponent must accept with `!accept @challenger <pokemon>`

- `GameEngine.exe accept <accepter> <challenger> <pokemon>`
  - Accepts a pending battle challenge and runs the fight
  - If a wild Pokémon spawn is active and not expired, the battle is queued and starts automatically once the spawn is caught or has fled
  - Awards XP, updates ELO, checks level-up evolutions, writes battle transcript to overlay state

- `GameEngine.exe leaderboard`
  - Shows top 10 Pokémon by ELO and top 10 players by ELO

- `GameEngine.exe test_battle`
  - Triggers a mock battle animation on the OBS overlay for testing animations

- `GameEngine.exe reset_spawn`
  - Clears the active spawn and resets overlay state

### Chat commands (Streamer.bot)

| Command | Description |
| --- | --- |
| `!spawn` | Spawn a wild Pokémon |
| `!catch` | Attempt to catch the active spawn |
| `!inventory` or `!pokedex` | List your Pokémon collection |
| `!stats <pokemon>` | View detailed stats, ELO, and records for a Pokémon in your collection |
| `!battle @user <pokemon>` | Challenge a user with a chosen Pokémon |
| `!accept @user <pokemon>` | Accept a challenge from that user |
| `!leaderboard` | Top 10 Pokémon and Top 10 Players by ELO |

## Configuration

`Config/settings.json` fields (defaults in `DEFAULT_SETTINGS` in `src/game_engine.py`):

- `spawn_interval_seconds` — Cooldown between manual spawns.
- `catch_timeout_seconds` — How long a spawn stays catchable before timing out (120s).
- `base_catch_rate` — Base probability modifier for catching (0.35).
- `battle_timeout_seconds` — Pending challenge expiry duration (120s).
- `battle_cooldown_seconds` — Per-user battle cooldown (6s).
- `rematch_cooldown_seconds` — Cooldown between same opponents (3s).
- `cooldown_seconds` — Catch cooldown.
- `max_inventory_size` — Max inventory size per user.
- `max_level` — Maximum Pokémon level allowed.
- `crit_chance`, `miss_chance` — Base probability for critical hits (10%) and misses (5%).
- `crit_multiplier` — Damage multiplier for critical hits (1.5x).
- `berserk_crit_bonus` — Additional critical chance bonus for Berserk trait (+0.15).
- `lucky_xp_multiplier` — Experience multiplier for Lucky trait (1.15x).
- `trait_attack_multiplier` — Attack multiplier for Brave trait (1.10x).
- `trait_defense_multiplier` — Defense multiplier for Tank trait (1.10x).
- `trait_speed_multiplier` — Speed multiplier for Swift trait (1.10x).
- `min_battle_damage` — Minimum damage dealt per turn in battles (default 5).
- `iv_min`, `iv_max` — Individual Values (IVs) range assigned on catch (0–15).
- `default_elo`, `elo_win`, `elo_loss` — Default ELO rating (1000), win gain (+25), and loss penalty (-20).
- `leaderboard_size` — Number of entries shown on the leaderboard (10).
- `xp_winner_base`, `xp_winner_level_mult` — Winner base XP (50) and multiplier per opponent level (5).
- `xp_loser_base`, `xp_loser_level_mult` — Loser base XP (15) and multiplier per opponent level (2).
- `discord_inventory_webhook_url` — Optional webhook URL to send `!inventory` and `!stats` results to a Discord channel.
- `auto_spawn_interval_seconds` — Interval for automated spawns in seconds (0 = disabled).

### Environment variables

- `STREAMERBOT_<SETTING_NAME>` or `CHATGAME_<SETTING_NAME>` — override any `Config/settings.json` numeric setting at runtime
- `DISCORD_INVENTORY_WEBHOOK_URL` or `CHATGAME_DISCORD_INVENTORY_WEBHOOK_URL` — override `discord_inventory_webhook_url` from environment

You can edit these values at any time. The engine will merge missing keys with defaults.

## Overlay Setup (OBS)

1. Add a Browser Source in OBS.
2. Point it to the local file:
   - `Pokemon Chat Game/Overlay/index.html`
3. Ensure the overlay can read local files (OBS setting: Local File enabled).

The overlay polls `Data/overlay_state.json` once per second.

## Streamer.bot Setup

1. Import `Streamerbot/import_actions.txt` (drag and drop the file, or copy-paste its contents into the **Import** box in Streamer.bot).
2. Go to **Settings -> Globals** in Streamer.bot, and create a global variable named `pokemonGamePath` pointing to the directory where the game is installed (e.g., `C:\Games\PokemonChatGame`).
3. Under the **Commands** tab, ensure that all chat commands (`!spawn`, `!catch`, `!inventory` / `!pokedex`, `!stats`, `!battle`, `!accept`, and `!leaderboard`) are enabled.

## Tools

The `Tools/` folder contains helper scripts that generate Streamer.bot exports or patch the engine source during development.

| File | Purpose |
| --- | --- |
| `Tools/gen_streamerbot_export.py` | Generates the basic `Streamerbot/import_actions.json` export. |
| `Tools/gen_full_import.py` | Generates a fuller Streamer.bot import that launches the EXE directly. |
| `Tools/gen_full_import_with_chat.py` | Generates a full import that also reads `Data/last_chat_message.txt` and sends the result back to chat. |
| `Tools/gen_full_import_with_csharp.py` | Generates a Streamer.bot export that embeds C# for the chat bridge flow. |
| `Tools/gen_full_import_csharp_runner.py` | Generates a C# runner variant that starts the EXE and forwards stdout back to chat. |
| `Tools/patch_chat_file.py` | Patch helper for adding chat message file support to `src/game_engine.py`. |
| `Tools/patch_chat_file2.py` | Alternate patch helper for the same chat file support change. |
| `Tools/patch_chat_output.py` | Patch helper that makes engine responses write to the chat output file too. |
| `Tools/patch_chat_paths.py` | Patch helper that adds `last_chat_message.txt` to the engine path setup. |
| `Tools/patch_overlay.py` | Patch helper that adjusts overlay behavior after catch and battle results. |

These scripts were written for this checkout, so if you move the project elsewhere you may need to update the hardcoded root path inside them.


## Setup on Another PC (End User)

1. Unzip `Pokemon Chat Game.zip` anywhere (Desktop is fine).
2. Run `GameEngine\GameEngine.exe` once to auto-create the database, config, and logs.
3. In OBS, add a Browser Source with Local File enabled and select:
   - `Pokemon Chat Game/Overlay/index.html`
4. In Streamer.bot, import `Streamerbot/import_actions.txt` (copy paste).
5. Update action paths if your Streamer.bot working directory differs.
6. Bind actions to chat commands (for example `!spawn`, `!catch`, `!inventory`, `!battle`, `!accept`, `!leaderboard`).

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

Tests cover spawn, catch success/failure, inventory retrieval, battle challenge/accept, leaderboard, derived stats, and persistence.

## Notes / Gotchas

- The game runs fully offline and stores all data locally.
- Only one active spawn exists at a time.
- Catch cooldown (`cooldown_seconds`) and battle cooldown (`battle_cooldown_seconds`) are enforced per user.
- Rematch cooldown (`rematch_cooldown_seconds`) applies between the same two players.
- Battles are challenge/accept: challenger picks a Pokémon, opponent accepts with their own pick.
- Each caught Pokémon has random IVs (0–15), a random trait, and starts at ELO 1000.
- Battle HP is derived fresh each fight; damage is not carried between battles.
- Level-up evolutions use `evolution_rules.json` (item/trade/friendship rules are defined but not yet implemented).
- Battle transcripts and animations are rendered dynamically in real-time on the overlay UI.

# Downloaded Pokémon Data

This project includes a data-downloading workflow for PokémonDB assets.

## Generated Sprite Images

The sprite downloader saves Gen 1 Pokémon colored sprites using Gen 6 artwork from PokémonDB. Files are written to:

`image_data/images/pokemon`

Filename format:
- `001_Bulbasaur.png`
- `002_Ivysaur.png`
- `003_Venusaur.png`

Run the sprite downloader with:
```powershell
python .\image_data\download_sprites.py
```

## Animated GIF Sprites

The GIF downloader saves Gen 6 animated sprites from Pokémon Showdown to:

`image_data/gif`

Filename format:
- `001_Bulbasaur.gif`
- `002_Ivysaur.gif`
- `003_Venusaur.gif`

Run the GIF downloader with:
```powershell
python .\image_data\download_gifs.py
```

## Grayscale Silhouette Images

The silhouette generator converts the downloaded colored images into solid gray silhouettes to use for unrevealed spawn animations in the overlay. Files are written to:

`image_data/grey_images`

Run the silhouette generator with:
```powershell
python .\image_data\generate_grey_images.py
```

## Base Stats JSON

The base stats downloader creates one JSON file containing the Gen 1 roster and their stats from PokémonDB. The file is written to:

`image_data/pokemon_base_stats.json`

Each Pokémon entry includes:
- `name`
- `base_stats` with `hp`, `attack`, `defense`, `sp_atk`, `sp_def`, `speed`, and `total`
- `catch_rate`
- `image_file`

Run the stats downloader with:
```powershell
python .\image_data\download_base_stats.py
```

## Game Engine Data Source

`src/game_engine.py` loads its default creature roster from `image_data/pokemon_base_stats.json` instead of using a hard-coded list.

If you regenerate the JSON file, rerun the game or rebuild the executable so it picks up the updated data.
