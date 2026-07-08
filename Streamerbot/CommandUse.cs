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
        string root     = gameRoot;
        string command = "use"; 

        string userName = GetArgValue(new[] { "userDisplayName", "userDisplay", "userName", "user", "displayName", "username" });
        string userArg = GetArgValue(new[] { "input0", "arg1", "item_name" });
        string arg2 = GetArgValue(new[] { "input1", "arg2", "pid" });

        if (string.IsNullOrWhiteSpace(userName) || string.IsNullOrWhiteSpace(userArg) || string.IsNullOrWhiteSpace(arg2))
        {
            CPH.SendYouTubeMessage("Usage: !use <item_name> <pid>");
            return true;
        }

        string processArgs = $"use {userName} {userArg} {arg2}";

        CPH.LogInfo($"[GameEngine] command={command} userName={userName} item={userArg} pid={arg2}");

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
