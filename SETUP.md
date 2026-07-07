# Pokémon Chat Game - Streamer Setup Guide

This guide helps you set up and run the Pokémon Chat Game on your local stream using Streamer.bot and OBS.

---

## 1. Download and Extract

1. Go to the GitHub repository's **Releases** page.
2. Download the latest `PokemonChatGame.zip` asset.
3. Extract the contents of the zip file to any directory on your computer (e.g., `C:\Games\PokemonChatGame`).

---

## 2. Initialize the Database

1. Open the extracted folder.
2. Open the `GameEngine` directory.
3. Run `GameEngine.exe` once by double-clicking it.
   - *This will auto-create the local SQLite database (`Data/game.db`), config files, and logs.*
   - You can close the command prompt window after it completes.

---

## 3. Configure Streamer.bot Action Paths

To let Streamer.bot execute the game CLI commands, follow these steps:

1. Open **Streamer.bot**.
2. Click **Import** (top left).
3. Open the `Streamerbot` folder in your extracted game directory.
4. Drag and drop `import_actions.txt` (or copy its contents) into the **Import String** box in Streamer.bot, then click **Import**.
5. Go to the **Settings** tab in Streamer.bot -> **Globals**.
6. Create a new **Global Variable**:
   - **Name**: `pokemonGamePath`
   - **Value**: The absolute path of the folder where you extracted the game (e.g., `C:\Games\PokemonChatGame` or `D:\Code\pokemon\Pokemon ChatGame`).
   - *Note: Do not add a trailing slash or quote marks.*

If you do not set this variable, the script will attempt to search for `GameEngine.exe` in the folder where Streamer.bot is running or in common subfolders.

---

## 4. Set Up the OBS Overlay

1. Open **OBS Studio**.
2. In your active scene, add a new **Browser Source**.
3. Check the box for **Local File**.
4. Click **Browse** and select `Overlay/index.html` from the extracted folder.
5. Recommended settings:
   - **Width**: `1920` (or your canvas width)
   - **Height**: `1080` (or your canvas height)
6. Ensure the OBS option **"Local File"** is enabled so the browser source can read the JSON state files from disk.

---

## 5. Enable Commands

Now go to the **Commands** tab in Streamer.bot and ensure that the following commands are enabled:

| Chat Command | Streamer.bot Action | Description |
| --- | --- | --- |
| `!spawn` | Spawn Wild Pokémon | Manually spawn a wild Pokémon (cooldown enforced) |
| `!catch` | Catch Spawned Pokémon | Attempt to catch the active wild Pokémon |
| `!inventory` or `!pokedex` | List Collection | Lists Pokémon in your collection (sends image to Discord if webhook is set) |
| `!stats <pokemon>` | View Stats Card | View detailed ELO, record, traits, and stats (also routes to Discord webhook) |
| `!battle @user <pokemon>` | Challenge User | Challenge another user in chat with your selected Pokémon |
| `!accept @user <pokemon>` | Accept Challenge | Accept a pending battle challenge and start the battle |
| `!bag` | View Bag Items | Displays all evolutionary stones and held items in your inventory |
| `!use <item_name> <pid>` | Use Stone/Item | Evolves a Level 10+ Pokémon by consuming the specified item from your bag |
| `!trade @user <pid>` | Propose Trade | Propose trading one of your Pokémon (by PID) to another user |
| `!accepttrade @user <pid>` | Accept Trade Swaps | Accept a pending trade from another user and swap ownership, triggering trade evolutions |
| `!leaderboard` | Show Leaderboard | Displays the top 10 players and top 10 Pokémon by ELO |

Enjoy streaming your new Pokémon Chat Game!
