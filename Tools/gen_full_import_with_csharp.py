import json
import uuid
import gzip
import base64

root = r"D:\Code\pokemon\Pokemon ChatGame"
exe = root + r"\GameEngine\GameEngine.exe"
chat_path = root + r"\Data\last_chat_message.txt"

queue = "00000000-0000-0000-0000-000000000000"

meta = {
    "name": "Pokemon Chat Game Full Import",
    "author": "auto-generated",
    "version": "1.0.0",
    "description": "Actions + Commands for Pokemon Chat Game",
    "autoRunAction": None,
    "minimumVersion": None,
}

csharp_source = f"""using System.IO;

public class CPHInline
{{
    public bool Execute()
    {{
        string path = @\"{chat_path}\";
        if (!File.Exists(path)) return true;

        string msg = File.ReadAllText(path).Trim();
        if (string.IsNullOrEmpty(msg)) return true;

        CPH.SendYouTubeMessage(msg);
        return true;
    }}
}}
"""

byte_code = base64.b64encode(csharp_source.encode("utf-8")).decode("ascii")


def make_command(name, command_text):
    return {
        "permittedUsers": [],
        "permittedGroups": ["Subscribers"],
        "id": str(uuid.uuid4()),
        "name": name,
        "enabled": True,
        "include": False,
        "mode": 0,
        "command": command_text,
        "regexExplicitCapture": False,
        "location": 0,
        "ignoreBotAccount": True,
        "ignoreInternal": True,
        "sources": 1024,
        "persistCounter": False,
        "persistUserCounter": False,
        "caseSensitive": False,
        "globalCooldown": 0,
        "userCooldown": 0,
        "group": None,
        "grantType": 0,
    }


def make_action(name, args, command_id):
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
        "triggers": [
            {
                "commandId": command_id,
                "id": str(uuid.uuid4()),
                "type": 401,
                "enabled": True,
                "exclusions": [],
            }
        ],
        "subActions": [
            {
                "command": exe,
                "arguments": args,
                "workingDir": root,
                "envVars": {},
                "waitForExit": 0,
                "id": str(uuid.uuid4()),
                "weight": 0.0,
                "type": 6,
                "parentId": None,
                "enabled": True,
                "index": 0,
            },
            {
                "name": None,
                "description": None,
                "references": [
                    r"C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\mscorlib.dll"
                ],
                "byteCode": byte_code,
                "precompile": False,
                "delayStart": False,
                "saveResultToVariable": False,
                "saveToVariable": None,
                "id": str(uuid.uuid4()),
                "weight": 0.0,
                "type": 99999,
                "parentId": None,
                "enabled": True,
                "index": 1,
            },
        ],
        "collapsedGroups": [],
    }


commands = [
    make_command("spawn", "!spawn"),
    make_command("catch", "!catch"),
    make_command("inventory", "!inventory"),
    make_command("battle", "!battle"),
]

actions = [
    make_action("Pokemon Chat Game Spawn", "spawn", commands[0]["id"]),
    make_action("Pokemon Chat Game Catch", "catch ${user}", commands[1]["id"]),
    make_action("Pokemon Chat Game Inventory", "inventory ${user}", commands[2]["id"]),
    make_action("Pokemon Chat Game Battle", "battle ${user} ${arg1}", commands[3]["id"]),
]

export = {
    "meta": meta,
    "data": {
        "actions": actions,
        "queues": [],
        "commands": commands,
        "websocketServers": [],
        "websocketClients": [],
        "timers": [],
    },
    "version": 23,
    "exportedFrom": "1.0.4",
    "minimumVersion": "1.0.0-alpha.1",
}

out_json = r"Pokemon ChatGame\\Streamerbot\\import_actions_full.json"
with open(out_json, "w", encoding="utf-8") as handle:
    json.dump(export, handle, indent=2)

raw = json.dumps(export, indent=2).encode("utf-8")
blob = b"SBAE" + gzip.compress(raw)
out_txt = r"Pokemon ChatGame\\Streamerbot\\import_actions_full.txt"
with open(out_txt, "w", encoding="utf-8") as handle:
    handle.write(base64.b64encode(blob).decode("ascii"))

print("Wrote", out_json)
print("Wrote", out_txt)
