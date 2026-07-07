using System;
using System.IO;
using System.Linq;
using System.Diagnostics;
using Newtonsoft.Json.Linq;

public class CPHInline
{
    // Path to the settings file — update if your install location differs
    private static readonly string SettingsPath =
        @"D:\Code\pokemon\Pokemon ChatGame\Config\settings.json";

    private void LogDebug(string message)
    {
        try
        {
            string dir = Path.GetDirectoryName(SettingsPath);
            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
            string logPath = Path.Combine(dir, "streamerbot_sync_debug.log");
            File.AppendAllText(logPath, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {message}\r\n", System.Text.Encoding.UTF8);
        }
        catch {}
    }

    /// <summary>
    /// Reads the global variable safely as an object to avoid any casting exceptions
    /// if the type doesn't match string exactly. Returns null if the global doesn't exist.
    /// </summary>
    private string GetGlobalAsString(string name)
    {
        // 1. Try reading as string first
        try
        {
            string strVal = CPH.GetGlobalVar<string>(name, true);
            if (strVal != null)
            {
                LogDebug($"Global '{name}' read as string: '{strVal}'");
                return strVal;
            }
        }
        catch (Exception) {}

        // 2. Try reading as double (handles both integers and floats)
        try
        {
            double? dblVal = CPH.GetGlobalVar<double?>(name, true);
            if (dblVal.HasValue)
            {
                string valStr = dblVal.Value.ToString(System.Globalization.CultureInfo.InvariantCulture);
                LogDebug($"Global '{name}' read as double: '{valStr}'");
                return valStr;
            }
        }
        catch (Exception) {}

        // 3. Try reading as long
        try
        {
            long? lngVal = CPH.GetGlobalVar<long?>(name, true);
            if (lngVal.HasValue)
            {
                string valStr = lngVal.Value.ToString(System.Globalization.CultureInfo.InvariantCulture);
                LogDebug($"Global '{name}' read as long: '{valStr}'");
                return valStr;
            }
        }
        catch (Exception) {}

        // 4. Try reading as boolean
        try
        {
            bool? boolVal = CPH.GetGlobalVar<bool?>(name, true);
            if (boolVal.HasValue)
            {
                string valStr = boolVal.Value ? "true" : "false";
                LogDebug($"Global '{name}' read as boolean: '{valStr}'");
                return valStr;
            }
        }
        catch (Exception) {}

        LogDebug($"Global '{name}' is null or not found.");
        return null;
    }

    private void SyncSettingsFromGlobals()
    {
        LogDebug("Starting SyncSettingsFromGlobals...");
        if (!File.Exists(SettingsPath))
        {
            LogDebug($"Settings file not found at: {SettingsPath}");
            return;
        }

        string json = File.ReadAllText(SettingsPath, System.Text.Encoding.UTF8);
        JObject settings;
        try { settings = JObject.Parse(json); }
        catch (Exception ex)
        {
            LogDebug($"Failed to parse settings.json: {ex.Message}");
            CPH.LogWarn($"[PokemonSettings] Failed to parse settings.json: {ex.Message}");
            return;
        }

        bool changed = false;

        foreach (string key in settings.Properties().Select(p => p.Name).ToList())
        {
            string raw = GetGlobalAsString("pokemon_" + key) ?? GetGlobalAsString(key);
            if (raw == null) continue; // Global not set, skip it

            JToken current = settings[key];
            try
            {
                switch (current.Type)
                {
                    case JTokenType.Integer:
                        settings[key] = long.Parse(raw, System.Globalization.CultureInfo.InvariantCulture);
                        break;
                    case JTokenType.Float:
                        settings[key] = double.Parse(raw, System.Globalization.CultureInfo.InvariantCulture);
                        break;
                    default:
                        settings[key] = raw;
                        break;
                }
                changed = true;
                LogDebug($"Updated key '{key}' to '{raw}' in JObject");
                CPH.LogInfo($"[PokemonSettings] {key} = {raw} (from global)");
            }
            catch (Exception ex)
            {
                LogDebug($"Failed to parse or set key '{key}' to value '{raw}': {ex.Message}");
                CPH.LogWarn($"[PokemonSettings] Skipping '{key}': could not parse '{raw}' — {ex.Message}");
            }
        }

        if (changed)
        {
            LogDebug("Writing modified settings back to settings.json...");
            File.WriteAllText(SettingsPath,
                settings.ToString(Newtonsoft.Json.Formatting.Indented),
                System.Text.Encoding.UTF8);
            LogDebug("Write complete.");
        }
        else
        {
            LogDebug("No settings were changed.");
        }
    }



    public bool Execute()
    {
        // --- Step 1: Sync settings.json from Streamerbot global vars ---
        try
        {
            SyncSettingsFromGlobals();
        }
        catch (Exception ex)
        {
            CPH.LogWarn($"[PokemonSettings] Error syncing settings: {ex.Message}");
        }

        // --- Step 2: Launch GameEngine for auto_spawn ---
        string exe = @"D:\Code\pokemon\Pokemon ChatGame\GameEngine\GameEngine.exe";
        string processArgs = "auto_spawn";

        var psi = new ProcessStartInfo
        {
            FileName = exe,
            Arguments = processArgs,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            WorkingDirectory = @"D:\Code\pokemon\Pokemon ChatGame",
            StandardOutputEncoding = System.Text.Encoding.UTF8,
            StandardErrorEncoding  = System.Text.Encoding.UTF8
        };

        try
        {
            using (var process = Process.Start(psi))
            {
                if (process != null)
                {
                    string output = process.StandardOutput.ReadToEnd().Trim();
                    string error  = process.StandardError.ReadToEnd().Trim();
                    process.WaitForExit();

                    if (!string.IsNullOrWhiteSpace(error))
                    {
                        CPH.SendYouTubeMessage($"Error: {error}");
                    }
                    else if (!string.IsNullOrWhiteSpace(output))
                    {
                        string[] lines = output.Split(
                            new[] { "\r\n", "\r", "\n" },
                            StringSplitOptions.RemoveEmptyEntries);
                        string mainOutput = "";

                        foreach (string line in lines)
                        {
                            string trimmed = line.Trim();
                            if (trimmed.StartsWith("[UPDATE_NOTIFICATION]"))
                            {
                                string newVer = trimmed.Replace("[UPDATE_NOTIFICATION]", "").Trim();

                                string lastNotifiedDate = CPH.GetGlobalVar<string>("pokemonUpdateNotifiedDate", true);
                                string todayDate = DateTime.Today.ToString("yyyy-MM-dd");

                                if (lastNotifiedDate != todayDate)
                                {
                                    string broadcaster = "streamer";
                                    try
                                    {
                                        var yt = CPH.YouTubeGetBroadcaster();
                                        if (yt != null && !string.IsNullOrWhiteSpace(yt.UserName))
                                            broadcaster = yt.UserName;
                                        else
                                        {
                                            var tw = CPH.TwitchGetBroadcaster();
                                            if (tw != null && !string.IsNullOrWhiteSpace(tw.UserName))
                                                broadcaster = tw.UserName;
                                        }
                                    }
                                    catch { }

                                    string updateMsg =
                                        $"⚠️ @{broadcaster} A new update for Pokemon Chat Game is available ({newVer})! " +
                                        $"Download it here: https://github.com/tazod-yt/Pokemon-ChatGame/releases";

                                    CPH.SendMessage(updateMsg);
                                    CPH.SendYouTubeMessage(updateMsg);
                                    CPH.SetGlobalVar("pokemonUpdateNotifiedDate", todayDate, true);
                                }
                            }
                            else
                            {
                                if (!string.IsNullOrWhiteSpace(mainOutput)) mainOutput += "\n";
                                mainOutput += trimmed;
                            }
                        }

                        if (!string.IsNullOrWhiteSpace(mainOutput))
                        {
                            CPH.SendMessage(mainOutput);
                            CPH.SendYouTubeMessage(mainOutput);
                        }
                    }
                }
                else
                {
                    CPH.SendYouTubeMessage("Failed to start GameEngine.exe");
                }
            }
        }
        catch (Exception ex)
        {
            CPH.LogWarn($"Auto spawn error: {ex.Message}");
            CPH.SendYouTubeMessage($"Auto spawn error: {ex.Message}");
        }

        return true;
    }
}
