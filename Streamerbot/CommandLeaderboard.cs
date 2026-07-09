using System;
using System.Diagnostics;
using System.Threading.Tasks;

public class CPHInline
{
    private string GetArgValue(string[] names)
    {
        foreach (var name in names)
        {
            if (CPH.TryGetArg<string>(name, out string value) && !string.IsNullOrWhiteSpace(value))
                return value.Trim();
        }
        return string.Empty;
    }

    public bool Execute()
    {
        string gameRoot = GetGameRoot();
        string exe      = System.IO.Path.Combine(gameRoot, @"GameEngine\GameEngine.exe");
        string command = "leaderboard"; // ← change per action ("leaderboard", "battle", "accept", etc.)

        string invokerName = GetArgValue(new[] { "userName", "user", "displayName", "username" });
        string userArg     = GetArgValue(new[] { "input0" });
        string arg2        = GetArgValue(new[] { "input1" });

        CPH.LogInfo($"[GameEngine] command={command} invoker={invokerName} input0={userArg} input1={arg2}");

        string processArgs;

        if (command == "catch")
        {
            string target = !string.IsNullOrWhiteSpace(userArg) ? userArg : invokerName;
            if (string.IsNullOrWhiteSpace(target)) { CPH.LogWarn("[GameEngine] catch: no target"); return true; }
            processArgs = $"catch {target}";
        }
        else if (command == "pokedex")
        {
            string target = !string.IsNullOrWhiteSpace(userArg) ? userArg : invokerName;
            if (string.IsNullOrWhiteSpace(target)) { CPH.LogWarn("[GameEngine] pokedex: no target"); return true; }
            processArgs = $"pokedex {target}";
        }
        else if (command == "battle")
        {
            if (string.IsNullOrWhiteSpace(invokerName) || string.IsNullOrWhiteSpace(userArg) || string.IsNullOrWhiteSpace(arg2))
            {
                CPH.LogWarn($"[GameEngine] battle: missing args — invoker={invokerName} input0={userArg} input1={arg2}");
                CPH.SendYouTubeMessage("Usage: !battle @opponent <pokemon>");
                return true;
            }
            processArgs = $"battle {invokerName} {userArg} {arg2}";
        }
        else if (command == "accept")
        {
            if (string.IsNullOrWhiteSpace(invokerName) || string.IsNullOrWhiteSpace(userArg) || string.IsNullOrWhiteSpace(arg2))
            {
                CPH.LogWarn($"[GameEngine] accept: missing args — invoker={invokerName} input0={userArg} input1={arg2}");
                CPH.SendYouTubeMessage("Usage: !accept @challenger <pokemon>");
                return true;
            }
            processArgs = $"accept {invokerName} {userArg} {arg2}";
        }
        else if (command == "leaderboard") { processArgs = "leaderboard"; }
        else if (command == "spawn")       { processArgs = "spawn"; }
        else if (command == "stats")
        {
            if (string.IsNullOrWhiteSpace(invokerName) || string.IsNullOrWhiteSpace(userArg))
            {
                CPH.LogWarn($"[GameEngine] stats: missing args — invoker={invokerName} input0={userArg}");
                CPH.SendYouTubeMessage("Usage: !stats <pokemon name or number>");
                return true;
            }
            processArgs = $"stats {invokerName} {userArg}";
        }
        else { CPH.LogWarn($"[GameEngine] unknown command: {command}"); return true; }

        CPH.LogInfo($"[GameEngine] launching: {exe} {processArgs}");

        var psi = new ProcessStartInfo
        {
            FileName               = exe,
            Arguments              = processArgs,
            UseShellExecute        = false,
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            CreateNoWindow         = true,
            WorkingDirectory       = gameRoot,
            StandardOutputEncoding = System.Text.Encoding.UTF8,
            StandardErrorEncoding  = System.Text.Encoding.UTF8
        };
        psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";

        string output = string.Empty;
        string error  = string.Empty;

        var process = Process.Start(psi);
        if (process != null)
        {
            var stdoutTask = Task.Run(() => process.StandardOutput.ReadToEnd());
            var stderrTask = Task.Run(() => process.StandardError.ReadToEnd());
            process.WaitForExit();
            output = stdoutTask.Result;
            error  = stderrTask.Result;
        }
        else
        {
            CPH.LogWarn("[GameEngine] Process.Start returned null — EXE failed to launch");
            return true;
        }

        CPH.LogInfo($"[GameEngine] exit output: '{output.Trim()}'");
        if (!string.IsNullOrWhiteSpace(error))
            CPH.LogWarn($"[GameEngine] stderr: {error.Trim()}");

        string msg = string.IsNullOrWhiteSpace(output) ? string.Empty : output.Trim();

        // Send messages to YouTube chat while enforcing 200-char limits and anti-spam delays
        if (!string.IsNullOrWhiteSpace(msg))
        {
            string[] lines = msg.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
            string currentChunk = "";
            foreach (var line in lines)
            {
                string trimmedLine = line.Trim();
                if (string.IsNullOrEmpty(trimmedLine)) continue;

                if (string.IsNullOrEmpty(currentChunk))
                {
                    currentChunk = trimmedLine;
                }
                else
                {
                    string nextPart = " | " + trimmedLine;
                    if (currentChunk.Length + nextPart.Length > 195) // Keep safe buffer under 200
                    {
                        CPH.SendYouTubeMessage(currentChunk);
                        System.Threading.Thread.Sleep(800); // 800ms delay to prevent YouTube rate-limit
                        currentChunk = trimmedLine;
                    }
                    else
                    {
                        currentChunk += nextPart;
                    }
                }
            }
            if (!string.IsNullOrEmpty(currentChunk))
            {
                CPH.SendYouTubeMessage(currentChunk);
            }
        }
        else
        {
            CPH.LogWarn("[GameEngine] output was empty — nothing sent to chat");
        }

        return true;
    }

    private string GetGameRoot()
    {
        string path = CPH.GetGlobalVar<string>("pokemonGamePath");
        if (!string.IsNullOrWhiteSpace(path))
        {
            path = path.Trim().Trim('"', '\'');
            if (System.IO.Directory.Exists(path))
                return path;
        }

        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        if (System.IO.File.Exists(System.IO.Path.Combine(baseDir, @"GameEngine\GameEngine.exe")))
            return baseDir;

        string sub1 = System.IO.Path.Combine(baseDir, "Pokemon Chat Game");
        if (System.IO.File.Exists(System.IO.Path.Combine(sub1, @"GameEngine\GameEngine.exe")))
            return sub1;

        string sub2 = System.IO.Path.Combine(baseDir, "PokemonChatGame");
        if (System.IO.File.Exists(System.IO.Path.Combine(sub2, @"GameEngine\GameEngine.exe")))
            return sub2;

        return System.IO.Directory.GetCurrentDirectory();
    }

}
