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
        string exe = @"D:\Code\pokemon\Pokemon ChatGame\GameEngine\GameEngine.exe";
        string root = @"D:\Code\pokemon\Pokemon ChatGame";
        string command = "bag"; 

        string userName = GetArgValue(new[] { "userDisplayName", "userDisplay", "userName", "user", "displayName", "username" });
        string userArg = GetArgValue(new[] { "input0", "arg1", "user2", "target" });

        string target = !string.IsNullOrWhiteSpace(userArg) ? userArg : userName;
        if (string.IsNullOrWhiteSpace(target)) return true;

        string processArgs = $"bag {target}";

        CPH.LogInfo($"[GameEngine] command={command} target={target}");

        var psi = new ProcessStartInfo
        {
            FileName = exe,
            Arguments = processArgs,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            WorkingDirectory = root,
            StandardOutputEncoding = System.Text.Encoding.UTF8,
            StandardErrorEncoding = System.Text.Encoding.UTF8
        };
        psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";

        string error = string.Empty;

        var process = Process.Start(psi);
        if (process != null)
        {
            var stderrTask = Task.Run(() => process.StandardError.ReadToEnd());
            
            while (!process.StandardOutput.EndOfStream)
            {
                string line = process.StandardOutput.ReadLine();
                if (!string.IsNullOrWhiteSpace(line))
                {
                    string msg = line.Trim();
                    CPH.LogInfo($"[GameEngine] stdout line: '{msg}'");
                    
                    if (msg.Length > 195)
                    {
                        string[] words = msg.Split(' ');
                        string chunk = "";
                        foreach (var word in words)
                        {
                            if (chunk.Length + word.Length + 1 > 195)
                            {
                                CPH.SendYouTubeMessage(chunk.Trim());
                                System.Threading.Thread.Sleep(800);
                                chunk = word;
                            }
                            else
                            {
                                chunk += " " + word;
                            }
                        }
                        if (!string.IsNullOrWhiteSpace(chunk))
                        {
                            CPH.SendYouTubeMessage(chunk.Trim());
                        }
                    }
                    else
                    {
                        CPH.SendYouTubeMessage(msg);
                    }
                }
            }

            process.WaitForExit();
            error = stderrTask.Result;
        }
        else
        {
            CPH.LogWarn("[GameEngine] Process failed to launch");
            return true;
        }

        if (!string.IsNullOrWhiteSpace(error))
        {
            CPH.LogWarn($"[GameEngine] stderr: {error.Trim()}");
        }

        return true;
    }
}
