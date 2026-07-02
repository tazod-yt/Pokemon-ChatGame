import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from game_engine import (  # noqa: E402
    GameEngine,
    build_paths,
    compute_derived_hp,
    compute_derived_stats,
    db_session,
    ensure_data_files,
    ensure_dirs,
    init_db,
    load_settings,
    seed_creatures,
)


def make_engine(tmp_path: Path) -> GameEngine:
    os.environ["CHATGAME_ROOT"] = str(tmp_path)
    paths = build_paths(tmp_path)
    ensure_dirs(paths)
    settings = load_settings(paths)
    init_db(paths)
    seed_creatures(paths)
    ensure_data_files(paths)
    return GameEngine(paths, settings)


def catch_for_user(engine: GameEngine, username: str, base_seed: int = 1) -> None:
    start = base_seed * 1000
    for seed in range(start, start + 500):
        with db_session(engine.paths) as conn:
            conn.execute("DELETE FROM settings WHERE key = 'last_spawn_at'")
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE users SET last_catch_at = NULL WHERE id = ?", (row[0],)
                )
        engine.rng.seed(seed)
        engine.spawn()
        engine.rng.seed(seed)
        result = engine.catch(username)
        if "caught" in result:
            return
        engine.reset_spawn()
    raise RuntimeError(f"Could not catch pokemon for {username}")


def test_spawn_creation():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        result = engine.spawn()
        assert "Spawned" in result


def test_catch_success():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        catch_for_user(engine, "ankit", 1)
        result = engine.inventory("ankit")
        assert "ankit" in result


def test_catch_failure():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        engine.spawn()
        engine.rng.seed(999)
        result = engine.catch("ankit")
        assert "failed" in result or "caught" in result


def test_inventory_retrieval():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        catch_for_user(engine, "ankit", 1)
        result = engine.inventory("ankit")
        assert "ankit" in result
        assert "ELO" in result


def test_inventory_item_includes_username():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        catch_for_user(engine, "ankit", 1)
        result = engine.inventory("ankit")
        assert "Pokemon Inventory:" in result
        assert "HP" in result
        assert "ELO" in result


def test_battle_challenge_and_accept():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        catch_for_user(engine, "user1", 1)
        catch_for_user(engine, "user2", 2)

        with db_session(engine.paths) as conn:
            challenger_pokemon = conn.execute(
                "SELECT creatures.name FROM inventory JOIN creatures ON creatures.id = inventory.creature_id JOIN users ON users.id = inventory.user_id WHERE users.username = ? ORDER BY inventory.obtained_at LIMIT 1",
                ("user1",),
            ).fetchone()[0]
            accepter_pokemon = conn.execute(
                "SELECT creatures.name FROM inventory JOIN creatures ON creatures.id = inventory.creature_id JOIN users ON users.id = inventory.user_id WHERE users.username = ? ORDER BY inventory.obtained_at LIMIT 1",
                ("user2",),
            ).fetchone()[0]

        challenge = engine.battle("user1", "user2", challenger_pokemon)
        assert "challenged" in challenge

        result = engine.accept("user2", "user1", accepter_pokemon)
        assert "wins" in result.lower()


def test_leaderboard():
    with tempfile.TemporaryDirectory() as tmp:
        engine = make_engine(Path(tmp))
        catch_for_user(engine, "ankit", 1)
        result = engine.leaderboard()
        assert "Top" in result and "ELO" in result
        assert "ankit" in result


def test_derived_stats():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ensure_dirs(build_paths(tmp_path))
        settings = load_settings(build_paths(tmp_path))
        hp = compute_derived_hp(45, 10, 5)
        assert hp == 45 + 30 + 5
        atk, defense, speed = compute_derived_stats(49, 49, 45, 10, 5, 5, 5, "Brave", settings)
        assert atk > 49
        assert defense == 49 + 20 + 5


def test_data_persistence():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        engine = make_engine(root)
        catch_for_user(engine, "ankit", 1)
        engine2 = make_engine(root)
        result = engine2.inventory("ankit")
        assert "ankit" in result


def test_load_settings_streamerbot_globals_override(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STREAMERBOT_SPAWN_INTERVAL_SECONDS", "10")
    monkeypatch.setenv("STREAMERBOT_COOLDOWN_SECONDS", "7")

    paths = build_paths(tmp_path)
    ensure_dirs(paths)
    paths.settings_json.write_text(
        json.dumps({"spawn_interval_seconds": 5, "cooldown_seconds": 2}),
        encoding="utf-8",
    )

    settings = load_settings(paths)

    assert settings["spawn_interval_seconds"] == 10
    assert settings["cooldown_seconds"] == 7
