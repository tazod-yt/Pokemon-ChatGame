import json
import uuid

meta = {
    "name": "Pokemon Chat Game Actions",
    "author": "auto-generated",
    "version": "1.0.0",
    "description": "Pokemon Chat Game Streamer.bot actions",
    "autoRunAction": None,
    "minimumVersion": None,
}

queue = "00000000-0000-0000-0000-000000000000"


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
                "envVars": {},
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

with open(r"Pokemon ChatGame\Streamerbot\import_actions.json", "w", encoding="utf-8") as handle:
    json.dump(export, handle, indent=2)

print("Wrote Pokemon ChatGame\\Streamerbot\\import_actions.json")
