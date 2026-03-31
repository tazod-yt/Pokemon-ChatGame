import argparse
import json
import logging
import os
import random
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_SETTINGS = {
    "spawn_interval_seconds": 300,
    "catch_timeout_seconds": 60,
    "base_catch_rate": 0.35,
    "battle_timeout_seconds": 120,
    "cooldown_seconds": 20,
    "max_inventory_size": 50,
}

DEFAULT_CREATURES = [
    {"name": "Cinderling", "base_hp": 30, "base_attack": 8, "base_defense": 4, "catch_rate_mod": 1.0},
    {"name": "Frostkit", "base_hp": 28, "base_attack": 7, "base_defense": 5, "catch_rate_mod": 1.0},
    {"name": "Leaflet", "base_hp": 35, "base_attack": 6, "base_defense": 6, "catch_rate_mod": 1.0},
    {"name": "Sparkfin", "base_hp": 26, "base_attack": 9, "base_defense": 3, "catch_rate_mod": 0.9},
    {"name": "Stonepaw", "base_hp": 40, "base_attack": 6, "base_defense": 8, "catch_rate_mod": 0.8},
    {"name": "Glimmerbug", "base_hp": 22, "base_attack": 10, "base_defense": 2, "catch_rate_mod": 0.9},
    {"name": "Mistwisp", "base_hp": 25, "base_attack": 7, "base_defense": 4, "catch_rate_mod": 1.1},
    {"name": "Ironling", "base_hp": 38, "base_attack": 8, "base_defense": 7, "catch_rate_mod": 0.75},
    {"name": "Emberfox", "base_hp": 32, "base_attack": 9, "base_defense": 4, "catch_rate_mod": 0.85},
    {"name": "Riverwing", "base_hp": 27, "base_attack": 8, "base_defense": 5, "catch_rate_mod": 1.05},
]

USERNAME_RE = re.compile(r"[^a-zA-Z0-9_]")


@dataclass
class Paths:
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
    chat_message_txt: Path


def find_root() -> Path:
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
        chat_message_txt=data_dir / "last_chat_message.txt",
    )


def ensure_dirs(paths: Paths) -> None:
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


def load_settings(paths: Paths) -> Dict[str, Any]:
    if not paths.settings_json.exists():
        write_json(paths.settings_json, DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)

    try:
        data = read_json(paths.settings_json)
    except Exception:
        data = {}

    settings = dict(DEFAULT_SETTINGS)
    settings.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    write_json(paths.settings_json, settings)
    return settings


def setup_logging(paths: Paths) -> None:
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(paths.log_file, encoding="utf-8"),
        ],
    )


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    tmp_path.replace(path)


def now_ts() -> int:
    return int(time.time())


def normalize_username(username: str) -> str:
    cleaned = USERNAME_RE.sub("", username.strip())
    return cleaned.lower()


def connect_db(paths: Paths) -> sqlite3.Connection:
    conn = sqlite3.connect(paths.game_db)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(paths: Paths) -> None:
    conn = connect_db(paths)
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                created_at INTEGER NOT NULL,
                last_catch_at INTEGER,
                last_battle_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS creatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                base_hp INTEGER NOT NULL,
                base_attack INTEGER NOT NULL,
                base_defense INTEGER NOT NULL,
                catch_rate_mod REAL NOT NULL DEFAULT 1.0,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                creature_id INTEGER NOT NULL,
                level INTEGER NOT NULL DEFAULT 1,
                exp INTEGER NOT NULL DEFAULT 0,
                current_hp INTEGER NOT NULL,
                obtained_at INTEGER NOT NULL,
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
    conn.close()


def seed_creatures(paths: Paths) -> None:
    conn = connect_db(paths)
    with conn:
        row = conn.execute("SELECT COUNT(*) FROM creatures").fetchone()
        if row and row[0] > 0:
            return
        for creature in DEFAULT_CREATURES:
            conn.execute(
                """
                INSERT INTO creatures (name, base_hp, base_attack, base_defense, catch_rate_mod, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    creature["name"],
                    creature["base_hp"],
                    creature["base_attack"],
                    creature["base_defense"],
                    creature["catch_rate_mod"],
                    now_ts(),
                ),
            )
    conn.close()


def ensure_data_files(paths: Paths) -> None:
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
    if not paths.chat_message_txt.exists():
        paths.chat_message_txt.write_text("", encoding="utf-8")


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_setting(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row[0]
    return None


class GameEngine:
    def __init__(self, paths: Paths, settings: Dict[str, Any], rng: Optional[random.Random] = None):
        self.paths = paths
        self.settings = settings
        self.rng = rng or random.Random()

    def _load_active_spawn(self) -> Dict[str, Any]:
        try:
            data = read_json(self.paths.active_spawn_json)
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        return data

    def _write_active_spawn(self, payload: Dict[str, Any]) -> None:
        write_json(self.paths.active_spawn_json, payload)

    def _write_overlay(self, payload: Dict[str, Any]) -> None:
        payload = dict(payload)
        payload["updated_at"] = now_ts()
        write_json(self.paths.overlay_state_json, payload)

    def _write_chat_message(self, message: str) -> None:
        try:
            self.paths.chat_message_txt.write_text(message, encoding="utf-8")
        except Exception:
            logging.exception("Failed to write chat message")

    def _respond(self, message: str) -> str:
        self._write_chat_message(message)
        return message

    def _spawn_is_expired(self, spawn: Dict[str, Any]) -> bool:
        expires_at = spawn.get("expires_at")
        if not expires_at:
            return True
        return now_ts() >= int(expires_at)

    def _ensure_user(self, conn: sqlite3.Connection, username: str) -> int:
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

    def _get_cooldown_remaining(self, last_time: Optional[int]) -> int:
        if not last_time:
            return 0
        cooldown = int(self.settings["cooldown_seconds"])
        remaining = cooldown - (now_ts() - int(last_time))
        return max(0, remaining)

    def _select_random_creature(self, conn: sqlite3.Connection) -> Tuple[int, Dict[str, Any]]:
        rows = conn.execute(
            "SELECT id, name, base_hp, base_attack, base_defense, catch_rate_mod FROM creatures"
        ).fetchall()
        if not rows:
            raise RuntimeError("No creatures available")
        row = self.rng.choice(rows)
        return int(row[0]), {
            "name": row[1],
            "base_hp": int(row[2]),
            "base_attack": int(row[3]),
            "base_defense": int(row[4]),
            "catch_rate_mod": float(row[5]),
        }

    def spawn(self) -> str:
        logging.info("Command: spawn")
        spawn = self._load_active_spawn()
        if spawn and not self._spawn_is_expired(spawn):
            return self._respond(f"Spawn already active: {spawn.get('name', 'Unknown')}")
        if spawn and self._spawn_is_expired(spawn):
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

        conn = connect_db(self.paths)
        with conn:
            last_spawn_at = get_setting(conn, "last_spawn_at")
            if last_spawn_at:
                interval = int(self.settings["spawn_interval_seconds"])
                remaining = interval - (now_ts() - int(last_spawn_at))
                if remaining > 0:
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
        return self._respond(f"Spawned {creature['name']}")

    def catch(self, username: str) -> str:
        username = normalize_username(username)
        if not username:
            return self._respond("Invalid username.")

        logging.info("Command: catch %s", username)
        spawn = self._load_active_spawn()
        if spawn and self._spawn_is_expired(spawn):
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
        if not spawn or self._spawn_is_expired(spawn):
            return self._respond("No active spawn to catch.")

        conn = connect_db(self.paths)
        with conn:
            user_id = self._ensure_user(conn, username)
            last_catch_at = conn.execute(
                "SELECT last_catch_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()[0]
            remaining = self._get_cooldown_remaining(last_catch_at)
            if remaining > 0:
                return self._respond(f"Catch cooldown active. Try again in {remaining}s.")

            inv_count = conn.execute(
                "SELECT COUNT(*) FROM inventory WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            if inv_count >= int(self.settings["max_inventory_size"]):
                return self._respond("Inventory full.")

            creature_row = conn.execute(
                "SELECT base_hp, base_attack, base_defense, catch_rate_mod FROM creatures WHERE id = ?",
                (spawn.get("creature_id"),),
            ).fetchone()
            if not creature_row:
                return self._respond("Spawn creature missing.")

            base_rate = float(self.settings["base_catch_rate"])
            catch_rate = min(0.95, max(0.05, base_rate * float(creature_row[3])))
            roll = self.rng.random()
            success = roll <= catch_rate
            now = now_ts()

            conn.execute(
                "UPDATE users SET last_catch_at = ? WHERE id = ?",
                (now, user_id),
            )

            if success:
                conn.execute(
                    """
                    INSERT INTO inventory (user_id, creature_id, level, exp, current_hp, obtained_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, spawn["creature_id"], 1, 0, int(creature_row[0]), now),
                )
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
                logging.info("Catch success: %s caught %s", username, spawn.get("name"))
                return self._respond(f"{username} caught {spawn.get('name')}!")

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
            return self._respond(f"{username} failed to catch {spawn.get('name')}.")

    def inventory(self, username: str) -> str:
        username = normalize_username(username)
        if not username:
            return self._respond("Invalid username.")

        logging.info("Command: inventory %s", username)
        conn = connect_db(self.paths)
        with conn:
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not row:
                return self._respond(f"{username} has no creatures yet.")
            user_id = int(row[0])
            rows = conn.execute(
                """
                SELECT creatures.name, inventory.level, inventory.exp, inventory.current_hp
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                WHERE inventory.user_id = ?
                ORDER BY inventory.obtained_at DESC
                """,
                (user_id,),
            ).fetchall()

        if not rows:
            return self._respond(f"{username} has no creatures yet.")

        lines = [f"{username}'s creatures:"]
        for name, level, exp, hp in rows:
            lines.append(f"- {name} (Lv {level}, EXP {exp}, HP {hp})")
        return self._respond("\n".join(lines))

    def battle(self, user1: str, user2: str) -> str:
        user1 = normalize_username(user1)
        user2 = normalize_username(user2)
        if not user1 or not user2 or user1 == user2:
            return self._respond("Invalid battle participants.")

        logging.info("Command: battle %s vs %s", user1, user2)
        conn = connect_db(self.paths)
        with conn:
            user1_id = self._ensure_user(conn, user1)
            user2_id = self._ensure_user(conn, user2)

            for uid in [user1_id, user2_id]:
                last_battle_at = conn.execute(
                    "SELECT last_battle_at FROM users WHERE id = ?",
                    (uid,),
                ).fetchone()[0]
                remaining = self._get_cooldown_remaining(last_battle_at)
                if remaining > 0:
                    return self._respond(f"Battle cooldown active. Try again in {remaining}s.")

            inv1 = conn.execute(
                """
                SELECT inventory.id, creatures.name, creatures.base_hp, creatures.base_attack, creatures.base_defense, inventory.level, inventory.exp
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                WHERE inventory.user_id = ?
                """,
                (user1_id,),
            ).fetchall()
            inv2 = conn.execute(
                """
                SELECT inventory.id, creatures.name, creatures.base_hp, creatures.base_attack, creatures.base_defense, inventory.level, inventory.exp
                FROM inventory
                JOIN creatures ON creatures.id = inventory.creature_id
                WHERE inventory.user_id = ?
                """,
                (user2_id,),
            ).fetchall()

            if not inv1 or not inv2:
                return self._respond("Both users need at least one creature to battle.")

            c1 = self.rng.choice(inv1)
            c2 = self.rng.choice(inv2)

            battle_log, winner = self._simulate_battle(c1, c2, user1, user2)
            now = now_ts()

            winner_id = user1_id if winner == user1 else user2_id
            conn.execute(
                "UPDATE users SET last_battle_at = ? WHERE id IN (?, ?)",
                (now, user1_id, user2_id),
            )

            winner_inv_id = c1[0] if winner == user1 else c2[0]
            loser_inv_id = c2[0] if winner == user1 else c1[0]

            self._award_battle_exp(conn, winner_inv_id, 12)
            self._award_battle_exp(conn, loser_inv_id, 4)

            conn.execute(
                "INSERT INTO battles (user1_id, user2_id, winner_id, log_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (user1_id, user2_id, winner_id, json.dumps(battle_log), now),
            )

        self._write_overlay(
            {
                "state": "idle",
                "message": "",
                "spawn": None,
                "timer": 0,
                "result": None,
            }
        )
        logging.info("Battle result: %s vs %s => %s", user1, user2, winner)
        return self._respond(f"{winner} wins the battle!")

    def _award_battle_exp(self, conn: sqlite3.Connection, inv_id: int, exp_gain: int) -> None:
        row = conn.execute(
            "SELECT level, exp, current_hp, creatures.base_hp FROM inventory JOIN creatures ON creatures.id = inventory.creature_id WHERE inventory.id = ?",
            (inv_id,),
        ).fetchone()
        if not row:
            return
        level, exp, current_hp, base_hp = row
        exp += exp_gain
        while exp >= 100:
            exp -= 100
            level += 1
            current_hp = base_hp + level * 5
        conn.execute(
            "UPDATE inventory SET level = ?, exp = ?, current_hp = ? WHERE id = ?",
            (level, exp, current_hp, inv_id),
        )

    def _simulate_battle(
        self,
        c1: Tuple[Any, ...],
        c2: Tuple[Any, ...],
        user1: str,
        user2: str,
    ) -> Tuple[List[Dict[str, Any]], str]:
        _, c1_name, c1_hp, c1_atk, c1_def, c1_level, _ = c1
        _, c2_name, c2_hp, c2_atk, c2_def, c2_level, _ = c2

        p1_hp = c1_hp + c1_level * 5
        p2_hp = c2_hp + c2_level * 5

        log: List[Dict[str, Any]] = []
        attacker = 0
        rounds = 0
        while p1_hp > 0 and p2_hp > 0 and rounds < 50:
            rounds += 1
            if attacker == 0:
                damage = max(1, int(c1_atk + c1_level * 2 - (c2_def + c2_level) * 0.5 + self.rng.randint(0, 4)))
                p2_hp -= damage
                log.append({"attacker": user1, "creature": c1_name, "damage": damage, "target": user2})
                attacker = 1
            else:
                damage = max(1, int(c2_atk + c2_level * 2 - (c1_def + c1_level) * 0.5 + self.rng.randint(0, 4)))
                p1_hp -= damage
                log.append({"attacker": user2, "creature": c2_name, "damage": damage, "target": user1})
                attacker = 0

        winner = user1 if p1_hp > 0 else user2
        log.append({"result": "win", "winner": winner})
        return log, winner

    def reset_spawn(self) -> str:
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


def build_engine() -> GameEngine:
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
    engine = build_engine()
    parser = argparse.ArgumentParser(prog="GameEngine")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("spawn")

    catch_parser = subparsers.add_parser("catch")
    catch_parser.add_argument("username")

    inv_parser = subparsers.add_parser("inventory")
    inv_parser.add_argument("username")

    battle_parser = subparsers.add_parser("battle")
    battle_parser.add_argument("user1")
    battle_parser.add_argument("user2")

    subparsers.add_parser("reset_spawn")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    if args.command == "spawn":
        print(engine.spawn())
        return 0
    if args.command == "catch":
        print(engine.catch(args.username))
        return 0
    if args.command == "inventory":
        print(engine.inventory(args.username))
        return 0
    if args.command == "battle":
        print(engine.battle(args.user1, args.user2))
        return 0
    if args.command == "reset_spawn":
        print(engine.reset_spawn())
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
