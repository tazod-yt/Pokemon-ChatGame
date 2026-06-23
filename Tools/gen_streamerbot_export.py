import json
import os
import uuid

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

meta = {
    "name": "Pokemon Chat Game Actions",
    "author": "auto-generated",
    "version": "1.0.0",
    "description": "Pokemon Chat Game Streamer.bot actions",
    "autoRunAction": None,
    "minimumVersion": None,
}

queue = "00000000-0000-0000-0000-000000000000"

STREAMERBOT_SETTING_ENV_VARS = {
    "STREAMERBOT_SPAWN_INTERVAL_SECONDS": "${STREAMERBOT_SPAWN_INTERVAL_SECONDS}",
    "STREAMERBOT_CATCH_TIMEOUT_SECONDS": "${STREAMERBOT_CATCH_TIMEOUT_SECONDS}",
    "STREAMERBOT_BATTLE_COOLDOWN_SECONDS": "${STREAMERBOT_BATTLE_COOLDOWN_SECONDS}",
    "STREAMERBOT_REMATCH_COOLDOWN_SECONDS": "${STREAMERBOT_REMATCH_COOLDOWN_SECONDS}",
    "STREAMERBOT_COOLDOWN_SECONDS": "${STREAMERBOT_COOLDOWN_SECONDS}",
}


def action(name, args):
    return {
        "id": str(uuid.uuid4()),
        "queue": queue,
        "enabled": True,
        "excludeFromHistory": False,
        "excludeFromPending": False,
        "name": name,
        "group": "",
        "alwaysRun": False,
        "randomAction": False,
        "concurrent": False,
        "triggers": [],
        "subActions": [
            {
                "command": r"..\GameEngine\GameEngine.exe",
                "arguments": args,
                "parseVariables": True,
                "workingDir": r"..",
                "envVars": STREAMERBOT_SETTING_ENV_VARS,
                "waitForExit": 0,
                "id": str(uuid.uuid4()),
                "weight": 0.0,
                "type": 6,
                "parentId": None,
                "enabled": True,
                "index": 0,
            }
        ],
        "collapsedGroups": [],
    }


export = {
    "meta": meta,
    "data": {
        "actions": [
            action("Pokemon Chat Game Spawn", "spawn"),
            action("Pokemon Chat Game Catch", "catch ${user}"),
            action("Pokemon Chat Game Inventory", "inventory ${user}"),
            action("Pokemon Chat Game Battle", "battle ${user} ${arg1} ${arg2}"),
            action("Pokemon Chat Game Accept", "accept ${user} ${arg1} ${arg2}"),
            action("Pokemon Chat Game Leaderboard", "leaderboard"),
        ],
        "queues": [],
        "commands": [],
        "websocketServers": [],
        "websocketClients": [],
        "timers": [],
    },
    "version": 23,
    "exportedFrom": "1.0.4",
    "minimumVersion": "1.0.0-alpha.1",
}

out_json = os.path.join(root, "Streamerbot", "import_actions.json")
os.makedirs(os.path.dirname(out_json), exist_ok=True)
with open(out_json, "w", encoding="utf-8") as handle:
    json.dump(export, handle, indent=2)

print(f"Wrote {out_json}")
