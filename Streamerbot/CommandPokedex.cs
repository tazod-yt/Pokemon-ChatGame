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
        string command = "pokedex"; // ← only this changes per script

        string invokerName = GetArgValue(new[] { "userName", "user", "displayName", "username" });
        string userArg     = GetArgValue(new[] { "input0" });
        string arg2        = GetArgValue(new[] { "input1" });

        string processArgs;

        if (command == "catch")
        {
            string target = !string.IsNullOrWhiteSpace(userArg) ? userArg : invokerName;
            if (string.IsNullOrWhiteSpace(target)) return true;
            processArgs = $"catch {target}";
        }
        else if (command == "pokedex")
        {
            string target = !string.IsNullOrWhiteSpace(userArg) ? userArg : invokerName;
            if (string.IsNullOrWhiteSpace(target)) return true;
            processArgs = $"pokedex {target}";
        }
        else if (command == "battle")
        {
            if (string.IsNullOrWhiteSpace(invokerName) || string.IsNullOrWhiteSpace(userArg) || string.IsNullOrWhiteSpace(arg2))
            {
                CPH.SendYouTubeMessage("Usage: !battle @opponent <pokemon>");
                return true;
            }
            processArgs = $"battle {invokerName} {userArg} {arg2}";
        }
        else if (command == "accept")
        {
            if (string.IsNullOrWhiteSpace(invokerName) || string.IsNullOrWhiteSpace(userArg) || string.IsNullOrWhiteSpace(arg2))
            {
                CPH.SendYouTubeMessage("Usage: !accept @challenger <pokemon>");
                return true;
            }
            processArgs = $"accept {invokerName} {userArg} {arg2}";
        }
        else if (command == "leaderboard")
        {
            processArgs = "leaderboard";
        }
        else if (command == "spawn")
        {
            processArgs = "spawn";
        }
        else
        {
            return true;
        }

        var psi = new ProcessStartInfo
        {
            FileName               = exe,
            Arguments              = processArgs,
            UseShellExecute        = false,
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            CreateNoWindow         = true,
            WorkingDirectory       = gameRoot
        };

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

        string msg = string.IsNullOrWhiteSpace(output) ? string.Empty : output.Trim();

        if (!string.IsNullOrWhiteSpace(error))
            CPH.LogWarn($"GameEngine stderr [{command}]: " + error.Trim());

        if (!string.IsNullOrWhiteSpace(msg))
            CPH.SendYouTubeMessage(msg);

        return true;
    }

    private string GetGameRoot()
    {
        string path = CPH.GetGlobalVar<string>("pokemonGamePath");
        if (!string.IsNullOrWhiteSpace(path) && System.IO.Directory.Exists(path))
            return path.Trim();

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
