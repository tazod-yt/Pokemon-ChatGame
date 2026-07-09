using System;
using System.Diagnostics;
using System.Threading.Tasks;

public class CPHInline
{
    public bool Execute()
    {
        string gameRoot = GetGameRoot();
        string exe      = System.IO.Path.Combine(gameRoot, @"GameEngine\GameEngine.exe");
        string processArgs = "update";

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
            CPH.LogWarn($"GameEngine stderr [update]: " + error.Trim());

        if (!string.IsNullOrWhiteSpace(msg))
        {
            CPH.LogInfo($"[AutoUpdate] result: " + msg);
            // Only send chat message on successful update, not on "already up to date" to avoid spam
            if (msg.Contains("[UPDATE_SUCCESS]"))
            {
                CPH.SendYouTubeMessage(msg);
                CPH.SendMessage(msg);
            }
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
