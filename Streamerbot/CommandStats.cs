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
        string exe     = @"D:\Code\pokemon\Pokemon ChatGame\GameEngine\GameEngine.exe";
        string command = "stats"; // ← set to stats command

        string invokerName = GetArgValue(new[] { "userName", "user", "displayName", "username" });
        string userArg     = GetArgValue(new[] { "input0" }); // The pokemon name/id input by user

        CPH.LogInfo($"[GameEngine] command={command} invoker={invokerName} input0={userArg}");

        string processArgs;

        if (command == "stats")
        {
            if (string.IsNullOrWhiteSpace(invokerName) || string.IsNullOrWhiteSpace(userArg))
            {
                CPH.LogWarn($"[GameEngine] stats: missing args — invoker={invokerName} input0={userArg}");
                CPH.SendYouTubeMessage("Usage: !stats <pokemon name or number>");
                return true;
            }
            processArgs = $"stats {invokerName} {userArg}";
        }
        else
        {
            return true;
        }

        CPH.LogInfo($"[GameEngine] launching: {exe} {processArgs}");

        var psi = new ProcessStartInfo
        {
            FileName               = exe,
            Arguments              = processArgs,
            UseShellExecute        = false,
            RedirectStandardOutput = true,
            RedirectStandardError  = true,
            CreateNoWindow         = true,
            WorkingDirectory       = @"D:\Code\pokemon\Pokemon ChatGame",
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

        if (!string.IsNullOrWhiteSpace(msg))
            CPH.SendYouTubeMessage(msg);
        else
            CPH.LogWarn("[GameEngine] output was empty — nothing sent to chat");

        return true;
    }
}
