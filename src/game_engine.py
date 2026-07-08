"""Game engine implementation for Pokemon ChatGame.

Contains database migration, inventory, battle, and spawn commands."""

import argparse
import json
import logging
import os
import random
import re
import sqlite3
import sys
import time

VERSION = "1.0.5"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from type_chart import get_type_multiplier

DEFAULT_SETTINGS = {
    # How often a new wild spawn can appear, in seconds.
    "spawn_interval_seconds": 3,
    # How long a spawn stays catchable before timing out, in seconds.
    "catch_timeout_seconds": 120,
    # Base probability modifier used when attempting to catch a creature.
    "base_catch_rate": 0.35,
    # Maximum time allowed for an active battle, in seconds.
    "battle_timeout_seconds": 120,
    # Cooldown after a battle ends before the same user can start another battle, in seconds.
    "battle_cooldown_seconds": 6,
    # Cooldown before the same pair of users can rematch, in seconds.
    "rematch_cooldown_seconds": 3,
    # General cooldown between repeated user actions, in seconds.
    "cooldown_seconds": 5,
    # Maximum number of creatures a user can hold in inventory.
    "max_inventory_size": 151,
    # Maximum creature level allowed.
    "max_level": 500,
    # Chance for an attack to land as a critical hit.
    "crit_chance": 0.10,
    # Chance for an attack to miss completely.
    "miss_chance": 0.05,
    # Damage multiplier applied when a critical hit occurs.
    "crit_multiplier": 1.5,
    # Additional crit damage bonus when the attacker has the Berserk trait.
    "berserk_crit_bonus": 0.15,
    # Experience multiplier for winning battles when the Lucky trait is active.
    "lucky_xp_multiplier": 1.15,
    # Attack multiplier for creatures with the Brave trait.
    "trait_attack_multiplier": 1.10,
    # Defense multiplier for creatures with the Tank trait.
    "trait_defense_multiplier": 1.10,
    # Speed multiplier for creatures with the Swift trait.
    "trait_speed_multiplier": 1.10,
    # Minimum individual value (IV) that can be assigned to creature stats.
    "iv_min": 0,
    # Maximum individual value (IV) that can be assigned to creature stats.
    "iv_max": 15,
    # Default Elo rating assigned to new creatures.
    "default_elo": 1000,
    # Elo points gained by a creature when it wins a battle.
    "elo_win": 25,
    # Elo points lost by a creature when it loses a battle.
    "elo_loss": 20,
    # Minimum amount of damage any attack can deal.
    "min_battle_damage": 5,
    # Number of entries shown on the leaderboard.
    "leaderboard_size": 10,
    # Base experience awarded to the winner of a battle.
    "xp_winner_base": 50,
    # Additional winner XP per level.
    "xp_winner_level_mult": 5,
    # Base experience awarded to the loser of a battle.
    "xp_loser_base": 15,
    # Additional loser XP per level.
    "xp_loser_level_mult": 2,
    # Discord webhook URL for inventory command notifications.
    "discord_inventory_webhook_url": "",
    # Auto-spawn interval in seconds. Set to 0 to disable.
    "auto_spawn_interval_seconds": 120,
}

TRAITS = ["Brave", "Tank", "Swift", "Lucky", "Berserk"]

EVOLUTION_ITEMS = [
    "moon-stone", "water-stone", "thunder-stone", "fire-stone", "leaf-stone",
    "sun-stone", "black-augurite", "oval-stone", "electirizer", "magmarizer",
    "metal-coat", "kings-rock", "up-grade", "dubious-disc", "protector", "dragon-scale"
]

CREATURE_EMOJI = {
    "Electric": "⚡",
    "Grass": "🌿",
    "Fire": "🔥",
    "Water": "💧",
    "Normal": "⭐",
}


def get_image_data_dir() -> Path:
    """Get image data dir."""
    candidates = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "image_data")

    repo_base = Path(__file__).resolve().parent.parent
    candidates.append(repo_base / "image_data")
    candidates.append(Path(sys.argv[0]).resolve().parent / "image_data")
    candidates.append(Path.cwd() / "image_data")

    def find_up(start: Path) -> Optional[Path]:
        """Find up."""
        current = start.resolve()
        for _ in range(8):
            candidate = current / "image_data"
            if candidate.exists():
                return candidate
            if current.parent == current:
                break
            current = current.parent
        return None

    for start in [Path.cwd(), Path(sys.argv[0]).resolve().parent, repo_base]:
        found = find_up(start)
        if found:
            return found

    for candidate in candidates:
        if (candidate / "pokemon_base_stats.json").exists():
            return candidate

    return candidates[0]


IMAGE_DATA_DIR = get_image_data_dir()
POKEMON_STATS_FILE = IMAGE_DATA_DIR / "pokemon_base_stats.json"

EVOLUTION_RULES_FILE = IMAGE_DATA_DIR / "evolution_rules.json"



def load_default_creatures() -> list[dict]:
    """Load default creatures."""
    if not POKEMON_STATS_FILE.exists():
        raise FileNotFoundError(f"Missing stats file: {POKEMON_STATS_FILE}")

    payload = json.loads(POKEMON_STATS_FILE.read_text(encoding="utf-8-sig"))
    pokemon = payload.get("pokemon", {})

    creatures: list[dict] = []
    for key, entry in pokemon.items():
        base_stats = entry.get("base_stats", {})
        catch_rate = entry.get("catch_rate", {})
        species_id = 0
        if isinstance(key, str) and "_" in key:
            prefix = key.split("_", 1)[0]
            if prefix.isdigit():
                species_id = int(prefix)
        creatures.append(
            {
                "name": entry.get("name", ""),
                "species_id": species_id,
                "base_hp": int(base_stats.get("hp", 0)),
                "base_attack": int(base_stats.get("attack", 0)),
                "base_defense": int(base_stats.get("defense", 0)),
                "base_speed": int(base_stats.get("speed", 0)),
                "base_sp_atk": int(base_stats.get("sp_atk", 0)),
                "base_sp_def": int(base_stats.get("sp_def", 0)),
                "types": entry.get("types", []),
                "catch_rate_mod": float(catch_rate.get("value", 100)),
            }
        )
    return creatures


DEFAULT_CREATURES = load_default_creatures()

SPECIES_ID_BY_NAME = {c["name"].strip().lower(): c.get("species_id", 0) for c in DEFAULT_CREATURES}

USERNAME_RE = re.compile(r"[^a-zA-Z0-9_]")


@dataclass
class Paths:
    """Paths holds related game data and behavior."""
    root: Path
    data_dir: Path
    config_dir: Path
    logs_dir: Path
    assets_dir: Path
    overlay_dir: Path
    streamerbot_dir: Path
    game_db: Path
    active_spawn_json: Path
    users_cache_json: Path
    overlay_state_json: Path
    settings_json: Path
    log_file: Path
    cmd_log_file: Path
    stdout_log: Path


@dataclass
class BattlePokemon:
    """BattlePokemon holds related game data and behavior."""
    inv_id: str
    owner: str
    name: str
    level: int
    xp: int
    trait: str
    elo: int
    wins: int
    losses: int
    hp_iv: int
    atk_iv: int
    def_iv: int
    spd_iv: int
    base_hp: int
    base_attack: int
    base_defense: int
    base_speed: int
    base_sp_atk: int
    base_sp_def: int
    types: List[str]
    creature_id: int

    @property
    def derived_hp(self) -> int:
        """Derived hp."""
        return compute_derived_hp(self.base_hp, self.level, self.hp_iv)

    def derived_stats(self, settings: Dict[str, Any]) -> Tuple[int, int, int]:
        """Derived stats."""
        return compute_derived_stats(
            self.base_attack,
            self.base_defense,
            self.base_speed,
            self.level,
            self.atk_iv,
            self.def_iv,
            self.spd_iv,
            self.trait,
            settings,
        )


def find_root() -> Path:
    """Find root."""
    env_root = os.environ.get("CHATGAME_ROOT")
    if env_root:
        return Path(env_root).resolve()

    probe = Path(sys.argv[0]).resolve()
    candidates = [probe, Path.cwd().resolve(), Path(__file__).resolve()]

    for candidate in candidates:
        current = candidate
        for _ in range(6):
            if (current / "Data").exists() and (current / "Config").exists():
                return current
            if current.parent == current:
                break
            current = current.parent

    return Path.cwd().resolve()


def build_paths(root: Path) -> Paths:
    """Build paths."""
    data_dir = root / "Data"
    config_dir = root / "Config"
    logs_dir = root / "Logs"
    assets_dir = root / "Assets"
    overlay_dir = root / "Overlay"
    streamerbot_dir = root / "Streamerbot"
    return Paths(
        root=root,
        data_dir=data_dir,
        config_dir=config_dir,
        logs_dir=logs_dir,
        assets_dir=assets_dir,
        overlay_dir=overlay_dir,
        streamerbot_dir=streamerbot_dir,
        game_db=data_dir / "game.db",
        active_spawn_json=data_dir / "active_spawn.json",
        users_cache_json=data_dir / "users_cache.json",
        overlay_state_json=data_dir / "overlay_state.json",
        settings_json=config_dir / "settings.json",
        log_file=logs_dir / "game.log",
        cmd_log_file=logs_dir / "cmd.log",
        stdout_log=logs_dir / "stdout.log",
    )


def ensure_dirs(paths: Paths) -> None:
    """Ensure dirs."""
    for directory in [
        paths.root,
        paths.data_dir,
        paths.config_dir,
        paths.logs_dir,
        paths.assets_dir,
        paths.overlay_dir,
        paths.streamerbot_dir,
        paths.assets_dir / "creatures",
        paths.assets_dir / "icons",
        paths.assets_dir / "sounds",
    ]:
        directory.mkdir(parents=True, exist_ok=True)


STREAMERBOT_SETTING_OVERRIDES = {
    "spawn_interval_seconds": int,
    "catch_timeout_seconds": int,
    "battle_cooldown_seconds": int,
    "rematch_cooldown_seconds": int,
    "cooldown_seconds": int,
    "auto_spawn_interval_seconds": int,
}


def _try_parse_streamerbot_setting(key: str, value: Any) -> Optional[Any]:
    """Parse a Streamerbot override value for a setting."""
    caster = STREAMERBOT_SETTING_OVERRIDES.get(key)
    if caster is None:
        return None

    try:
        if isinstance(value, str):
            value = value.strip()
        return caster(value)
    except (TypeError, ValueError):
        return None


def _get_streamerbot_overrides() -> Dict[str, Any]:
    """Load selected Streamerbot globals from environment variables."""
    overrides: Dict[str, Any] = {}
    for key in STREAMERBOT_SETTING_OVERRIDES:
        env_keys = [
            f"STREAMERBOT_{key.upper()}",
            f"CHATGAME_{key.upper()}",
            key.upper(),
        ]
        for env_key in env_keys:
            raw_value = os.environ.get(env_key)
            if raw_value is None:
                continue
            parsed_value = _try_parse_streamerbot_setting(key, raw_value)
            if parsed_value is not None:
                overrides[key] = parsed_value
            break
    return overrides


def _get_discord_webhook_override() -> Dict[str, Any]:
    """Load Discord webhook override from environment variables."""
    env_keys = [
        "DISCORD_INVENTORY_WEBHOOK_URL",
        "CHATGAME_DISCORD_INVENTORY_WEBHOOK_URL",
    ]
    for env_key in env_keys:
        raw_value = os.environ.get(env_key)
        if raw_value is not None:
            return {"discord_inventory_webhook_url": raw_value.strip()}
    return {}


def load_settings(paths: Paths) -> Dict[str, Any]:
    """Load settings."""
    settings = dict(DEFAULT_SETTINGS)

    if not paths.settings_json.exists():
        write_json(paths.settings_json, settings)
        settings.update(_get_discord_webhook_override())
        return settings

    data = None
    for attempt in range(5):
        try:
            data = read_json(paths.settings_json)
            break
        except Exception as e:
            if attempt == 4:
                raise RuntimeError(
                    f"Fatal: Could not read settings file {paths.settings_json} after retries: {e}"
                )
            time.sleep(0.1)

    if data is None:
        data = {}

    settings.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    
    try:
        write_json(paths.settings_json, settings)
    except Exception as e:
        logging.warning(f"Could not write to settings.json: {e}")

    settings.update(_get_discord_webhook_override())
    return settings


def setup_logging(paths: Paths) -> None:
    """Setup logging."""
    from logging.handlers import TimedRotatingFileHandler
    
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Weekly rotation (rotates on Monday 'W0', keeping 1 backup)
    game_handler = TimedRotatingFileHandler(
        paths.log_file, when="W0", interval=1, backupCount=1, encoding="utf-8"
    )
    game_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    
    logging.basicConfig(
        level=logging.INFO,
        handlers=[game_handler],
    )
    
    cmd_logger = logging.getLogger("cmd")
    cmd_logger.setLevel(logging.INFO)
    cmd_logger.propagate = False
    
    cmd_handler = TimedRotatingFileHandler(
        paths.cmd_log_file, when="W0", interval=1, backupCount=1, encoding="utf-8"
    )
    cmd_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    cmd_logger.addHandler(cmd_handler)


def read_json(path: Path) -> Any:
    """Read json."""
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    """Write json."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    tmp_path.replace(path)


def now_ts() -> int:
    """Now ts."""
    return int(time.time())


def normalize_username(username: str) -> str:
    """Normalize username."""
    cleaned = USERNAME_RE.sub("", username.strip())
    return cleaned.lower()


def connect_db(paths: Paths) -> sqlite3.Connection:
    """Connect db."""
    conn = sqlite3.connect(paths.game_db)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def db_session(paths: Paths):
    """Db session."""
    conn = connect_db(paths)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Internal helper to table columns."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def migrate_db(conn: sqlite3.Connection) -> None:
    """Migrate db."""
    user_cols = _table_columns(conn, "users")
    if "elo" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN elo INTEGER NOT NULL DEFAULT 1000")

    creature_cols = _table_columns(conn, "creatures")
    if "base_speed" not in creature_cols:
        conn.execute("ALTER TABLE creatures ADD COLUMN base_speed INTEGER NOT NULL DEFAULT 0")
    if "base_sp_atk" not in creature_cols:
        conn.execute("ALTER TABLE creatures ADD COLUMN base_sp_atk INTEGER NOT NULL DEFAULT 0")
    if "base_sp_def" not in creature_cols:
        conn.execute("ALTER TABLE creatures ADD COLUMN base_sp_def INTEGER NOT NULL DEFAULT 0")
    if "types" not in creature_cols:
        conn.execute("ALTER TABLE creatures ADD COLUMN types TEXT DEFAULT ''")
    if "species_id" not in creature_cols:
        conn.execute("ALTER TABLE creatures ADD COLUMN species_id INTEGER NOT NULL DEFAULT 0")

    inventory_cols = _table_columns(conn, "inventory")
    # If an old `current_hp` column exists (legacy), remove it by recreating the table
    if "current_hp" in inventory_cols:
        # Recreate inventory table without current_hp while preserving data
        conn.execute("PRAGMA foreign_keys=OFF;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory_new (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            creature_id INTEGER NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            xp INTEGER NOT NULL DEFAULT 0,
            obtained_at INTEGER NOT NULL,
            wins INTEGER NOT NULL DEFAULT 0,
            losses INTEGER NOT NULL DEFAULT 0,
            hp_iv INTEGER NOT NULL DEFAULT 0,
            atk_iv INTEGER NOT NULL DEFAULT 0,
            def_iv INTEGER NOT NULL DEFAULT 0,
            spd_iv INTEGER NOT NULL DEFAULT 0,
            trait TEXT NOT NULL DEFAULT 'Brave',
            elo INTEGER NOT NULL DEFAULT 1000,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(creature_id) REFERENCES creatures(id) ON DELETE CASCADE
            )
            """
        )
        # copy all columns except current_hp
        copy_cols = [c for c in inventory_cols if c != "current_hp"]
        copy_cols_sorted = ", ".join(copy_cols)
        conn.execute(f"INSERT INTO inventory_new ({copy_cols_sorted}) SELECT {copy_cols_sorted} FROM inventory")
        conn.execute("DROP TABLE inventory")
        conn.execute("ALTER TABLE inventory_new RENAME TO inventory")
        conn.execute("PRAGMA foreign_keys=ON;")
        inventory_cols = _table_columns(conn, "inventory")
    if "exp" in inventory_cols and "xp" not in inventory_cols:
        conn.execute("ALTER TABLE inventory RENAME COLUMN exp TO xp")
        inventory_cols = _table_columns(conn, "inventory")

    inventory_additions = {
        "username": "TEXT NOT NULL DEFAULT ''",
        "wins": "INTEGER NOT NULL DEFAULT 0",
        "losses": "INTEGER NOT NULL DEFAULT 0",
        "hp_iv": "INTEGER NOT NULL DEFAULT 0",
        "atk_iv": "INTEGER NOT NULL DEFAULT 0",
        "def_iv": "INTEGER NOT NULL DEFAULT 0",
        "spd_iv": "INTEGER NOT NULL DEFAULT 0",
        "trait": "TEXT",
        "elo": "INTEGER NOT NULL DEFAULT 1000",
    }
    trait_column_added = False
    for col, definition in inventory_additions.items():
        if col not in inventory_cols:
            conn.execute(f"ALTER TABLE inventory ADD COLUMN {col} {definition}")
            if col == "trait":
                trait_column_added = True
            inventory_cols.add(col)

    if trait_column_added:
        rows = conn.execute("SELECT id FROM inventory").fetchall()
        for row in rows:
            trait = random.choice(TRAITS)
            conn.execute("UPDATE inventory SET trait = ? WHERE id = ?", (trait, row[0]))
    else:
        rows = conn.execute(
            "SELECT id FROM inventory WHERE trait IS NULL OR trait = ''"
        ).fetchall()
        for row in rows:
            trait = random.choice(TRAITS)
            conn.execute("UPDATE inventory SET trait = ? WHERE id = ?", (trait, row[0]))

    conn.execute(
        """
        UPDATE inventory SET username = (
            SELECT username FROM users WHERE users.id = inventory.user_id
        ) WHERE username = ''
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenger_id INTEGER NOT NULL,
            challenged_id INTEGER NOT NULL,
            challenger_inventory_id TEXT NOT NULL,
            challenged_inventory_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY(challenger_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(challenged_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(challenger_inventory_id) REFERENCES inventory(id) ON DELETE CASCADE,
            FOREIGN KEY(challenged_inventory_id) REFERENCES inventory(id) ON DELETE CASCADE
        )
        """
    )

    speed_by_name = {c["name"]: c["base_speed"] for c in DEFAULT_CREATURES}
    sp_atk_by_name = {c["name"]: c.get("base_sp_atk", 0) for c in DEFAULT_CREATURES}
    sp_def_by_name = {c["name"]: c.get("base_sp_def", 0) for c in DEFAULT_CREATURES}
    types_by_name = {c["name"]: c.get("types", []) for c in DEFAULT_CREATURES}
    species_by_name = {c["name"]: c.get("species_id", 0) for c in DEFAULT_CREATURES}
    creature_rows = conn.execute("SELECT id, name FROM creatures").fetchall()
    for creature_id, name in creature_rows:
        speed = speed_by_name.get(name, 0)
        conn.execute("UPDATE creatures SET base_speed = ? WHERE id = ?", (speed, creature_id))
        conn.execute("UPDATE creatures SET base_sp_atk = ? WHERE id = ?", (sp_atk_by_name.get(name, 0), creature_id))
        conn.execute("UPDATE creatures SET base_sp_def = ? WHERE id = ?", (sp_def_by_name.get(name, 0), creature_id))
        conn.execute("UPDATE creatures SET species_id = ? WHERE id = ?", (species_by_name.get(name, 0), creature_id))
        # store types as JSON text
        types_val = json.dumps(types_by_name.get(name, []), ensure_ascii=False)
        conn.execute("UPDATE creatures SET types = ? WHERE id = ?", (types_val, creature_id))

    # Migration: Pre-populate pokedex from current inventory
    conn.execute(
        """
        INSERT OR IGNORE INTO pokedex (user_id, creature_id)
        SELECT DISTINCT user_id, creature_id FROM inventory
        """
    )


def init_db(paths: Paths) -> None:
    """Init db."""
    conn = connect_db(paths)
    try:
        with conn:
            # Check and Migrate inventory schema from INTEGER to TEXT PID if necessary
            table_check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventory'").fetchone()
            if table_check:
                cursor = conn.execute("PRAGMA table_info(inventory)")
                columns = cursor.fetchall()
                id_col = next((col for col in columns if col[1] == "id"), None)
                if id_col and id_col[2].upper() == "INTEGER":
                    logging.info("Migrating inventory table to support TEXT PIDs (prefixed with 'P')")
                    # 1. Rename existing inventory table
                    conn.execute("ALTER TABLE inventory RENAME TO inventory_old")
                    
                    # 2. Create new inventory table with TEXT id
                    conn.execute(
                        """
                        CREATE TABLE inventory (
                        id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        username TEXT NOT NULL DEFAULT '',
                        creature_id INTEGER NOT NULL,
                        level INTEGER NOT NULL DEFAULT 1,
                        xp INTEGER NOT NULL DEFAULT 0,
                        obtained_at INTEGER NOT NULL,
                        wins INTEGER NOT NULL DEFAULT 0,
                        losses INTEGER NOT NULL DEFAULT 0,
                        hp_iv INTEGER NOT NULL DEFAULT 0,
                        atk_iv INTEGER NOT NULL DEFAULT 0,
                        def_iv INTEGER NOT NULL DEFAULT 0,
                        spd_iv INTEGER NOT NULL DEFAULT 0,
                        trait TEXT NOT NULL DEFAULT 'Brave',
                        elo INTEGER NOT NULL DEFAULT 1000,
                        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY(creature_id) REFERENCES creatures(id) ON DELETE CASCADE
                        )
                        """
                    )
                    
                    # 3. Transfer data with 'P' prefix
                    conn.execute(
                        """
                        INSERT INTO inventory (
                            id, user_id, username, creature_id, level, xp, obtained_at,
                            wins, losses, hp_iv, atk_iv, def_iv, spd_iv, trait, elo
                        )
                        SELECT
                            'P' || CAST(id AS TEXT), user_id, username, creature_id, level, xp, obtained_at,
                            wins, losses, hp_iv, atk_iv, def_iv, spd_iv, trait, elo
                        FROM inventory_old
                        """
                    )
                    
                    # 4. Drop the old table
                    conn.execute("DROP TABLE inventory_old")
                    
                    # 5. Migrate pending_trades table if exists
                    trades_check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_trades'").fetchone()
                    if trades_check:
                        conn.execute("ALTER TABLE pending_trades RENAME TO pending_trades_old")
                        conn.execute(
                            """
                            CREATE TABLE pending_trades (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sender_id INTEGER NOT NULL,
                            receiver_id INTEGER NOT NULL,
                            sender_inventory_id TEXT NOT NULL,
                            created_at INTEGER NOT NULL,
                            expires_at INTEGER NOT NULL,
                            FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
                            FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE
                            )
                            """
                        )
                        conn.execute(
                            """
                            INSERT INTO pending_trades (id, sender_id, receiver_id, sender_inventory_id, created_at, expires_at)
                            SELECT id, sender_id, receiver_id, 'P' || CAST(sender_inventory_id AS TEXT), created_at, expires_at
                            FROM pending_trades_old
                            """
                        )
                        conn.execute("DROP TABLE pending_trades_old")

                    # 6. Migrate pending_battles table if exists
                    battles_check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_battles'").fetchone()
                    if battles_check:
                        cursor = conn.execute("PRAGMA table_info(pending_battles)")
                        columns = cursor.fetchall()
                        chal_col = next((col for col in columns if col[1] == "challenger_inventory_id"), None)
                        if chal_col and chal_col[2].upper() == "INTEGER":
                            logging.info("Migrating pending_battles table to support TEXT challenger_inventory_id")
                            conn.execute("ALTER TABLE pending_battles RENAME TO pending_battles_old")
                            conn.execute(
                                """
                                CREATE TABLE pending_battles (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    challenger_id INTEGER NOT NULL,
                                    challenged_id INTEGER NOT NULL,
                                    challenger_inventory_id TEXT NOT NULL,
                                    challenged_inventory_id TEXT,
                                    status TEXT NOT NULL DEFAULT 'pending',
                                    created_at INTEGER NOT NULL,
                                    expires_at INTEGER NOT NULL,
                                    FOREIGN KEY(challenger_id) REFERENCES users(id) ON DELETE CASCADE,
                                    FOREIGN KEY(challenged_id) REFERENCES users(id) ON DELETE CASCADE,
                                    FOREIGN KEY(challenger_inventory_id) REFERENCES inventory(id) ON DELETE CASCADE,
                                    FOREIGN KEY(challenged_inventory_id) REFERENCES inventory(id) ON DELETE CASCADE
                                )
                                """
                            )
                            conn.execute(
                                """
                                INSERT INTO pending_battles (
                                    id, challenger_id, challenged_id, challenger_inventory_id,
                                    challenged_inventory_id, status, created_at, expires_at
                                )
                                SELECT
                                    id, challenger_id, challenged_id,
                                    'P' || CAST(challenger_inventory_id AS TEXT),
                                    CASE WHEN challenged_inventory_id IS NOT NULL THEN 'P' || CAST(challenged_inventory_id AS TEXT) ELSE NULL END,
                                    status, created_at, expires_at
                                FROM pending_battles_old
                                """
                            )
                            conn.execute("DROP TABLE pending_battles_old")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                created_at INTEGER NOT NULL,
                last_catch_at INTEGER,
                last_battle_at INTEGER,
                elo INTEGER NOT NULL DEFAULT 1000
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS creatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                species_id INTEGER NOT NULL DEFAULT 0,
                name TEXT UNIQUE NOT NULL,
                base_hp INTEGER NOT NULL,
                base_attack INTEGER NOT NULL,
                base_defense INTEGER NOT NULL,
                base_speed INTEGER NOT NULL DEFAULT 0,
                catch_rate_mod REAL NOT NULL DEFAULT 1.0,
                created_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL DEFAULT '',
                creature_id INTEGER NOT NULL,
                level INTEGER NOT NULL DEFAULT 1,
                xp INTEGER NOT NULL DEFAULT 0,
                obtained_at INTEGER NOT NULL,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                hp_iv INTEGER NOT NULL DEFAULT 0,
                atk_iv INTEGER NOT NULL DEFAULT 0,
                def_iv INTEGER NOT NULL DEFAULT 0,
                spd_iv INTEGER NOT NULL DEFAULT 0,
                trait TEXT NOT NULL DEFAULT 'Brave',
                elo INTEGER NOT NULL DEFAULT 1000,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(creature_id) REFERENCES creatures(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER NOT NULL,
                user2_id INTEGER NOT NULL,
                winner_id INTEGER NOT NULL,
                log_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(user1_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(user2_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(winner_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pokedex (
                user_id INTEGER NOT NULL,
                creature_id INTEGER NOT NULL,
                PRIMARY KEY(user_id, creature_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(creature_id) REFERENCES creatures(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bag (
                user_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(user_id, item_name),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                sender_inventory_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(sender_inventory_id) REFERENCES inventory(id) ON DELETE CASCADE
                )
                """
            )
            migrate_db(conn)
    finally:
        conn.close()


def seed_creatures(paths: Paths) -> None:
    """Seed creatures."""
    conn = connect_db(paths)
    try:
        with conn:
            row = conn.execute("SELECT COUNT(*) FROM creatures").fetchone()
            if row and row[0] > 0:
                return
            for creature in DEFAULT_CREATURES:
                conn.execute(
                    """
                    INSERT INTO creatures (species_id, name, base_hp, base_attack, base_defense, base_speed, base_sp_atk, base_sp_def, types, catch_rate_mod, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        creature.get("species_id", 0),
                        creature["name"],
                        creature["base_hp"],
                        creature["base_attack"],
                        creature["base_defense"],
                        creature["base_speed"],
                        creature.get("base_sp_atk", 0),
                        creature.get("base_sp_def", 0),
                        json.dumps(creature.get("types", []), ensure_ascii=False),
                        creature["catch_rate_mod"],
                        now_ts(),
                    ),
                )
    finally:
        conn.close()


def ensure_data_files(paths: Paths) -> None:
    """Ensure data files."""
    if not paths.active_spawn_json.exists():
        write_json(paths.active_spawn_json, {})
    if not paths.users_cache_json.exists():
        write_json(paths.users_cache_json, {})
    if not paths.overlay_state_json.exists():
        write_json(
            paths.overlay_state_json,
            {
                "state": "idle",
                "message": "",
                "spawn": None,
                "timer": 0,
                "result": None,
                "updated_at": None,
            },
        )
    if not paths.stdout_log.exists():
        paths.stdout_log.write_text("", encoding="utf-8")


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Set setting."""
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_setting(conn: sqlite3.Connection, key: str) -> Optional[str]:
    """Get setting."""
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row[0]
    return None


def compute_derived_hp(base_hp: int, level: int, hp_iv: int) -> int:
    """Compute derived hp."""
    return base_hp + level * 3 + hp_iv


def compute_derived_stats(
    base_attack: int,
    base_defense: int,
    base_speed: int,
    level: int,
    atk_iv: int,
    def_iv: int,
    spd_iv: int,
    trait: str,
    settings: Dict[str, Any],
) -> Tuple[int, int, int]:
    """Compute derived stats."""
    attack = base_attack + level * 2 + atk_iv
    defense = base_defense + level * 2 + def_iv
    speed = base_speed + int(level * 1.5) + spd_iv

    if trait == "Brave":
        attack = int(attack * settings["trait_attack_multiplier"])
    if trait == "Tank":
        defense = int(defense * settings["trait_defense_multiplier"])
    if trait == "Swift":
        speed = int(speed * settings["trait_speed_multiplier"])

    return attack, defense, speed


def compute_derived_special_atk(base_sp_atk: int, level: int, atk_iv: int, trait: str, settings: Dict[str, Any]) -> int:
    val = base_sp_atk + level * 2 + atk_iv
    if trait == "Brave":
        val = int(val * settings["trait_attack_multiplier"])
    return val


def compute_derived_special_def(base_sp_def: int, level: int, def_iv: int, trait: str, settings: Dict[str, Any]) -> int:
    val = base_sp_def + level * 2 + def_iv
    if trait == "Tank":
        val = int(val * settings["trait_defense_multiplier"])
    return val


def creature_emoji(name: str) -> str:
    """Creature emoji."""
    name_lower = name.lower()
    if any(x in name_lower for x in ("pika", "volt", "elect", "jolt")):
        return CREATURE_EMOJI["Electric"]
    if any(x in name_lower for x in ("bulba", "ivy", "venus", "oddish", "bellsprout")):
        return CREATURE_EMOJI["Grass"]
    if any(x in name_lower for x in ("char", "growl", "ponyta", "magmar")):
        return CREATURE_EMOJI["Fire"]
    if any(x in name_lower for x in ("squirt", "wartort", "psyduck", "poli", "seel")):
        return CREATURE_EMOJI["Water"]
    return CREATURE_EMOJI["Normal"]


class GameEngine:
    """GameEngine holds related game data and behavior."""
    def __init__(self, paths: Paths, settings: Dict[str, Any], rng: Optional[random.Random] = None):
        """Initialize the game engine with paths, settings, and RNG."""
        self.paths = paths
        self.settings = settings
        self.rng = rng or random.Random()
        self._evolution_rules: Optional[Dict[str, Any]] = None

    def _load_evolution_rules(self) -> Dict[str, Any]:
        """Internal helper to load evolution rules."""
        if self._evolution_rules is not None:
            return self._evolution_rules
        if not EVOLUTION_RULES_FILE.exists():
            self._evolution_rules = {}
            return self._evolution_rules
        try:
            self._evolution_rules = json.loads(EVOLUTION_RULES_FILE.read_text(encoding="utf-8-sig"))
        except Exception:
            self._evolution_rules = {}
        return self._evolution_rules

    def _get_item_targets(self, item_name: str) -> List[str]:
        """Get names of pokemon that can be evolved by this item/stone."""
        rules = self._load_evolution_rules()
        targets = []
        for pokemon_name, rule_list in rules.items():
            for r in rule_list:
                if r.get("item") == item_name or r.get("held_item") == item_name:
                    targets.append(pokemon_name)
        return sorted(list(set(targets)))

    def _check_ready_to_evolve_prompt(self, conn: sqlite3.Connection, username: str) -> List[str]:
        """Check if user has level 10+ pokemon ready to evolve via item, return list of prompts."""
        prompts = []
        user_row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not user_row:
            return prompts
        user_id = user_row[0]
        
        # Fetch all inventory items
        rows = conn.execute(
            """
            SELECT inventory.id, creatures.name, inventory.level
            FROM inventory
            JOIN creatures ON creatures.id = inventory.creature_id
            WHERE inventory.user_id = ?
            """,
            (user_id,)
        ).fetchall()
        
        rules = self._load_evolution_rules()
        for inv_id, creature_name, level in rows:
            if level >= 10:
                species_rules = rules.get(creature_name, [])
                for r in species_rules:
                    if r.get("type") == "use-item":
                        item_name = r.get("item")
                        prompts.append(
                            f"💡 @{username}, your {creature_name} (PID: {inv_id}) is level {level} and ready to evolve! "
                            f"Use !use {item_name} {inv_id} if you have it."
                        )
                        break
        return prompts

    def _load_active_spawn(self) -> Dict[str, Any]:
        """Internal helper to load active spawn."""
        try:
            data = read_json(self.paths.active_spawn_json)
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        return data

    def _write_active_spawn(self, payload: Dict[str, Any]) -> None:
        """Internal helper to write active spawn."""
        write_json(self.paths.active_spawn_json, payload)

    def _write_overlay(self, payload: Dict[str, Any]) -> None:
        """Internal helper to write overlay."""
        payload = dict(payload)
        payload["updated_at"] = now_ts()
        write_json(self.paths.overlay_state_json, payload)

    def _check_for_updates(self) -> Optional[str]:
        """Check for updates on GitHub Releases, caching the result for 24 hours."""
        cache_file = self.paths.data_dir / "update_check.json"
        now = int(time.time())
        cached_ver = None
        needs_check = True

        if cache_file.exists():
            try:
                cache_data = read_json(cache_file)
                last_checked = cache_data.get("last_checked", 0)
                cached_ver = cache_data.get("latest_version")
                if now - last_checked < 86400:
                    needs_check = False
            except Exception:
                pass

        if not needs_check:
            if cached_ver:
                try:
                    c_parts = [int(x) for x in cached_ver.strip().lstrip("v").split(".")]
                    l_parts = [int(x) for x in VERSION.split(".")]
                    if c_parts > l_parts:
                        return cached_ver
                except Exception:
                    if cached_ver.strip().lstrip("v") != VERSION.strip().lstrip("v"):
                        return cached_ver
            return None

        # Perform update check
        latest_version = None
        try:
            url = "https://api.github.com/repos/tazod-yt/Pokemon-ChatGame/releases/latest"
            req = Request(url, headers={"User-Agent": "Pokemon-ChatGame-Updater"})
            with urlopen(req, timeout=1.5) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                latest_version = res_data.get("tag_name")
        except Exception:
            pass

        # If checker failed, keep cached_ver or use current VERSION to avoid hammering the API
        write_ver = latest_version if latest_version else (cached_ver if cached_ver else "v" + VERSION)
        try:
            write_json(cache_file, {"last_checked": now, "latest_version": write_ver})
        except Exception:
            pass

        if latest_version:
            try:
                c_parts = [int(x) for x in latest_version.strip().lstrip("v").split(".")]
                l_parts = [int(x) for x in VERSION.split(".")]
                if c_parts > l_parts:
                    return latest_version
            except Exception:
                if latest_version.strip().lstrip("v") != VERSION.strip().lstrip("v"):
                    return latest_version
        return None

    def _is_battle_active(self) -> bool:
        """Check if a battle is currently active on the overlay, including 10s post-battle buffer."""
        if not self.paths.overlay_state_json.exists():
            return False
        try:
            state = read_json(self.paths.overlay_state_json)
            if state and state.get("state") == "battle":
                expires_at = state.get("result", {}).get("expires_at", 0)
                if now_ts() < int(expires_at) + 10:
                    return True
        except Exception:
            pass
        return False

    def _mention(self, username: str) -> str:
        """Format a username with an @ prefix for chat output."""
        if not username:
            return username
        return f"@{username}"

    def _split_discord_messages(self, message: str, max_length: int = 2000) -> List[str]:
        """Split a long Discord message into chunks by whole lines without breaking a line."""
        lines = message.splitlines(keepends=True)
        if not lines:
            return [""]

        chunks: List[str] = [""]
        for line in lines:
            if len(chunks[-1]) + len(line) <= max_length:
                chunks[-1] += line
            else:
                if len(line) > max_length:
                    # A single line exceeds Discord's length limit; send it separately.
                    chunks.append(line)
                else:
                    chunks.append(line)
        return [chunk for chunk in chunks if chunk]

    def _generate_inventory_grid_image(self, username: str, owned_species: set) -> Path:
        """Generate a grid image showing the user's inventory collection."""
        from PIL import Image, ImageDraw, ImageFont
        import glob

        cols = 13
        rows_count = 12  # 13 * 12 = 156 slots (covers 1 to 151)
        cell_w, cell_h = 120, 160
        margin = 10
        item_w, item_h = cell_w - 2 * margin, 100  # 100x100 sprite area

        # Create a blank image with a dark background
        grid_img = Image.new("RGBA", (cols * cell_w, rows_count * cell_h), (0, 0, 0, 255))

        # Try to load a clean sans-serif system font with size 16
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font = ImageFont.load_default()

        # Build species ID to name lookup from default creatures database
        creature_name_by_id = {c.get("species_id", 0): c["name"] for c in DEFAULT_CREATURES if "species_id" in c}

        # Load and resize the pokeball image
        pokeball_path = IMAGE_DATA_DIR / "pokeball.png"
        if pokeball_path.exists():
            pokeball_base = Image.open(pokeball_path).convert("RGBA")
            pokeball_sprite = pokeball_base.resize((item_w, 100), Image.Resampling.LANCZOS)
        else:
            pokeball_sprite = None

        pokemon_images_dir = IMAGE_DATA_DIR / "images" / "pokemon"
        grey_images_dir = IMAGE_DATA_DIR / "grey_images"

        total_items = 151
        for idx in range(total_items):
            species_id = idx + 1
            col = idx % cols
            row = idx // cols

            # Centering offset for the last row if it's partially filled
            if row == rows_count - 1:
                last_row_count = total_items - (rows_count - 1) * cols
                row_offset_x = (cols * cell_w - last_row_count * cell_w) // 2
                cell_left = row_offset_x + col * cell_w
            else:
                cell_left = col * cell_w

            x = cell_left + margin
            y = row * cell_h + 26  # Offset sprite down to leave room for the name above

            if species_id in owned_species:
                # Load the sprite of the owned pokemon
                pattern = str(pokemon_images_dir / f"{species_id:03d}_*.png")
                matches = glob.glob(pattern)
                if matches:
                    sprite_path = Path(matches[0])
                    sprite_base = Image.open(sprite_path).convert("RGBA")
                    sprite = sprite_base.resize((item_w, 100), Image.Resampling.LANCZOS)
                    grid_img.paste(sprite, (x, y), sprite)
                elif pokeball_sprite:
                    grid_img.paste(pokeball_sprite, (x, y), pokeball_sprite)
            else:
                # Load the grey silhouette of the unowned pokemon
                pattern = str(grey_images_dir / f"{species_id:03d}_*.png")
                matches = glob.glob(pattern)
                if matches:
                    sprite_path = Path(matches[0])
                    sprite_base = Image.open(sprite_path).convert("RGBA")
                    sprite = sprite_base.resize((item_w, 100), Image.Resampling.LANCZOS)
                    grid_img.paste(sprite, (x, y), sprite)
                elif pokeball_sprite:
                    grid_img.paste(pokeball_sprite, (x, y), pokeball_sprite)

            draw = ImageDraw.Draw(grid_img)
            pokemon_name = creature_name_by_id.get(species_id, "Unknown")

            # 1. Draw the species name above the sprite
            try:
                left, top, right, bottom = draw.textbbox((0, 0), pokemon_name, font=font)
                name_w = right - left
            except AttributeError:
                try:
                    name_w = draw.textlength(pokemon_name, font=font)
                except AttributeError:
                    name_w = font.getsize(pokemon_name)[0]

            name_x = cell_left + cell_w // 2 - name_w // 2
            name_y = row * cell_h + 6

            if species_id in owned_species:
                name_color = (255, 255, 255, 255)  # White for owned names
            else:
                name_color = (120, 120, 120, 255)  # Gray for unowned names

            draw.text((name_x, name_y), pokemon_name, fill=name_color, font=font)

            # 2. Draw the species number below the sprite
            text = f"#{species_id:03d}"
            try:
                left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
                text_w = right - left
            except AttributeError:
                try:
                    text_w = draw.textlength(text, font=font)
                except AttributeError:
                    text_w = font.getsize(text)[0]

            text_x = cell_left + cell_w // 2 - text_w // 2
            text_y = row * cell_h + 134

            if species_id in owned_species:
                text_color = (255, 223, 0, 255)  # Gold for owned numbers
            else:
                text_color = (120, 120, 120, 255)  # Gray for unowned numbers

            draw.text((text_x, text_y), text, fill=text_color, font=font)

        # Save output image
        output_dir = self.paths.data_dir / "temp"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"inventory_{username}.png"
        grid_img.save(output_path, "PNG")
        return output_path

    def _send_discord_inventory_image_webhook(self, username: str, file_path: Path, stats_text: str = "") -> Optional[str]:
        """Send inventory grid image to Discord via configured webhook and return the message URL."""
        webhook_url = str(self.settings.get("discord_inventory_webhook_url", "") or "").strip()
        if not webhook_url:
            return None

        if "?" in webhook_url:
            if "wait=" not in webhook_url:
                webhook_url += "&wait=true"
        else:
            webhook_url += "?wait=true"

        import uuid
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"

        file_bytes = file_path.read_bytes()
        filename = file_path.name

        body = []

        # Add payload_json part
        body.append(f"--{boundary}".encode('utf-8'))
        body.append(b'Content-Disposition: form-data; name="payload_json"')
        body.append(b'Content-Type: application/json')
        body.append(b'')
        payload_content = f"**{username}'s Pokedex Collection**"
        if stats_text:
            payload_content += f"\n{stats_text}"
        payload_json = {
            "content": payload_content
        }
        body.append(json.dumps(payload_json).encode('utf-8'))

        # Add file part
        body.append(f"--{boundary}".encode('utf-8'))
        body.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode('utf-8'))
        body.append(b'Content-Type: image/png')
        body.append(b'')
        body.append(file_bytes)

        body.append(f"--{boundary}--".encode('utf-8'))

        payload = b'\r\n'.join(body)

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }

        request = Request(webhook_url, data=payload, headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read()
                if raw:
                    data = json.loads(raw.decode("utf-8"))
                    message_id = data.get("id")
                    channel_id = data.get("channel_id")
                    guild_id = data.get("guild_id")
                    if guild_id and channel_id and message_id:
                        return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
                    elif channel_id and message_id:
                        return f"https://discord.com/channels/@me/{channel_id}/{message_id}"
        except HTTPError as e:
            body_err = e.read().decode("utf-8", errors="replace") if e.fp is not None else ""
            logging.error("Failed to send Discord inventory image webhook: %s %s", e.code, body_err)
        except (URLError, OSError) as e:
            logging.error("Failed to send Discord inventory image webhook: %s", e)

        return None

    def _send_discord_stats_webhook(self, message: str) -> Optional[str]:
        """Send stats text to Discord via configured webhook and return the message URL."""
        webhook_url = str(self.settings.get("discord_inventory_webhook_url", "") or "").strip()
        if not webhook_url:
            return None

        if "?" in webhook_url:
            if "wait=" not in webhook_url:
                webhook_url += "&wait=true"
        else:
            webhook_url += "?wait=true"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }

        first_message_url: Optional[str] = None
        for segment in self._split_discord_messages(message):
            payload = json.dumps({"content": segment}).encode("utf-8")
            request = Request(webhook_url, data=payload, headers=headers)
            try:
                with urlopen(request, timeout=10) as response:
                    raw = response.read()
                    if not raw:
                        continue
                    data = json.loads(raw.decode("utf-8"))
                    message_id = data.get("id")
                    channel_id = data.get("channel_id")
                    guild_id = data.get("guild_id")
                    if not first_message_url:
                        if guild_id and channel_id and message_id:
                            first_message_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
                        elif channel_id and message_id:
                            first_message_url = f"https://discord.com/channels/@me/{channel_id}/{message_id}"
            except HTTPError as e:
                body = e.read().decode("utf-8", errors="replace") if e.fp is not None else ""
                logging.error("Failed to send Discord stats webhook: %s %s", e.code, body)
            except (URLError, OSError) as e:
                logging.error("Failed to send Discord stats webhook: %s", e)

        return first_message_url

    def _write_stdout_log(self, message: str) -> None:
        """Internal helper to write stdout log."""
        try:
            self.paths.stdout_log.parent.mkdir(parents=True, exist_ok=True)
            with self.paths.stdout_log.open("a", encoding="utf-8") as handle:
                handle.write(f"{message}\n")
        except Exception:
            logging.exception("Failed to write stdout log")

    def _respond(self, message: str) -> str:
        """Internal helper to respond."""
        self._write_stdout_log(message)
        try:
            update_ver = self._check_for_updates()
            if update_ver:
                message += f"\n[UPDATE_NOTIFICATION] {update_ver}"
        except Exception:
            pass
        return message

    def _spawn_is_expired(self, spawn: Dict[str, Any]) -> bool:
        """Internal helper to spawn is expired."""
        expires_at = spawn.get("expires_at")
        if not expires_at:
            return True
        return now_ts() >= int(expires_at)

    def _ensure_user(self, conn: sqlite3.Connection, username: str) -> int:
        """Internal helper to ensure user."""
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            return int(row[0])
        created_at = now_ts()
        conn.execute(
            "INSERT INTO users (username, created_at) VALUES (?, ?)",
            (username, created_at),
        )
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        return int(row[0])

    def _get_cooldown_remaining(self, last_time: Optional[int], cooldown_key: str) -> int:
        """Internal helper to get cooldown remaining."""
        if not last_time:
            return 0
        cooldown = int(self.settings[cooldown_key])
        remaining = cooldown - (now_ts() - int(last_time))
        return max(0, remaining)

    def _expire_pending_battles(self, conn: sqlite3.Connection) -> None:
        """Internal helper to expire pending battles."""
        now = now_ts()
        conn.execute(
            "UPDATE pending_battles SET status = 'expired' WHERE status = 'pending' AND expires_at < ?",
            (now,),
        )

    def _select_random_creature(self, conn: sqlite3.Connection) -> Tuple[int, Dict[str, Any]]:
        """Internal helper to select random creature."""
        rows = conn.execute(
            "SELECT id, name, base_hp, base_attack, base_defense, base_speed, base_sp_atk, base_sp_def, types, catch_rate_mod FROM creatures"
        ).fetchall()
        if not rows:
            raise RuntimeError("No creatures available")
        row = self.rng.choice(rows)
        return int(row[0]), {
            "name": row[1],
            "base_hp": int(row[2]),
            "base_attack": int(row[3]),
            "base_defense": int(row[4]),
            "base_speed": int(row[5]),
            "base_sp_atk": int(row[6]),
            "base_sp_def": int(row[7]),
            "types": json.loads(row[8]) if row[8] else [],
            "catch_rate_mod": float(row[9]),
        }

    def _random_trait(self) -> str:
        """Internal helper to random trait."""
        return self.rng.choice(TRAITS)

    def _random_iv(self) -> int:
        """Internal helper to random iv."""
        return self.rng.randint(int(self.settings["iv_min"]), int(self.settings["iv_max"]))

    def _generate_next_pid(self, conn: sqlite3.Connection) -> str:
        """Generate the next text PID prefixed with 'P'."""
        row = conn.execute("SELECT id FROM inventory").fetchall()
        max_id = 0
        for r in row:
            val = r[0]
            if isinstance(val, str) and val.lower().startswith("p"):
                try:
                    num = int(val[1:])
                    if num > max_id:
                        max_id = num
                except ValueError:
                    pass
        return f"P{max_id + 1}"

    def _resolve_inventory_pokemon(
        self,
        conn: sqlite3.Connection,
        user_id: int,
        selector: str,
    ) -> Optional[Tuple[Any, ...]]:
        """Internal helper to resolve inventory pokemon."""
        rows = conn.execute(
            """
            SELECT inventory.id, inventory.creature_id, creatures.name,
                     creatures.base_hp, creatures.base_attack, creatures.base_defense, creatures.base_speed,
                     creatures.base_sp_atk, creatures.base_sp_def, creatures.types,
                   inventory.level, inventory.xp, inventory.wins, inventory.losses,
                   inventory.hp_iv, inventory.atk_iv, inventory.def_iv, inventory.spd_iv,
                   inventory.trait, inventory.elo
            FROM inventory
            JOIN creatures ON creatures.id = inventory.creature_id
            WHERE inventory.user_id = ?
            ORDER BY inventory.obtained_at DESC
            """,
            (user_id,),
        ).fetchall()

        if not rows:
            return None

        selector = selector.strip()
        selector_lower = selector.lower()

        # Case 1: PID (e.g. P1)
        if selector_lower.startswith("p") and selector_lower[1:].isdigit():
            for row in rows:
                if row[0].lower() == selector_lower:
                    return row
            return None

        # Case 2: If numeric selector, treat it as a global creature id (creatures.id)
        if selector.isdigit():
            creature_id = int(selector)
            row = conn.execute(
                """
                SELECT inventory.id, inventory.creature_id, creatures.name,
                       creatures.base_hp, creatures.base_attack, creatures.base_defense, creatures.base_speed,
                       creatures.base_sp_atk, creatures.base_sp_def, creatures.types,
                       inventory.level, inventory.xp, inventory.wins, inventory.losses,
                       inventory.hp_iv, inventory.atk_iv, inventory.def_iv, inventory.spd_iv,
                       inventory.trait, inventory.elo
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                WHERE inventory.user_id = ? AND creatures.species_id = ?
                ORDER BY inventory.obtained_at DESC LIMIT 1
                """,
                (user_id, creature_id),
            ).fetchone()
            if row:
                return row
            return None

        for row in rows:
            if row[2].lower() == selector_lower:
                return row
        for row in rows:
            if selector_lower in row[2].lower():
                return row
        return None

    def _resolve_trade_pokemon(self, conn: sqlite3.Connection, user_id: int, username: str, selector: str) -> Union[Tuple[str, str], str]:
        """
        Resolves a selector (PID, name, or number) to a specific Pokémon from a user's inventory.
        Returns:
            Tuple[pid (str), pokemon_name (str)] on success.
            A string response message on validation failure/conflict.
        """
        selector = selector.strip()
        if not selector:
            return f"@{username}, you must specify a PID, Pokémon name, or number."

        # Case 1: PID
        if selector.lower().startswith("p") and selector[1:].isdigit():
            row = conn.execute(
                """
                SELECT inventory.id, creatures.name
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                WHERE inventory.id = ? AND inventory.user_id = ?
                """,
                (selector, user_id)
            ).fetchone()
            if not row:
                return f"@{username} does not own a Pokémon with PID {selector}."
            return (row[0], row[1])

        # Case 2: Pokémon number (species index) or name
        if selector.isdigit():
            creature_rows = conn.execute("SELECT id, name FROM creatures WHERE species_id = ?", (int(selector),)).fetchall()
        else:
            creature_rows = conn.execute("SELECT id, name FROM creatures WHERE LOWER(name) = ?", (selector.lower(),)).fetchall()
            if not creature_rows:
                # Try substring search if no exact match
                creature_rows = conn.execute("SELECT id, name FROM creatures WHERE LOWER(name) LIKE ?", (f"%{selector.lower()}%",)).fetchall()

        if not creature_rows:
            return f"@{username}, no wild Pokémon found matching '{selector}'."

        creature_ids = [r[0] for r in creature_rows]
        placeholders = ", ".join("?" for _ in creature_ids)
        inv_rows = conn.execute(
            f"""
            SELECT inventory.id, creatures.name
            FROM inventory
            JOIN creatures ON creatures.id = inventory.creature_id
            WHERE inventory.creature_id IN ({placeholders}) AND inventory.user_id = ?
            """,
            (*creature_ids, user_id)
        ).fetchall()

        if not inv_rows:
            display_name = creature_rows[0][1] if creature_rows else selector
            return f"@{username} does not own any {display_name}."

        if len(inv_rows) == 1:
            return (inv_rows[0][0], inv_rows[0][1])

        display_name = inv_rows[0][1]
        return f"@{username} you have more than 1 {display_name} use PID instead, !stats <pokemon_name/number> to get pid"

    def _load_battle_pokemon(self, row: Tuple[Any, ...], owner: str) -> BattlePokemon:
        """Internal helper to load battle pokemon."""
        return BattlePokemon(
            inv_id=str(row[0]),
            creature_id=int(row[1]),
            name=row[2],
            base_hp=int(row[3]),
            base_attack=int(row[4]),
            base_defense=int(row[5]),
            base_speed=int(row[6]),
            base_sp_atk=int(row[7]),
            base_sp_def=int(row[8]),
            types=json.loads(row[9]) if row[9] else [],
            level=int(row[10]),
            xp=int(row[11]),
            wins=int(row[12]),
            losses=int(row[13]),
            hp_iv=int(row[14]),
            atk_iv=int(row[15]),
            def_iv=int(row[16]),
            spd_iv=int(row[17]),
            trait=row[18],
            elo=int(row[19]),
            owner=owner,
        )

    def _get_rematch_cooldown_remaining(
        self, conn: sqlite3.Connection, user1_id: int, user2_id: int
    ) -> int:
        """Internal helper to get rematch cooldown remaining."""
        row = conn.execute(
            """
            SELECT created_at FROM battles
            WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)
            ORDER BY created_at DESC LIMIT 1
            """,
            (user1_id, user2_id, user2_id, user1_id),
        ).fetchone()
        if not row:
            return 0
        return self._get_cooldown_remaining(row[0], "rematch_cooldown_seconds")

    def spawn(self) -> str:
        """Spawn."""
        logging.info("Command: spawn")
        if self._is_battle_active():
            return self._respond("A battle is in progress. Please wait until it completes.")
        spawn = self._load_active_spawn()
        if spawn and not self._spawn_is_expired(spawn):
            return self._respond(f"Spawn already active: {spawn.get('name', 'Unknown')}")
        expired_name = None
        if spawn and self._spawn_is_expired(spawn):
            expired_name = spawn.get('name', 'Unknown')
            self._write_active_spawn({})
            self._write_overlay(
                {
                    "state": "idle",
                    "message": "",
                    "spawn": None,
                    "timer": 0,
                    "result": None,
                }
            )

        with db_session(self.paths) as conn:
            last_spawn_at = get_setting(conn, "last_spawn_at")
            if last_spawn_at:
                interval = int(self.settings["spawn_interval_seconds"])
                remaining = interval - (now_ts() - int(last_spawn_at))
                if remaining > 0:
                    if expired_name:
                        return self._respond(f"{expired_name} fled")
                    return self._respond(f"Spawn on cooldown. Try again in {remaining}s.")

            creature_id, creature = self._select_random_creature(conn)
            spawned_at = now_ts()
            expires_at = spawned_at + int(self.settings["catch_timeout_seconds"])
            spawn_payload = {
                "creature_id": creature_id,
                "name": creature["name"],
                "spawned_at": spawned_at,
                "expires_at": expires_at,
            }
            self._write_active_spawn(spawn_payload)
            set_setting(conn, "last_spawn_at", str(spawned_at))

        self._write_overlay(
            {
                "state": "spawn",
                "message": f"A wild {creature['name']} appeared!",
                "spawn": spawn_payload,
                "timer": int(self.settings["catch_timeout_seconds"]),
                "result": None,
            }
        )
        logging.info("Spawned creature: %s", creature["name"])
        return self._respond(f"wild {creature['name']} appeared")

    def auto_spawn(self) -> str:
        """Auto spawn on interval."""
        logging.info("Command: auto_spawn")
        if self._is_battle_active():
            logging.info("Skipping auto-spawn because a battle is active")
            return ""

        # Check if auto-spawn is enabled
        auto_spawn_interval = self.settings.get("auto_spawn_interval_seconds")
        if not auto_spawn_interval:
            logging.info("Auto-spawn disabled")
            return ""

        auto_spawn_interval = int(auto_spawn_interval)

        spawn = self._load_active_spawn()
        # If spawn active and not expired, don't spawn again
        if spawn and not self._spawn_is_expired(spawn):
            logging.info("Spawn already active, skipping auto-spawn")
            return ""

        # Clear expired spawn
        expired_name = None
        if spawn and self._spawn_is_expired(spawn):
            expired_name = spawn.get("name", "Unknown")
            self._write_active_spawn({})
            self._write_overlay(
                {
                    "state": "idle",
                    "message": "",
                    "spawn": None,
                    "timer": 0,
                    "result": None,
                }
            )

        with db_session(self.paths) as conn:
            last_auto_spawn_at = get_setting(conn, "last_auto_spawn_at")
            if last_auto_spawn_at:
                remaining = auto_spawn_interval - (now_ts() - int(last_auto_spawn_at))
                if remaining > 0:
                    logging.info("Auto-spawn on cooldown, %ds remaining", remaining)
                    if expired_name:
                        return self._respond(f"{expired_name} fled")
                    return ""

            # Time to spawn
            creature_id, creature = self._select_random_creature(conn)
            spawned_at = now_ts()
            expires_at = spawned_at + int(self.settings["catch_timeout_seconds"])
            spawn_payload = {
                "creature_id": creature_id,
                "name": creature["name"],
                "spawned_at": spawned_at,
                "expires_at": expires_at,
            }
            self._write_active_spawn(spawn_payload)
            set_setting(conn, "last_auto_spawn_at", str(spawned_at))

        self._write_overlay(
            {
                "state": "spawn",
                "message": f"A wild {creature['name']} appeared!",
                "spawn": spawn_payload,
                "timer": int(self.settings["catch_timeout_seconds"]),
                "result": None,
            }
        )
        logging.info("Auto-spawned creature: %s", creature["name"])
        if expired_name:
            return self._respond(f"{expired_name} fled\nwild {creature['name']} appeared")
        return self._respond(f"wild {creature['name']} appeared")

    def catch(self, username: str, ball_type: str = "pokeball") -> str:
        """Catch."""
        username = normalize_username(username)
        if not username:
            return self._respond("Invalid username.")

        logging.info("Command: catch %s using %s", username, ball_type)
        if self._is_battle_active():
            return self._respond("A battle is in progress. Please wait until it completes.")
        spawn = self._load_active_spawn()
        if spawn and self._spawn_is_expired(spawn):
            spawn_name = spawn.get("name", "Unknown")
            self._write_active_spawn({})
            self._write_overlay(
                {
                    "state": "idle",
                    "message": "",
                    "spawn": None,
                    "timer": 0,
                    "result": None,
                }
            )
            return self._respond(f"{spawn_name} fled")
        if not spawn:
            return self._respond("No active spawn to catch.")

        with db_session(self.paths) as conn:
            user_id = self._ensure_user(conn, username)
            last_catch_at = conn.execute(
                "SELECT last_catch_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()[0]
            remaining = self._get_cooldown_remaining(last_catch_at, "cooldown_seconds")
            if remaining > 0:
                return self._respond(f"{self._mention(username)} Catch cooldown active. Try again in {remaining}s.")

            inv_count = conn.execute(
                "SELECT COUNT(*) FROM inventory WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            if inv_count >= int(self.settings["max_inventory_size"]):
                return self._respond("Inventory full.")

            # Normalize ball type
            ball_type = ball_type.strip().lower()
            if ball_type in ["great", "great-ball"]:
                ball_name = "great-ball"
                ball_multiplier = 1.5
            elif ball_type in ["ultra", "ultra-ball"]:
                ball_name = "ultra-ball"
                ball_multiplier = 2.0
            else:
                ball_name = "pokeball"
                ball_multiplier = 1.0

            # If using a specialty ball, check and consume
            if ball_name != "pokeball":
                ball_row = conn.execute(
                    "SELECT quantity FROM bag WHERE user_id = ? AND item_name = ?",
                    (user_id, ball_name)
                ).fetchone()
                if not ball_row or int(ball_row[0]) <= 0:
                    return self._respond(f"@{username}, you do not have any {ball_name.replace('-', ' ')}s in your bag!")
                conn.execute(
                    "UPDATE bag SET quantity = quantity - 1 WHERE user_id = ? AND item_name = ?",
                    (user_id, ball_name)
                )

            creature_row = conn.execute(
                "SELECT base_hp, base_attack, base_defense, catch_rate_mod FROM creatures WHERE id = ?",
                (spawn.get("creature_id"),),
            ).fetchone()
            if not creature_row:
                return self._respond("Spawn creature missing.")

            catch_rate = (float(creature_row[3]) / 765) * ball_multiplier
            catch_rate = min(1.0, max(0.0, catch_rate))
            roll = self.rng.random()
            success = roll <= catch_rate
            now = now_ts()

            conn.execute(
                "UPDATE users SET last_catch_at = ? WHERE id = ?",
                (now, user_id),
            )

            if success:
                trait = self._random_trait()
                hp_iv = self._random_iv()
                atk_iv = self._random_iv()
                def_iv = self._random_iv()
                spd_iv = self._random_iv()
                pid = self._generate_next_pid(conn)
                conn.execute(
                    """
                    INSERT INTO inventory (
                        id, user_id, username, creature_id, level, xp, obtained_at,
                        wins, losses, hp_iv, atk_iv, def_iv, spd_iv, trait, elo
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        user_id,
                        username,
                        spawn["creature_id"],
                        1,
                        0,
                        now,
                        0,
                        0,
                        hp_iv,
                        atk_iv,
                        def_iv,
                        spd_iv,
                        trait,
                        int(self.settings["default_elo"]),
                    ),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO pokedex (user_id, creature_id) VALUES (?, ?)",
                    (user_id, spawn["creature_id"]),
                )
                self._write_active_spawn({})
                self._write_overlay(
                    {
                        "state": "catch_success",
                        "message": f"{username} caught {spawn.get('name')}!",
                        "spawn": spawn,
                        "timer": 0,
                        "result": "success",
                        "ball_type": ball_name,
                    }
                )
                logging.info("Catch success: %s caught %s", username, spawn.get("name"))
                success_msg = f"{self._mention(username)} caught {spawn.get('name')}! ({trait})"
                if ball_name != "pokeball":
                    ball_display = "Great Ball" if ball_name == "great-ball" else "Ultra Ball"
                    success_msg += f" using a {ball_display}!"
                
                prompts = self._check_ready_to_evolve_prompt(conn, username)
                if prompts:
                    success_msg += "\n" + "\n".join(prompts)
                return self._respond(success_msg)

            self._write_overlay(
                {
                    "state": "spawn",
                    "message": "",
                    "spawn": spawn,
                    "timer": max(0, int(spawn.get("expires_at", now)) - now),
                    "result": None,
                }
            )
            logging.info("Catch failed: %s vs %s", username, spawn.get("name"))
            return self._respond(f"{self._mention(username)} failed to catch {spawn.get('name')}.")

    def pokedex(self, username: str) -> str:
        """Pokedex."""
        username = normalize_username(username)
        if not username:
            return self._respond("Invalid username.")

        logging.info("Command: pokedex %s", username)
        with db_session(self.paths) as conn:
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not row:
                return self._respond(f"{self._mention(username)} has no creatures yet.")
            user_id = int(row[0])
            rows = conn.execute(
                """
                SELECT inventory.username, creatures.species_id, creatures.name, inventory.level, inventory.xp, inventory.trait,
                       inventory.elo, inventory.wins, inventory.losses,
                       creatures.base_hp, creatures.base_attack, creatures.base_defense, creatures.base_speed,
                       inventory.hp_iv, inventory.atk_iv, inventory.def_iv, inventory.spd_iv
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                WHERE inventory.user_id = ?
                ORDER BY inventory.obtained_at DESC
                """,
                (user_id,),
            ).fetchall()

            # Query pokedex table for all ever-owned species
            pokedex_rows = conn.execute(
                """
                SELECT creatures.species_id 
                FROM pokedex
                JOIN creatures ON creatures.id = pokedex.creature_id
                WHERE pokedex.user_id = ?
                """,
                (user_id,),
            ).fetchall()

        if not pokedex_rows:
            return self._respond(f"{self._mention(username)} has no creatures yet.")

        # Create image payload first
        owned_species = {p_row[0] for p_row in pokedex_rows if p_row[0]}
        
        # Calculate stats for Discord message
        total_owned = len(rows)
        unique_caught = len(owned_species)
        total_wins = sum(int(row[7]) for row in rows)
        total_losses = sum(int(row[8]) for row in rows)
        total_battles = total_wins + total_losses
        win_rate_str = f"{(total_wins / total_battles) * 100:.1f}%" if total_battles > 0 else "0.0%"
        
        stats_text = (
            f"📈 **Collection Progress:** {unique_caught}/151 Unique Species\n"
            f"🎒 **Total Owned:** {total_owned} Pokémon\n"
            f"⚔️ **Battle Record:** {total_wins} W - {total_losses} L ({win_rate_str} Win Rate)"
        )

        img_path = self._generate_inventory_grid_image(username, owned_species)
        webhook_link = self._send_discord_inventory_image_webhook(username, img_path, stats_text)

        # Cleanup temp file
        try:
            if img_path.exists():
                img_path.unlink()
        except Exception:
            logging.warning("Failed to remove temp inventory image: %s", img_path)

        if webhook_link:
            return self._respond(f"{self._mention(username)} here is your pokedex - {webhook_link}")

        # Fallback to text format if webhook fails or is unconfigured
        lines = [f"{username}'s Pokedex:"]
        for (_inventory_username, species_id, name, level, xp, trait, elo, wins, losses, base_hp, base_attack, base_defense, base_speed, hp_iv, atk_iv, def_iv, spd_iv) in rows:
            total_hp = int(base_hp) + int(hp_iv)
            total_atk = int(base_attack) + int(atk_iv)
            total_def = int(base_defense) + int(def_iv)
            total_spd = int(base_speed) + int(spd_iv)
            display_id = SPECIES_ID_BY_NAME.get((name or "").strip().lower(), species_id)
            lines.append(
                f"{display_id}. {name} (Lv {level}, XP {xp}, {trait}, ELO {elo}, W/L {wins}/{losses}) "
                f"HP {total_hp} ({base_hp}+{hp_iv}), ATK {total_atk} ({base_attack}+{atk_iv}), "
                f"DEF {total_def} ({base_defense}+{def_iv}), SPD {total_spd} ({base_speed}+{spd_iv})"
            )
        result = "\n".join(lines)
        return self._respond(result)

    def inventory(self, username: str) -> str:
        """Inventory (alias for pokedex)."""
        return self.pokedex(username)

    def stats(self, username: str, selector: str) -> str:
        """Get stats for all matching Pokémon of a user and send to Discord webhook."""
        username = normalize_username(username)
        if not username:
            return self._respond("Invalid username.")

        selector = selector.strip()
        if not selector:
            return self._respond("Specify a Pokémon name or number.")

        logging.info("Command: stats %s %s", username, selector)
        with db_session(self.paths) as conn:
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not row:
                return self._respond(f"{self._mention(username)} has no creatures yet.")
            user_id = int(row[0])

            # Fetch all creatures of the user first to do local filtering matching _resolve_inventory_pokemon style
            rows = conn.execute(
                """
                SELECT inventory.username, creatures.species_id, creatures.name, inventory.level, inventory.xp, inventory.trait,
                       inventory.elo, inventory.wins, inventory.losses,
                       creatures.base_hp, creatures.base_attack, creatures.base_defense, creatures.base_speed,
                       inventory.hp_iv, inventory.atk_iv, inventory.def_iv, inventory.spd_iv,
                       inventory.id
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                WHERE inventory.user_id = ?
                ORDER BY inventory.obtained_at DESC
                """,
                (user_id,),
            ).fetchall()

        if not rows:
            return self._respond(f"{self._mention(username)} has no creatures yet.")

        # Filter the rows based on the selector
        matched_rows = []
        is_pid_query = False
        if selector.lower().startswith("p") and selector[1:].isdigit():
            is_pid_query = True
            matched_rows = [r for r in rows if str(r[17]).lower() == selector.lower()]

        if not matched_rows and not is_pid_query:
            if selector.isdigit():
                target_species_id = int(selector)
                matched_rows = [r for r in rows if r[1] == target_species_id]
            else:
                selector_lower = selector.lower()
                # Exact match first
                matched_rows = [r for r in rows if r[2].lower() == selector_lower]
                # Substring match next if no exact matches found
                if not matched_rows:
                    matched_rows = [r for r in rows if selector_lower in r[2].lower()]

        if not matched_rows:
            return self._respond(f"{self._mention(username)} has no {selector} in their inventory.")

        # Format stats details
        pokemon_name = matched_rows[0][2]
        lines = [f"📋 **{username}'s {pokemon_name} Collection**\n"]
        for (_inventory_username, species_id, name, level, xp, trait, elo, wins, losses, base_hp, base_attack, base_defense, base_speed, hp_iv, atk_iv, def_iv, spd_iv, inv_id) in matched_rows:
            total_hp = int(base_hp) + int(hp_iv)
            total_atk = int(base_attack) + int(atk_iv)
            total_def = int(base_defense) + int(def_iv)
            total_spd = int(base_speed) + int(spd_iv)

            total_battles = int(wins) + int(losses)
            win_rate_str = f"{(int(wins) / total_battles) * 100:.1f}% WR" if total_battles > 0 else "No battles"

            lines.append(f"🔹 **Lv. {level} {name}** (PID: `{inv_id}`)")
            lines.append(f"🧬 **Trait:** `{trait}`  |  🏆 **ELO:** `{elo}`  |  ⚔️ **Record:** `{wins}W - {losses}L` ({win_rate_str})")
            lines.append("📊 **Stats (Base + IV):**")
            lines.append("```")
            lines.append(f"HP  : {total_hp:<3} ({base_hp} + {hp_iv})")
            lines.append(f"ATK : {total_atk:<3} ({base_attack} + {atk_iv})")
            lines.append(f"DEF : {total_def:<3} ({base_defense} + {def_iv})")
            lines.append(f"SPD : {total_spd:<3} ({base_speed} + {spd_iv})")
            lines.append("```\n")

        result = "\n".join(lines)

        # Send to Discord webhook as text
        webhook_link = self._send_discord_stats_webhook(result)
        if webhook_link:
            return self._respond(f"{self._mention(username)} here are your {matched_rows[0][2]} stats - {webhook_link}")
        return self._respond(result)

    def battle(self, challenger: str, opponent: str, pokemon: str) -> str:
        """Battle."""
        challenger = normalize_username(challenger)
        opponent = normalize_username(opponent)
        if not challenger or not opponent or challenger == opponent:
            return self._respond("Invalid battle participants.")
        if not pokemon or not pokemon.strip():
            return self._respond("Specify a Pokémon name or number.")

        logging.info("Command: battle %s vs %s with %s", challenger, opponent, pokemon)
        if self._is_battle_active():
            return self._respond("A battle is in progress. Please wait until it completes.")

        with db_session(self.paths) as conn:
            self._expire_pending_battles(conn)
            challenger_id = self._ensure_user(conn, challenger)
            opponent_id = self._ensure_user(conn, opponent)

            last_battle_at = conn.execute(
                "SELECT last_battle_at FROM users WHERE id = ?",
                (challenger_id,),
            ).fetchone()[0]
            remaining = self._get_cooldown_remaining(last_battle_at, "battle_cooldown_seconds")
            if remaining > 0:
                return self._respond(f"Battle cooldown active. Try again in {remaining}s.")

            rematch_remaining = self._get_rematch_cooldown_remaining(conn, challenger_id, opponent_id)
            if rematch_remaining > 0:
                return self._respond(
                    f"Rematch cooldown active. Try again in {rematch_remaining}s."
                )

            existing = conn.execute(
                """
                SELECT id FROM pending_battles
                WHERE challenger_id = ? AND challenged_id = ? AND status = 'pending'
                """,
                (challenger_id, opponent_id),
            ).fetchone()
            if existing:
                return self._respond(f"You already challenged {self._mention(opponent)}. Waiting for accept.")

            inv_row = self._resolve_inventory_pokemon(conn, challenger_id, pokemon)
            if not inv_row:
                return self._respond(f"{self._mention(challenger)} does not have that Pokémon.")

            opponent_has = conn.execute(
                "SELECT COUNT(*) FROM inventory WHERE user_id = ?",
                (opponent_id,),
            ).fetchone()[0]
            if opponent_has == 0:
                return self._respond(f"{self._mention(opponent)} has no creatures to battle.")

            now = now_ts()
            expires_at = now + int(self.settings["battle_timeout_seconds"])
            conn.execute(
                """
                INSERT INTO pending_battles (
                    challenger_id, challenged_id, challenger_inventory_id,
                    status, created_at, expires_at
                )
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (challenger_id, opponent_id, str(inv_row[0]), now, expires_at),
            )

        pokemon_name = inv_row[2]
        msg = (
            f"{self._mention(challenger)} challenged {self._mention(opponent)} with {pokemon_name}! "
            f"{self._mention(opponent)}, use !accept {self._mention(challenger)} <pokemon> within "
            f"{int(self.settings['battle_timeout_seconds'])}s."
        )
        logging.info("Battle challenge: %s -> %s", challenger, opponent)
        return self._respond(msg)

    def accept(self, accepter: str, challenger: str, pokemon: str) -> str:
        """Accept."""
        accepter = normalize_username(accepter)
        challenger = normalize_username(challenger)
        if not accepter or not challenger or accepter == challenger:
            return self._respond("Invalid accept participants.")
        if not pokemon or not pokemon.strip():
            return self._respond("Specify a Pokémon name or number.")

        logging.info("Command: accept %s from %s with %s", accepter, challenger, pokemon)
        if self._is_battle_active():
            return self._respond("A battle is in progress. Please wait until it completes.")

        # --- Phase 1: Database Validations ---
        with db_session(self.paths) as conn:
            self._expire_pending_battles(conn)
            accepter_id = self._ensure_user(conn, accepter)
            challenger_id = self._ensure_user(conn, challenger)

            pending = conn.execute(
                """
                SELECT id, challenger_inventory_id, expires_at
                FROM pending_battles
                WHERE challenger_id = ? AND challenged_id = ? AND status = 'pending'
                ORDER BY created_at DESC LIMIT 1
                """,
                (challenger_id, accepter_id),
            ).fetchone()
            if not pending:
                return self._respond(f"No pending challenge from {self._mention(challenger)}.")

            pending_id, challenger_inv_id, expires_at = pending
            if now_ts() >= int(expires_at):
                conn.execute(
                    "UPDATE pending_battles SET status = 'expired' WHERE id = ?",
                    (pending_id,),
                )
                return self._respond(f"Challenge from {self._mention(challenger)} has expired.")

            last_battle_at = conn.execute(
                "SELECT last_battle_at FROM users WHERE id = ?",
                (accepter_id,),
            ).fetchone()[0]
            remaining = self._get_cooldown_remaining(last_battle_at, "battle_cooldown_seconds")
            if remaining > 0:
                return self._respond(f"Battle cooldown active. Try again in {remaining}s.")

            rematch_remaining = self._get_rematch_cooldown_remaining(
                conn, challenger_id, accepter_id
            )
            if rematch_remaining > 0:
                return self._respond(
                    f"Rematch cooldown active. Try again in {rematch_remaining}s."
                )

            accepter_row = self._resolve_inventory_pokemon(conn, accepter_id, pokemon)
            if not accepter_row:
                return self._respond(f"{self._mention(accepter)} does not have that Pokémon.")

            challenger_row = conn.execute(
                """
                SELECT inventory.id, inventory.creature_id, creatures.name,
                       creatures.base_hp, creatures.base_attack, creatures.base_defense, creatures.base_speed,
                       creatures.base_sp_atk, creatures.base_sp_def, creatures.types,
                       inventory.level, inventory.xp, inventory.wins, inventory.losses,
                       inventory.hp_iv, inventory.atk_iv, inventory.def_iv, inventory.spd_iv,
                       inventory.trait, inventory.elo
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                WHERE inventory.id = ? AND inventory.user_id = ?
                """,
                (challenger_inv_id, challenger_id),
            ).fetchone()
            if not challenger_row:
                return self._respond("Challenger's Pokémon is no longer available.")

        # --- Phase 2: Active Spawn Queue & Wait (Closed DB connection) ---
        spawn = self._load_active_spawn()
        active_spawn_blocked = False
        if spawn and not self._spawn_is_expired(spawn):
            active_spawn_blocked = True

        if active_spawn_blocked:
            print("Battle accepted! It will start after the active spawned pokemon is caught or has fled.", flush=True)
            while True:
                cur_spawn = self._load_active_spawn()
                if not cur_spawn or self._spawn_is_expired(cur_spawn):
                    break
                time.sleep(1)
            print("Battle will start now!", flush=True)
        else:
            print("Battle will start now!", flush=True)

        # --- Phase 3: Execute Battle & Apply Rewards ---
        with db_session(self.paths) as conn:
            # Re-fetch rows in case anything shifted during queue wait time
            accepter_row = self._resolve_inventory_pokemon(conn, accepter_id, pokemon)
            challenger_row = conn.execute(
                """
                SELECT inventory.id, inventory.creature_id, creatures.name,
                       creatures.base_hp, creatures.base_attack, creatures.base_defense, creatures.base_speed,
                       creatures.base_sp_atk, creatures.base_sp_def, creatures.types,
                       inventory.level, inventory.xp, inventory.wins, inventory.losses,
                       inventory.hp_iv, inventory.atk_iv, inventory.def_iv, inventory.spd_iv,
                       inventory.trait, inventory.elo
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                WHERE inventory.id = ? AND inventory.user_id = ?
                """,
                (challenger_inv_id, challenger_id),
            ).fetchone()

            p1 = self._load_battle_pokemon(challenger_row, challenger)
            p2 = self._load_battle_pokemon(accepter_row, accepter)

            transcript, battle_log, winner_owner = self._simulate_battle(p1, p2)
            now = now_ts()

            winner_id = challenger_id if winner_owner == challenger else accepter_id
            loser_owner = accepter if winner_owner == challenger else challenger
            winner_pokemon = p1 if winner_owner == challenger else p2
            loser_pokemon = p2 if winner_owner == challenger else p1

            conn.execute(
                "UPDATE users SET last_battle_at = ? WHERE id IN (?, ?)",
                (now, challenger_id, accepter_id),
            )

            conn.execute(
                """
                UPDATE pending_battles
                SET status = 'completed', challenged_inventory_id = ?
                WHERE id = ?
                """,
                (str(accepter_row[0]), pending_id),
            )

            self._apply_battle_rewards(conn, winner_pokemon, loser_pokemon)
            self._apply_elo_changes(conn, winner_pokemon, loser_pokemon)
            winner_ev = self._check_evolution(conn, winner_pokemon)
            loser_ev = self._check_evolution(conn, loser_pokemon)

            conn.execute(
                "INSERT INTO battles (user1_id, user2_id, winner_id, log_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (challenger_id, accepter_id, winner_id, json.dumps(battle_log), now),
            )

        self._write_overlay(
            {
                "state": "battle",
                "message": transcript[-1] if transcript else f"{winner_owner} wins!",
                "spawn": None,
                "timer": 0,
                "result": {
                    "type": "battle",
                    "winner": winner_owner,
                    "loser": loser_owner,
                    "challenger": challenger,
                    "challenger_pokemon": p1.name,
                    "accepter": accepter,
                    "accepter_pokemon": p2.name,
                    "winner_pokemon": winner_pokemon.name,
                    "loser_pokemon": loser_pokemon.name,
                    "transcript": transcript,
                    "expires_at": now + 14,
                },
            }
        )
        time.sleep(14)
        logging.info("Battle result: %s vs %s => %s", challenger, accepter, winner_owner)

        chat_responses = []
        chat_responses.append(transcript[-1] if transcript else f"{winner_owner} wins!")

        if winner_ev:
            self._write_overlay({
                "state": "evolution",
                "message": f"{winner_pokemon.owner}'s {winner_pokemon.name} is evolving!",
                "spawn": None,
                "timer": 0,
                "evolution": {
                    "username": winner_pokemon.owner,
                    "from": winner_pokemon.name,
                    "to": winner_ev,
                    "expires_at": int(time.time()) + 8,
                }
            })
            time.sleep(8)
            chat_responses.append(f"@{winner_pokemon.owner} {winner_pokemon.name} evolved into {winner_ev}!")

        if loser_ev:
            self._write_overlay({
                "state": "evolution",
                "message": f"{loser_pokemon.owner}'s {loser_pokemon.name} is evolving!",
                "spawn": None,
                "timer": 0,
                "evolution": {
                    "username": loser_pokemon.owner,
                    "from": loser_pokemon.name,
                    "to": loser_ev,
                    "expires_at": int(time.time()) + 8,
                }
            })
            time.sleep(8)
            chat_responses.append(f"@{loser_pokemon.owner} {loser_pokemon.name} evolved into {loser_ev}!")

        if winner_ev or loser_ev:
            self._write_overlay({
                "state": "none",
                "message": "",
                "spawn": None,
                "timer": 0,
            })

        # --- Phase 4: Execute Item Drops and Level-10 Evolve Prompts ---
        drop_msgs = []
        with db_session(self.paths) as conn:
            for player in [challenger, accepter]:
                uid_row = conn.execute("SELECT id FROM users WHERE username = ?", (player,)).fetchone()
                if uid_row:
                    uid = uid_row[0]
                    roll = self.rng.random()
                    if roll < 0.50:
                        dropped_item = "great-ball"
                        conn.execute(
                            """
                            INSERT INTO bag (user_id, item_name, quantity)
                            VALUES (?, ?, 1)
                            ON CONFLICT(user_id, item_name)
                            DO UPDATE SET quantity = quantity + 1
                            """,
                            (uid, dropped_item)
                        )
                        drop_msgs.append(f"🎉 @{player} found a great-ball! This can be used to catch wild Pokémon via !catch great.")
                    elif roll < 0.85:
                        dropped_item = self.rng.choice(EVOLUTION_ITEMS)
                        conn.execute(
                            """
                            INSERT INTO bag (user_id, item_name, quantity)
                            VALUES (?, ?, 1)
                            ON CONFLICT(user_id, item_name)
                            DO UPDATE SET quantity = quantity + 1
                            """,
                            (uid, dropped_item)
                        )
                        targets = self._get_item_targets(dropped_item)
                        targets_str = ", ".join(targets)
                        if "stone" in dropped_item or dropped_item == "black-augurite":
                            note = f"This can be used to evolve {targets_str} directly."
                        else:
                            note = f"This can be used to evolve {targets_str} during a trade."
                        drop_msgs.append(f"🎉 @{player} found a {dropped_item}! {note}")
                    else:
                        dropped_item = "ultra-ball"
                        conn.execute(
                            """
                            INSERT INTO bag (user_id, item_name, quantity)
                            VALUES (?, ?, 1)
                            ON CONFLICT(user_id, item_name)
                            DO UPDATE SET quantity = quantity + 1
                            """,
                            (uid, dropped_item)
                        )
                        drop_msgs.append(f"🎉 @{player} found an ultra-ball! This can be used to catch wild Pokémon via !catch ultra.")

            # Check Level 10 Evolve prompts for both players
            p1_prompts = self._check_ready_to_evolve_prompt(conn, challenger)
            p2_prompts = self._check_ready_to_evolve_prompt(conn, accepter)

        chat_responses.extend(drop_msgs)
        chat_responses.extend(p1_prompts)
        chat_responses.extend(p2_prompts)

        return self._respond("\n".join(chat_responses))

    def bag(self, username: str) -> str:
        """List items in user's bag."""
        username = normalize_username(username)
        if not username:
            return self._respond("Invalid username.")
            
        logging.info("Command: bag %s", username)
        with db_session(self.paths) as conn:
            user_row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not user_row:
                return self._respond(f"@{username}, your Bag is empty. Win battles to earn items!")
            user_id = user_row[0]
            
            rows = conn.execute(
                "SELECT item_name, quantity FROM bag WHERE user_id = ? AND quantity > 0",
                (user_id,)
            ).fetchall()
            
        if not rows:
            return self._respond(f"@{username}, your Bag is empty. Win battles to earn items!")
            
        items_str = ", ".join(f"{qty}x {name}" for name, qty in rows)
        return self._respond(f"@{username}, your Bag contains: {items_str}.")

    def use(self, username: str, item_name: str, pid: str) -> str:
        """Use an item/stone on a pokemon (by PID)."""
        username = normalize_username(username)
        if not username:
            return self._respond("Invalid username.")
        item_name = item_name.strip().lower()
        
        pid = pid.strip()
        if not (pid.lower().startswith("p") and pid[1:].isdigit()):
            return self._respond("Invalid PID.")
            
        logging.info("Command: use %s %s on PID %s", username, item_name, pid)
        with db_session(self.paths) as conn:
            user_row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not user_row:
                return self._respond(f"@{username} has no creatures.")
            user_id = user_row[0]
            
            # Check item in bag
            item_row = conn.execute(
                "SELECT quantity FROM bag WHERE user_id = ? AND item_name = ?",
                (user_id, item_name)
            ).fetchone()
            if not item_row or int(item_row[0]) <= 0:
                return self._respond(f"@{username}, you do not have a {item_name} in your bag.")
                
            # Check pokemon ownership and level
            inv_row = conn.execute(
                """
                SELECT creatures.name, inventory.level, inventory.creature_id
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                WHERE inventory.id = ? AND inventory.user_id = ?
                """,
                (pid, user_id)
            ).fetchone()
            
            if not inv_row:
                return self._respond(f"@{username}, you do not own a Pokémon with PID {pid}.")
                
            pokemon_name, level, creature_id = inv_row
            
            if level < 10:
                return self._respond(f"@{username}, {pokemon_name} (PID: {pid}) must be at least Level 10 to evolve via item.")
                
            # Find matching rules
            rules = self._load_evolution_rules()
            species_rules = rules.get(pokemon_name, [])
            target_evolution = None
            
            for rule in species_rules:
                if rule.get("type") == "use-item" and rule.get("item") == item_name:
                    target_evolution = rule.get("to")
                    break
                    
            if not target_evolution:
                return self._respond(f"@{username}, {item_name} cannot be used to evolve {pokemon_name}.")
                
            new_creature = conn.execute(
                "SELECT id FROM creatures WHERE name = ?",
                (target_evolution,)
            ).fetchone()
            if not new_creature:
                return self._respond("Evolution target creature missing in database.")
                
            new_creature_id = int(new_creature[0])
            
            # Update database: consume item, update creature
            conn.execute(
                "UPDATE bag SET quantity = quantity - 1 WHERE user_id = ? AND item_name = ?",
                (user_id, item_name)
            )
            conn.execute(
                "UPDATE inventory SET creature_id = ? WHERE id = ?",
                (new_creature_id, pid)
            )
            conn.execute(
                "INSERT OR IGNORE INTO pokedex (user_id, creature_id) VALUES (?, ?)",
                (user_id, new_creature_id)
            )
            
        # Trigger evolution overlay animation
        self._write_overlay({
            "state": "evolution",
            "message": f"{username}'s {pokemon_name} is evolving!",
            "spawn": None,
            "timer": 0,
            "evolution": {
                "username": username,
                "from": pokemon_name,
                "to": target_evolution,
                "expires_at": int(time.time()) + 8,
            }
        })
        time.sleep(8)
        self._write_overlay({
            "state": "none",
            "message": "",
            "spawn": None,
            "timer": 0,
        })
        
        return self._respond(f"✨ @{username} used a {item_name} on their {pokemon_name} (PID: {pid}), evolving it into {target_evolution}!")

    def trade(self, sender: str, receiver: str, sender_pid: str) -> str:
        """Create a pending trade offer."""
        sender = normalize_username(sender)
        receiver = normalize_username(receiver)
        if not sender or not receiver or sender == receiver:
            return self._respond("Invalid trade participants.")
            
        logging.info("Command: trade %s offers %s to %s", sender, sender_pid, receiver)
        with db_session(self.paths) as conn:
            sender_id = self._ensure_user(conn, sender)
            receiver_id = self._ensure_user(conn, receiver)
            
            resolved = self._resolve_trade_pokemon(conn, sender_id, sender, sender_pid)
            if isinstance(resolved, str):
                return self._respond(resolved)
                
            resolved_pid, pokemon_name = resolved
            
            # Insert into pending_trades
            now = now_ts()
            expires_at = now + 120 # 2 minutes
            
            # Delete any existing active trade from sender to receiver
            conn.execute(
                "DELETE FROM pending_trades WHERE sender_id = ? AND receiver_id = ?",
                (sender_id, receiver_id)
            )
            
            conn.execute(
                """
                INSERT INTO pending_trades (sender_id, receiver_id, sender_inventory_id, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sender_id, receiver_id, resolved_pid, now, expires_at)
            )
            
        return self._respond(
            f"🤝 @{sender} wants to trade their {pokemon_name} (PID: {resolved_pid}) with @{receiver}. "
            f"@{receiver}, type !accepttrade @{sender} <pokemon_name/number> to complete the trade."
        )

    def accepttrade(self, receiver: str, sender: str, receiver_pid: str) -> str:
        """Accept a trade offer."""
        receiver = normalize_username(receiver)
        sender = normalize_username(sender)
        if not receiver or not sender or receiver == sender:
            return self._respond("Invalid trade participants.")
            
        logging.info("Command: accepttrade %s accepts from %s with %s", receiver, sender, receiver_pid)
        with db_session(self.paths) as conn:
            receiver_id = self._ensure_user(conn, receiver)
            sender_id = self._ensure_user(conn, sender)
            
            # Verify trade exists
            trade = conn.execute(
                """
                SELECT id, sender_inventory_id, expires_at FROM pending_trades
                WHERE sender_id = ? AND receiver_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (sender_id, receiver_id)
            ).fetchone()
            
            if not trade:
                return self._respond(f"No pending trade offer from @{sender}.")
                
            trade_id, sender_pid, expires_at = trade
            
            if now_ts() >= int(expires_at):
                conn.execute("DELETE FROM pending_trades WHERE id = ?", (trade_id,))
                return self._respond("The trade offer has expired.")
                
            # Resolve receiver PID / name / number
            resolved = self._resolve_trade_pokemon(conn, receiver_id, receiver, receiver_pid)
            if isinstance(resolved, str):
                return self._respond(resolved)
                
            resolved_receiver_pid, receiver_pokemon_name = resolved
            
            # Verify sender PID ownership still holds
            sender_inv = conn.execute(
                "SELECT creatures.name, inventory.level, creatures.id FROM inventory JOIN creatures ON creatures.id = inventory.creature_id WHERE inventory.id = ? AND inventory.user_id = ?",
                (sender_pid, sender_id)
            ).fetchone()
            
            if not sender_inv:
                conn.execute("DELETE FROM pending_trades WHERE id = ?", (trade_id,))
                return self._respond(f"@{sender}'s Pokémon is no longer available.")
                
            sender_pokemon_name, sender_level, sender_creature_id = sender_inv
            
            # Get receiver Pokémon level and creature_id
            receiver_inv = conn.execute(
                "SELECT inventory.level, creatures.id FROM inventory JOIN creatures ON creatures.id = inventory.creature_id WHERE inventory.id = ?",
                (resolved_receiver_pid,)
            ).fetchone()
            receiver_level, receiver_creature_id = receiver_inv
            
            # Swap owners in inventory
            conn.execute(
                "UPDATE inventory SET user_id = ?, username = ? WHERE id = ?",
                (receiver_id, receiver, sender_pid)
            )
            conn.execute(
                "UPDATE inventory SET user_id = ?, username = ? WHERE id = ?",
                (sender_id, sender, resolved_receiver_pid)
            )
            
            # Log both in pokedex for their new owners
            conn.execute("INSERT OR IGNORE INTO pokedex (user_id, creature_id) VALUES (?, ?)", (receiver_id, sender_creature_id))
            conn.execute("INSERT OR IGNORE INTO pokedex (user_id, creature_id) VALUES (?, ?)", (sender_id, receiver_creature_id))
            
            # Evolution Checks during trade
            rules = self._load_evolution_rules()
            
            def check_trade_evo(pid, p_name, user_id_val):
                species_rules = rules.get(p_name, [])
                for r in species_rules:
                    if r.get("type") == "trade":
                        held_item = r.get("held_item")
                        if held_item:
                            item_check = conn.execute(
                                "SELECT quantity FROM bag WHERE user_id = ? AND item_name = ?",
                                (user_id_val, held_item)
                            ).fetchone()
                            if not item_check or int(item_check[0]) <= 0:
                                continue
                            conn.execute(
                                "UPDATE bag SET quantity = quantity - 1 WHERE user_id = ? AND item_name = ?",
                                (user_id_val, held_item)
                            )
                        
                        evolves_to = r.get("to")
                        new_c = conn.execute("SELECT id FROM creatures WHERE name = ?", (evolves_to,)).fetchone()
                        if new_c:
                            conn.execute("UPDATE inventory SET creature_id = ? WHERE id = ?", (int(new_c[0]), pid))
                            conn.execute("INSERT OR IGNORE INTO pokedex (user_id, creature_id) VALUES (?, ?)", (user_id_val, int(new_c[0])))
                            return evolves_to
                return None
                
            sender_new_pokemon_evo = check_trade_evo(resolved_receiver_pid, receiver_pokemon_name, sender_id)
            receiver_new_pokemon_evo = check_trade_evo(sender_pid, sender_pokemon_name, receiver_id)
            
            # Delete trade offer
            conn.execute("DELETE FROM pending_trades WHERE id = ?", (trade_id,))
            
        # Build Response
        msg = f"🤝 Trade complete! @{sender} received @{receiver}'s {receiver_pokemon_name} (PID: {resolved_receiver_pid}) and @{receiver} received @{sender}'s {sender_pokemon_name} (PID: {sender_pid})."
        
        evo_notes = []
        if sender_new_pokemon_evo:
            evo_notes.append(f"@{sender}'s {receiver_pokemon_name} evolved into {sender_new_pokemon_evo}!")
        if receiver_new_pokemon_evo:
            evo_notes.append(f"@{receiver}'s {sender_pokemon_name} evolved into {receiver_new_pokemon_evo}!")
            
        if evo_notes:
            msg += " " + " ".join(evo_notes)
            
        first_evo_username = sender if sender_new_pokemon_evo else (receiver if receiver_new_pokemon_evo else None)
        first_evo_from = receiver_pokemon_name if sender_new_pokemon_evo else (sender_pokemon_name if receiver_new_pokemon_evo else None)
        first_evo_to = sender_new_pokemon_evo if sender_new_pokemon_evo else (receiver_new_pokemon_evo if receiver_new_pokemon_evo else None)
        
        if first_evo_to:
            self._write_overlay({
                "state": "evolution",
                "message": f"{first_evo_username}'s {first_evo_from} is evolving!",
                "spawn": None,
                "timer": 0,
                "evolution": {
                    "username": first_evo_username,
                    "from": first_evo_from,
                    "to": first_evo_to,
                    "expires_at": int(time.time()) + 8,
                }
            })
            time.sleep(8)
            self._write_overlay({
                "state": "none",
                "message": "",
                "spawn": None,
                "timer": 0,
            })
            
        return self._respond(msg)

    def leaderboard(self) -> str:
        """Leaderboard."""
        logging.info("Command: leaderboard")
        limit = int(self.settings["leaderboard_size"])
        with db_session(self.paths) as conn:
            pokemon_rows = conn.execute(
                """
                SELECT creatures.name, users.username, inventory.elo
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                JOIN users ON users.id = inventory.user_id
                WHERE lower(users.username) != 'user'
                ORDER BY inventory.elo DESC, inventory.level DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            player_rows = conn.execute(
                """
                SELECT username, elo
                FROM users
                WHERE lower(username) != 'user'
                ORDER BY elo DESC, created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        lines = ["🏆 **Top Pokémon by ELO:**"]
        if pokemon_rows:
            for idx, (name, owner, elo) in enumerate(pokemon_rows, start=1):
                lines.append(f"{idx}. {name} ({self._mention(owner)}) {elo}")
        else:
            lines.append("No Pokémon on the leaderboard yet.")

        lines.append("\n👑 **Top Players by ELO:**")
        if player_rows:
            for idx, (username, elo) in enumerate(player_rows, start=1):
                lines.append(f"{idx}. {self._mention(username)} {elo}")
        else:
            lines.append("No players on the leaderboard yet.")

        result = "\n".join(lines)
        webhook_link = self._send_discord_stats_webhook(result)
        if webhook_link:
            return self._respond(f"Game Leaderboard - {webhook_link}")
        return self._respond(result)

    def _apply_battle_rewards(
        self,
        conn: sqlite3.Connection,
        winner: BattlePokemon,
        loser: BattlePokemon,
    ) -> None:
        """Internal helper to apply battle rewards."""
        winner_xp = (
            int(self.settings["xp_winner_base"])
            + loser.level * int(self.settings["xp_winner_level_mult"])
        )
        loser_xp = (
            int(self.settings["xp_loser_base"])
            + winner.level * int(self.settings["xp_loser_level_mult"])
        )
        if winner.trait == "Lucky":
            winner_xp = int(winner_xp * self.settings["lucky_xp_multiplier"])
        if loser.trait == "Lucky":
            loser_xp = int(loser_xp * self.settings["lucky_xp_multiplier"])

        self._award_battle_xp(conn, winner.inv_id, winner_xp, is_winner=True)
        self._award_battle_xp(conn, loser.inv_id, loser_xp, is_winner=False)

    def _award_battle_xp(
        self, conn: sqlite3.Connection, inv_id: str, xp_gain: int, is_winner: bool
    ) -> None:
        """Internal helper to award battle xp."""
        row = conn.execute(
            "SELECT level, xp, wins, losses FROM inventory WHERE id = ?",
            (inv_id,),
        ).fetchone()
        if not row:
            return
        level, xp, wins, losses = row
        xp += xp_gain
        if is_winner:
            wins += 1
        else:
            losses += 1

        max_level = int(self.settings["max_level"])
        while level < max_level and xp >= level * 100:
            xp -= level * 100
            level += 1

        conn.execute(
            "UPDATE inventory SET level = ?, xp = ?, wins = ?, losses = ? WHERE id = ?",
            (level, xp, wins, losses, inv_id),
        )

    def _apply_elo_changes(
        self,
        conn: sqlite3.Connection,
        winner: BattlePokemon,
        loser: BattlePokemon,
    ) -> None:
        """Internal helper to apply elo changes."""
        winner_elo = winner.elo + int(self.settings["elo_win"])
        loser_elo = max(0, loser.elo - int(self.settings["elo_loss"]))
        conn.execute("UPDATE inventory SET elo = ? WHERE id = ?", (winner_elo, winner.inv_id))
        conn.execute("UPDATE inventory SET elo = ? WHERE id = ?", (loser_elo, loser.inv_id))

        # Also apply ELO changes to players
        winner_user_row = conn.execute("SELECT elo FROM users WHERE username = ?", (winner.owner,)).fetchone()
        loser_user_row = conn.execute("SELECT elo FROM users WHERE username = ?", (loser.owner,)).fetchone()

        winner_user_elo = int(winner_user_row[0]) if winner_user_row else 1000
        loser_user_elo = int(loser_user_row[0]) if loser_user_row else 1000

        new_winner_user_elo = winner_user_elo + int(self.settings["elo_win"])
        new_loser_user_elo = max(0, loser_user_elo - int(self.settings["elo_loss"]))

        conn.execute("UPDATE users SET elo = ? WHERE username = ?", (new_winner_user_elo, winner.owner))
        conn.execute("UPDATE users SET elo = ? WHERE username = ?", (new_loser_user_elo, loser.owner))

    def _check_evolution(self, conn: sqlite3.Connection, pokemon: BattlePokemon) -> Optional[str]:
        """Internal helper to check evolution."""
        rules = self._load_evolution_rules()
        species_rules = rules.get(pokemon.name, [])
        if not species_rules:
            return None

        row = conn.execute(
            "SELECT level, user_id FROM inventory WHERE id = ?",
            (pokemon.inv_id,),
        ).fetchone()
        if not row:
            return None
        level = int(row[0])
        user_id = int(row[1])

        for rule in species_rules:
            rtype = rule.get("type", "level-up")
            if rtype in ["use-item", "trade"]:
                continue

            if rtype == "level-up":
                if "level" in rule:
                    required_level = int(rule.get("level"))
                elif "friendship" in rule:
                    required_level = int(rule.get("friendship")) // 10
                else:
                    required_level = 1

                if level < required_level:
                    continue

                if "time_of_day" in rule:
                    from datetime import datetime
                    hour = datetime.now().hour
                    tod = rule.get("time_of_day")
                    is_day = 6 <= hour < 18
                    if tod == "day" and not is_day:
                        continue
                    if tod == "night" and is_day:
                        continue

                if "held_item" in rule:
                    item_needed = rule.get("held_item")
                    item_count = conn.execute(
                        "SELECT quantity FROM bag WHERE user_id = ? AND item_name = ?",
                        (user_id, item_needed)
                    ).fetchone()
                    if not item_count or int(item_count[0]) <= 0:
                        continue
                    conn.execute(
                        "UPDATE bag SET quantity = quantity - 1 WHERE user_id = ? AND item_name = ?",
                        (user_id, item_needed)
                    )
            else:
                # E.g. use-move, three-critical-hits, etc. default to level 16
                if level < 16:
                    continue

            evolves_to = rule.get("to")
            if not evolves_to:
                continue
            new_creature = conn.execute(
                "SELECT id FROM creatures WHERE name = ?",
                (evolves_to,),
            ).fetchone()
            if not new_creature:
                logging.warning("Evolution target missing: %s", evolves_to)
                continue
            conn.execute(
                "UPDATE inventory SET creature_id = ? WHERE id = ?",
                (int(new_creature[0]), pokemon.inv_id),
            )
            conn.execute(
                "INSERT OR IGNORE INTO pokedex (user_id, creature_id) VALUES (?, ?)",
                (user_id, int(new_creature[0])),
            )
            logging.info("Evolution: %s evolved into %s", pokemon.name, evolves_to)
            return evolves_to
        return None

    def _simulate_battle(
        self,
        p1: BattlePokemon,
        p2: BattlePokemon,
    ) -> Tuple[List[str], List[Dict[str, Any]], str]:
        """Internal helper to simulate battle."""
        p1_hp = p1.derived_hp
        p2_hp = p2.derived_hp
        p1_atk, p1_def, p1_spd = compute_derived_stats(
            p1.base_attack,
            p1.base_defense,
            p1.base_speed,
            p1.level,
            p1.atk_iv,
            p1.def_iv,
            p1.spd_iv,
            p1.trait,
            self.settings,
        )
        p2_atk, p2_def, p2_spd = compute_derived_stats(
            p2.base_attack,
            p2.base_defense,
            p2.base_speed,
            p2.level,
            p2.atk_iv,
            p2.def_iv,
            p2.spd_iv,
            p2.trait,
            self.settings,
        )

        transcript: List[str] = []
        log: List[Dict[str, Any]] = []

        if p1_spd >= p2_spd:
            attackers = [
                (p1, p2, p1_atk, p2_def, p1.owner, p2.owner, "p1_hp", "p2_hp"),
                (p2, p1, p2_atk, p1_def, p2.owner, p1.owner, "p2_hp", "p1_hp"),
            ]
        else:
            attackers = [
                (p2, p1, p2_atk, p1_def, p2.owner, p1.owner, "p2_hp", "p1_hp"),
                (p1, p2, p1_atk, p2_def, p1.owner, p2.owner, "p1_hp", "p2_hp"),
            ]

        hp_map = {"p1_hp": p1_hp, "p2_hp": p2_hp}
        rounds = 0
        turn_index = 0

        while hp_map["p1_hp"] > 0 and hp_map["p2_hp"] > 0 and rounds < 50:
            attacker_data = attackers[turn_index % 2]
            atk_pokemon, def_pokemon, atk, defense, atk_owner, def_owner, atk_hp_key, def_hp_key = attacker_data
            emoji = creature_emoji(atk_pokemon.name)

            crit_chance = float(self.settings["crit_chance"])
            if atk_pokemon.trait == "Berserk":
                crit_chance += float(self.settings["berserk_crit_bonus"])

            damage = 0
            is_crit = False
            is_miss = self.rng.random() < float(self.settings["miss_chance"])
            # Swift trait reduces miss chance
            miss_chance = float(self.settings["miss_chance"])
            if atk_pokemon.trait == "Swift":
                miss_chance = 0.03
            is_miss = self.rng.random() < miss_chance

            if is_miss:
                transcript.append(f"{emoji} {atk_pokemon.name} ({atk_owner}) missed!")
                log.append(
                    {
                        "attacker": atk_owner,
                        "creature": atk_pokemon.name,
                        "damage": 0,
                        "target": def_owner,
                        "miss": True,
                    }
                )
            else:
                # Determine whether attack is physical or special
                is_special = atk_pokemon.base_sp_atk > atk_pokemon.base_attack
                if atk_pokemon.base_attack >= atk_pokemon.base_sp_atk:
                    is_special = False

                # choose attack and defense values
                if is_special:
                    atk_value = compute_derived_special_atk(
                        atk_pokemon.base_sp_atk, atk_pokemon.level, atk_pokemon.atk_iv, atk_pokemon.trait, self.settings
                    )
                    def_value = compute_derived_special_def(
                        def_pokemon.base_sp_def, def_pokemon.level, def_pokemon.def_iv, def_pokemon.trait, self.settings
                    )
                else:
                    atk_value = atk
                    def_value = defense

                # choose attack type: physical -> primary; special -> secondary if exists else primary
                attack_type = None
                if atk_pokemon.types:
                    if is_special and len(atk_pokemon.types) > 1:
                        attack_type = atk_pokemon.types[-1]
                    else:
                        attack_type = atk_pokemon.types[0]

                # base raw damage
                raw_damage = (atk_value * self.rng.uniform(0.9, 1.1)) - (def_value * 0.5)

                # critical check
                if self.rng.random() < crit_chance:
                    is_crit = True
                    raw_damage *= float(self.settings["crit_multiplier"])

                # STAB
                stab = 1.0
                if attack_type and attack_type in (atk_pokemon.types or []):
                    stab = 1.5

                # type effectiveness
                eff = get_type_multiplier(attack_type or "", def_pokemon.types if def_pokemon.types else [])

                raw_damage = raw_damage * stab * eff

                damage = max(int(self.settings["min_battle_damage"]), int(raw_damage))
                hp_map[def_hp_key] -= damage
                transcript.append(f"{emoji} {atk_pokemon.name} ({atk_owner}) attacks for {damage} damage")
                if is_crit:
                    transcript.append(f"{emoji} Critical hit!")
                # effectiveness messages
                if eff == 0:
                    transcript.append(f"{emoji} It has no effect...")
                elif eff < 1:
                    transcript.append(f"{emoji} It's not very effective...")
                elif eff > 1:
                    transcript.append(f"{emoji} It's super effective!")
                log.append(
                    {
                        "attacker": atk_owner,
                        "creature": atk_pokemon.name,
                        "damage": damage,
                        "attack_type": attack_type,
                        "stab": stab,
                        "effectiveness": eff,
                        "target": def_owner,
                        "crit": is_crit,
                    }
                )

            if hp_map[def_hp_key] <= 0:
                faint_emoji = creature_emoji(def_pokemon.name)
                transcript.append(f"{faint_emoji} {def_pokemon.name} ({def_owner}) fainted")
                log.append({"fainted": def_pokemon.name, "owner": def_owner})
                break

            turn_index += 1
            if turn_index % 2 == 0:
                rounds += 1

        winner_owner = p1.owner if hp_map["p1_hp"] > 0 else p2.owner
        winner_pokemon = p1 if winner_owner == p1.owner else p2
        win_emoji = creature_emoji(winner_pokemon.name)
        transcript.append(f"🏆 {winner_pokemon.name} ( {self._mention(winner_owner)} ) wins")
        log.append({"result": "win", "winner": winner_owner})

        return transcript, log, winner_owner

    def reset_spawn(self) -> str:
        """Reset spawn."""
        logging.info("Command: reset_spawn")
        self._write_active_spawn({})
        self._write_overlay(
            {
                "state": "idle",
                "message": "",
                "spawn": None,
                "timer": 0,
                "result": None,
            }
        )
        return self._respond("Spawn reset.")

    def test_battle(self) -> str:
        """Play a mock test battle animation on the overlay."""
        logging.info("Command: test_battle")
        now = now_ts()
        mock_result = {
            "state": "battle",
            "message": "Charizard ( @Tazod ) wins",
            "spawn": None,
            "timer": 0,
            "result": {
                "type": "battle",
                "winner": "Tazod",
                "loser": "AnkitKotharkar",
                "challenger": "Tazod",
                "challenger_pokemon": "Charizard",
                "accepter": "AnkitKotharkar",
                "accepter_pokemon": "Blastoise",
                "winner_pokemon": "Charizard",
                "loser_pokemon": "Blastoise",
                "transcript": [
                    "🔥 Charizard (Tazod) attacks for 25 damage",
                    "🌊 Blastoise (AnkitKotharkar) attacks for 30 damage",
                    "🔥 Charizard (Tazod) attacks for 15 damage",
                    "🔥 Critical hit!",
                    "🌊 Blastoise (AnkitKotharkar) fainted",
                    "🏆 Charizard ( @Tazod ) wins"
                ],
                "expires_at": now + 14,
            },
        }
        self._write_overlay(mock_result)
        return "Test battle triggered on overlay."

    def test_evolution(self, username: str, old_name: str, new_name: str) -> str:
        """Play a mock evolution animation on the overlay."""
        logging.info("Command: test_evolution %s %s %s", username, old_name, new_name)
        now = int(time.time())
        mock_result = {
            "state": "evolution",
            "message": f"{username}'s {old_name} is evolving!",
            "spawn": None,
            "timer": 0,
            "evolution": {
                "username": username,
                "from": old_name,
                "to": new_name,
                "expires_at": now + 8,
            },
        }
        self._write_overlay(mock_result)
        time.sleep(8)
        self._write_overlay({
            "state": "none",
            "message": "",
            "spawn": None,
            "timer": 0,
        })
        return self._respond(f"@{username} {old_name} evolved into {new_name}!")

    def init_game(self) -> str:
        """Initialize game session, reset overlay/spawn, and check updates."""
        logging.info("Command: init")
        self._write_active_spawn({})
        self._write_overlay(
            {
                "state": "none",
                "message": "",
                "spawn": None,
                "timer": 0,
                "result": None,
            }
        )
        return self._respond("Pokemon Chat Game engine initialized successfully.")



def build_engine() -> GameEngine:
    """Build engine."""
    root = find_root()
    paths = build_paths(root)
    ensure_dirs(paths)
    setup_logging(paths)
    logging.info("GameEngine startup")
    settings = load_settings(paths)
    init_db(paths)
    seed_creatures(paths)
    ensure_data_files(paths)
    return GameEngine(paths, settings)


def main() -> int:
    """Main."""
    engine = build_engine()
    parser = argparse.ArgumentParser(prog="GameEngine")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("spawn")

    catch_parser = subparsers.add_parser("catch")
    catch_parser.add_argument("username")
    catch_parser.add_argument("ball_type", nargs="?", default="pokeball")

    pokedex_parser = subparsers.add_parser("pokedex")
    pokedex_parser.add_argument("username")

    battle_parser = subparsers.add_parser("battle")
    battle_parser.add_argument("challenger")
    battle_parser.add_argument("opponent")
    battle_parser.add_argument("pokemon")

    accept_parser = subparsers.add_parser("accept")
    accept_parser.add_argument("accepter")
    accept_parser.add_argument("challenger")
    accept_parser.add_argument("pokemon")

    subparsers.add_parser("leaderboard")

    subparsers.add_parser("reset_spawn")

    subparsers.add_parser("auto_spawn")

    subparsers.add_parser("init")

    subparsers.add_parser("test_battle")

    test_evolution_parser = subparsers.add_parser("test_evolution")
    test_evolution_parser.add_argument("username")
    test_evolution_parser.add_argument("old_name")
    test_evolution_parser.add_argument("new_name")

    stats_parser = subparsers.add_parser("stats")
    stats_parser.add_argument("username")
    stats_parser.add_argument("pokemon")

    bag_parser = subparsers.add_parser("bag")
    bag_parser.add_argument("username")

    use_parser = subparsers.add_parser("use")
    use_parser.add_argument("username")
    use_parser.add_argument("item_name")
    use_parser.add_argument("pid")

    trade_parser = subparsers.add_parser("trade")
    trade_parser.add_argument("sender")
    trade_parser.add_argument("receiver")
    trade_parser.add_argument("sender_pid")

    accepttrade_parser = subparsers.add_parser("accepttrade")
    accepttrade_parser.add_argument("receiver")
    accepttrade_parser.add_argument("sender")
    accepttrade_parser.add_argument("receiver_pid")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    cmd_logger = logging.getLogger("cmd")
    if args.command == "spawn":
        cmd_logger.info("Command: spawn")
        print(engine.spawn(), flush=True)
        return 0
    if args.command == "catch":
        cmd_logger.info("Command: catch %s using %s", args.username, args.ball_type)
        print(engine.catch(args.username, args.ball_type), flush=True)
        return 0
    if args.command == "pokedex":
        cmd_logger.info("Command: pokedex %s", args.username)
        print(engine.pokedex(args.username), flush=True)
        return 0
    if args.command == "battle":
        cmd_logger.info("Command: battle %s %s %s", args.challenger, args.opponent, args.pokemon)
        print(engine.battle(args.challenger, args.opponent, args.pokemon), flush=True)
        return 0
    if args.command == "accept":
        cmd_logger.info("Command: accept %s %s %s", args.accepter, args.challenger, args.pokemon)
        print(engine.accept(args.accepter, args.challenger, args.pokemon), flush=True)
        return 0
    if args.command == "leaderboard":
        cmd_logger.info("Command: leaderboard")
        print(engine.leaderboard(), flush=True)
        return 0
    if args.command == "reset_spawn":
        cmd_logger.info("Command: reset_spawn")
        print(engine.reset_spawn(), flush=True)
        return 0
    if args.command == "auto_spawn":
        cmd_logger.info("Command: auto_spawn")
        print(engine.auto_spawn(), flush=True)
        return 0
    if args.command == "init":
        cmd_logger.info("Command: init")
        print(engine.init_game(), flush=True)
        return 0
    if args.command == "test_battle":
        cmd_logger.info("Command: test_battle")
        print(engine.test_battle(), flush=True)
        return 0
    if args.command == "test_evolution":
        cmd_logger.info("Command: test_evolution %s %s %s", args.username, args.old_name, args.new_name)
        print(engine.test_evolution(args.username, args.old_name, args.new_name), flush=True)
        return 0
    if args.command == "stats":
        cmd_logger.info("Command: stats %s %s", args.username, args.pokemon)
        print(engine.stats(args.username, args.pokemon), flush=True)
        return 0
    if args.command == "bag":
        cmd_logger.info("Command: bag %s", args.username)
        print(engine.bag(args.username), flush=True)
        return 0
    if args.command == "use":
        cmd_logger.info("Command: use %s %s on PID %s", args.username, args.item_name, args.pid)
        print(engine.use(args.username, args.item_name, args.pid), flush=True)
        return 0
    if args.command == "trade":
        cmd_logger.info("Command: trade %s to %s with PID %s", args.sender, args.receiver, args.sender_pid)
        print(engine.trade(args.sender, args.receiver, args.sender_pid), flush=True)
        return 0
    if args.command == "accepttrade":
        cmd_logger.info("Command: accepttrade %s from %s with PID %s", args.receiver, args.sender, args.receiver_pid)
        print(engine.accepttrade(args.receiver, args.sender, args.receiver_pid), flush=True)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
