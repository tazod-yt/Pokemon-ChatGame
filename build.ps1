param(
  [string]$Python = "python",
  [switch]$Zip
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $root "src\game_engine.py"
$dist = Join-Path $root "GameEngine"
$work = Join-Path $root "build"

Write-Host "Building GameEngine.exe..."
& $Python -m PyInstaller --onefile --name GameEngine --distpath $dist --workpath $work --specpath $work $src
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

if ($Zip) {
  $zipPath = Join-Path (Split-Path -Parent $root) "Pokemon Chat Game.zip"
  if (Test-Path $zipPath) { Remove-Item $zipPath }
  Write-Host "Creating $zipPath..."
  Compress-Archive -Path (Join-Path $root "*") -DestinationPath $zipPath
}

