import json
import os
import uuid
import gzip
import base64

root = r"D:\Code\pokemon\Pokemon ChatGame"
exe = root + r"\GameEngine\GameEngine.exe"

queue = "00000000-0000-0000-0000-000000000000"

meta = {
    "name": "Pokemon Chat Game Full Import (C# Runner)",
    "author": "auto-generated",
    "version": "1.0.0",
    "description": "Actions + Commands for Pokemon Chat Game (C# runs EXE and sends stdout)",
    "autoRunAction": None,
    "minimumVersion": None,
}


def csharp_bytecode(args: str) -> str:
    lines = [
        "using System;",
        "using System.Diagnostics;",
        "using System.IO;",
        "using System.Linq;",
        "",
        "public class CPHInline",
        "{",
        "    public bool Execute()",
        "    {",
        f"        string exe = @\"{exe}\";",
        f"        string args = @\"{args}\";",
        "",
        "        var psi = new ProcessStartInfo",
        "        {",
        "            FileName = exe,",
        "            Arguments = args,",
        "            UseShellExecute = false,",
        "            RedirectStandardOutput = true,",
        "            RedirectStandardError = true,",
        "            CreateNoWindow = true,",
        f"            WorkingDirectory = @\"{root}\"",
        "        };",
        "",
        "        var process = Process.Start(psi);",
        "        string output = string.Empty;",
        "        string error = string.Empty;",
        "        if (process != null)",
        "        {",
        "            output = process.StandardOutput.ReadToEnd();",
        "            error = process.StandardError.ReadToEnd();",
        "            process.WaitForExit();",
        "        }",
        "",
        "        string msg = string.IsNullOrWhiteSpace(output) ? \"GameEngine launched.\" : output.Trim();",
        "        if (!string.IsNullOrWhiteSpace(error))",
        "        {",
        "            msg += \" Error: \" + error.Trim();",
        "        }",
        "",
        "        CPH.SendYouTubeMessage(msg);",
        "        return true;",
        "    }",
        "}",
        "",
    ]
    source = "\n".join(lines)
    return base64.b64encode(source.encode("utf-8")).decode("ascii")

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
                "name": None,
                "description": None,
                "references": [
                    r"C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\mscorlib.dll"
                ],
                "byteCode": csharp_bytecode(args),
                "precompile": False,
                "delayStart": False,
                "saveResultToVariable": False,
                "saveToVariable": None,
                "id": str(uuid.uuid4()),
                "weight": 0.0,
                "type": 99999,
                "parentId": None,
                "enabled": True,
                "index": 0,
            }
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

out_json = os.path.join(root, "Streamerbot", "import_actions_full.json")
with open(out_json, "w", encoding="utf-8") as handle:
    json.dump(export, handle, indent=2)

raw = json.dumps(export, indent=2).encode("utf-8")
blob = b"SBAE" + gzip.compress(raw)
out_txt = os.path.join(root, "Streamerbot", "import_actions_full.txt")
with open(out_txt, "w", encoding="utf-8") as handle:
    handle.write(base64.b64encode(blob).decode("ascii"))

print("Wrote", out_json)
print("Wrote", out_txt)
