import os
import re

csharp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Streamerbot"))

helper_method = """
    private string GetGameRoot()
    {
        string path = CPH.GetGlobalVar<string>("pokemonGamePath");
        if (!string.IsNullOrWhiteSpace(path) && System.IO.Directory.Exists(path))
            return path.Trim();

        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        if (System.IO.File.Exists(System.IO.Path.Combine(baseDir, @"GameEngine\\GameEngine.exe")))
            return baseDir;

        string sub1 = System.IO.Path.Combine(baseDir, "Pokemon Chat Game");
        if (System.IO.File.Exists(System.IO.Path.Combine(sub1, @"GameEngine\\GameEngine.exe")))
            return sub1;

        string sub2 = System.IO.Path.Combine(baseDir, "PokemonChatGame");
        if (System.IO.File.Exists(System.IO.Path.Combine(sub2, @"GameEngine\\GameEngine.exe")))
            return sub2;

        return System.IO.Directory.GetCurrentDirectory();
    }
"""

for filename in os.listdir(csharp_dir):
    if not filename.endswith(".cs"):
        continue

    filepath = os.path.join(csharp_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update exe and root definitions
    content = re.sub(
        r'string exe\s*=\s*@"[^"]*\\GameEngine\\GameEngine\.exe";',
        lambda m: 'string gameRoot = GetGameRoot();\n        string exe      = System.IO.Path.Combine(gameRoot, @"GameEngine\\GameEngine.exe");',
        content
    )
    content = re.sub(
        r'string root\s*=\s*@"[^"]*";',
        lambda m: 'string root     = gameRoot;',
        content
    )

    # 2. Update settings.json in CommandAutoSpawnTimer.cs
    content = re.sub(
        r'private static readonly string SettingsPath\s*=\s*@"[^"]*";',
        lambda m: 'private string SettingsPath => System.IO.Path.Combine(GetGameRoot(), @"Config\\settings.json");',
        content
    )

    # 3. Update WorkingDirectory assignments
    content = re.sub(
        r'WorkingDirectory\s*=\s*@"[^"]*"',
        lambda m: 'WorkingDirectory       = gameRoot',
        content
    )

    # 4. Insert GetGameRoot() helper right before the final closing brace
    # Check if helper method is already there
    if "private string GetGameRoot()" not in content:
        # Find the last closing brace
        last_brace_idx = content.rfind("}")
        if last_brace_idx != -1:
            content = content[:last_brace_idx] + helper_method + "\n" + content[last_brace_idx:]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("C# files patched successfully.")
