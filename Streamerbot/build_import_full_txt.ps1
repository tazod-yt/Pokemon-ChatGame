param(
  [string]$JsonPath = "Streamerbot\\import_actions_full.json",
  [string]$TxtPath = "Streamerbot\\import_actions_full.txt"
)

if (-not (Test-Path $JsonPath)) {
  throw "JSON not found: $JsonPath"
}

$jsonText = Get-Content -Raw $JsonPath
$bytes = [Text.Encoding]::UTF8.GetBytes($jsonText)
$msOut = New-Object IO.MemoryStream
$gz = New-Object IO.Compression.GzipStream($msOut, [IO.Compression.CompressionMode]::Compress)
$gz.Write($bytes, 0, $bytes.Length)
$gz.Close()
$gzBytes = $msOut.ToArray()
$header = [Text.Encoding]::ASCII.GetBytes('SBAE')
$all = $header + $gzBytes
$b64 = [Convert]::ToBase64String($all)
Set-Content -Path $TxtPath -Value $b64 -NoNewline

Write-Host "Wrote $TxtPath"
