using System;
using System.Diagnostics;
using System.Threading.Tasks;

public class CPHInline
{
    public bool Execute()
    {
        string exe     = @"D:\Code\pokemon\Pokemon ChatGame\GameEngine\GameEngine.exe";
        string processArgs = "update";

        var psi = new ProcessStartInfo
        {
            FileName               = exe,
            Arguments              = processArgs,
            UseShellExecute        = false,
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            CreateNoWindow         = true,
            WorkingDirectory       = @"D:\Code\pokemon\Pokemon ChatGame"
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
}
