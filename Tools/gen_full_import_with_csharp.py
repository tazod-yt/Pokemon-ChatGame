import json
import os
import uuid
import gzip
import base64

root = r"D:\Code\pokemon\Pokemon ChatGame"
exe = root + r"\GameEngine\GameEngine.exe"
chat_path = root + r"\Data\last_chat_message.txt"

queue = "00000000-0000-0000-0000-000000000000"

STREAMERBOT_SETTING_ENV_VARS = {
    "STREAMERBOT_SPAWN_INTERVAL_SECONDS": "${STREAMERBOT_SPAWN_INTERVAL_SECONDS}",
    "STREAMERBOT_CATCH_TIMEOUT_SECONDS": "${STREAMERBOT_CATCH_TIMEOUT_SECONDS}",
    "STREAMERBOT_BATTLE_COOLDOWN_SECONDS": "${STREAMERBOT_BATTLE_COOLDOWN_SECONDS}",
    "STREAMERBOT_REMATCH_COOLDOWN_SECONDS": "${STREAMERBOT_REMATCH_COOLDOWN_SECONDS}",
    "STREAMERBOT_COOLDOWN_SECONDS": "${STREAMERBOT_COOLDOWN_SECONDS}",
}

meta = {
    "name": "Pokemon Chat Game Full Import",
    "author": "auto-generated",
    "version": "1.0.0",
    "description": "Actions + Commands for Pokemon Chat Game",
    "autoRunAction": None,
    "minimumVersion": None,
}

def make_csharp_source(arguments: str) -> str:
    lines = [
        "using System;",
        "using System.Diagnostics;",
        "using System.IO;",
        "using System.Linq;",
        "",
        "public class CPHInline",
        "{",
        "    private string GetArgValue(string[] names)",
        "    {",
        "        foreach (var name in names)",
        "        {",
        "            if (CPH.TryGetArg<string>(name, out string value) && !string.IsNullOrWhiteSpace(value))",
        "            {",
        "                return value.Trim();",
        "            }",
        "        }",
        "        return string.Empty;",
        "    }",
        "",
        "    public bool Execute()",
        "    {",
        f"        string exe = @\"{exe}\";",
        f"        string command = @\"{arguments}\";",
        "        command = command.Trim();",
        "        string userName = GetArgValue(new[] { \"userDisplayName\", \"userDisplay\", \"userName\", \"user\", \"displayName\", \"username\" });",
        "        string userArg = GetArgValue(new[] { \"input0\", \"arg1\", \"user2\", \"target\", \"opponent\" });",
        "        string arg2 = GetArgValue(new[] { \"input1\", \"arg2\" });",
        "        string processArgs = (command == \"inventory\") ? \"pokedex\" : command;",
        "",
        "        if (command == \"catch\")",
        "        {",
        "            if (!string.IsNullOrWhiteSpace(userArg))",
        "            {",
        "                processArgs += \" \" + userArg;",
        "            }",
        "            else if (!string.IsNullOrWhiteSpace(userName))",
        "            {",
        "                processArgs += \" \" + userName;",
        "            }",
        "            else",
        "            {",
        "                return true;",
        "            }",
        "        }",
        "        else if (command == \"pokedex\" || command == \"inventory\")",
        "        {",
        "            if (!string.IsNullOrWhiteSpace(userArg))",
        "            {",
        "                processArgs += \" \" + userArg;",
        "            }",
        "            else if (!string.IsNullOrWhiteSpace(userName))",
        "            {",
        "                processArgs += \" \" + userName;",
        "            }",
        "            else",
        "            {",
        "                return true;",
        "            }",
        "        }",
        "        else if (command == \"battle\")",
        "        {",
        "            if (string.IsNullOrWhiteSpace(userName) || string.IsNullOrWhiteSpace(userArg) || string.IsNullOrWhiteSpace(arg2)) return true;",
        "            processArgs += \" \" + userName + \" \" + userArg + \" \" + arg2;",
        "        }",
        "        else if (command == \"accept\")",
        "        {",
        "            if (string.IsNullOrWhiteSpace(userName) || string.IsNullOrWhiteSpace(userArg) || string.IsNullOrWhiteSpace(arg2)) return true;",
        "            processArgs += \" \" + userName + \" \" + userArg + \" \" + arg2;",
        "        }",
        "",
        "        var psi = new ProcessStartInfo",
        "        {",
        "            FileName = exe,",
        "            Arguments = processArgs,",
        "            UseShellExecute = false,",
        "            RedirectStandardOutput = true,",
        "            RedirectStandardError = true,",
        "            CreateNoWindow = true,",
        f"            WorkingDirectory = @\"{root}\",",
        "            StandardOutputEncoding = System.Text.Encoding.UTF8,",
        "            StandardErrorEncoding = System.Text.Encoding.UTF8",
        "        };",
        "        psi.EnvironmentVariables[\"PYTHONIOENCODING\"] = \"utf-8\";",
        "",
        "        var process = Process.Start(psi);",
        "        string error = string.Empty;",
        "        if (process != null)",
        "        {",
        "            var stderrTask = System.Threading.Tasks.Task.Run(() => process.StandardError.ReadToEnd());",
        "            while (!process.StandardOutput.EndOfStream)",
        "            {",
        "                string line = process.StandardOutput.ReadLine();",
        "                if (!string.IsNullOrWhiteSpace(line))",
        "                {",
        "                    string msg = line.Trim();",
        "                    if (msg.Length > 195)",
        "                    {",
        "                        string[] words = msg.Split(' ');",
        "                        string chunk = \"\";",
        "                        foreach (var word in words)",
        "                        {",
        "                            if (chunk.Length + word.Length + 1 > 195)",
        "                            {",
        "                                CPH.SendYouTubeMessage(chunk.Trim());",
        "                                System.Threading.Thread.Sleep(800);",
        "                                chunk = word;",
        "                            }",
        "                            else",
        "                            {",
        "                                chunk += \" \" + word;",
        "                            }",
        "                        }",
        "                        if (!string.IsNullOrWhiteSpace(chunk))",
        "                        {",
        "                            CPH.SendYouTubeMessage(chunk.Trim());",
        "                        }",
        "                    }",
        "                    else",
        "                    {",
        "                        CPH.SendYouTubeMessage(msg);",
        "                    }",
        "                }",
        "            }",
        "            process.WaitForExit();",
        "            error = stderrTask.Result;",
        "        }",
        "        else",
        "        {",
        "            return true;",
        "        }",
        "        if (!string.IsNullOrWhiteSpace(error))",
        "        {",
        "            CPH.LogWarn(\"GameEngine error: \" + error.Trim());",
        "        }",
        "        return true;",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


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
    byte_code = base64.b64encode(make_csharp_source(args).encode("utf-8")).decode("ascii")
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
    make_command("accept", "!accept"),
    make_command("leaderboard", "!leaderboard"),
]

actions = [
    make_action("Pokemon Chat Game Spawn", "spawn", commands[0]["id"]),
    make_action("Pokemon Chat Game Catch", "catch", commands[1]["id"]),
    make_action("Pokemon Chat Game Inventory", "inventory", commands[2]["id"]),
    make_action("Pokemon Chat Game Battle", "battle", commands[3]["id"]),
    make_action("Pokemon Chat Game Accept", "accept", commands[4]["id"]),
    make_action("Pokemon Chat Game Leaderboard", "leaderboard", commands[5]["id"]),
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
os.makedirs(os.path.dirname(out_json), exist_ok=True)
with open(out_json, "w", encoding="utf-8") as handle:
    json.dump(export, handle, indent=2)

raw = json.dumps(export, indent=2).encode("utf-8")
blob = b"SBAE" + gzip.compress(raw)
out_txt = os.path.join(root, "Streamerbot", "import_actions_full.txt")
with open(out_txt, "w", encoding="utf-8") as handle:
    handle.write(base64.b64encode(blob).decode("ascii"))

print("Wrote", out_json)
print("Wrote", out_txt)
