param(
  [string]$Python = "python",
  [switch]$Zip
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $root "src\game_engine.py"
$dist = Join-Path $root "GameEngine"
$work = Join-Path $root "build"

Write-Host "Building GameEngine.exe..."
& $Python -m PyInstaller --console --onefile --name GameEngine --distpath $dist --workpath $work --specpath $work --add-data "$root\image_data;image_data" $src
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

if ($Zip) {
  $zipPath = Join-Path (Split-Path -Parent $root) "Pokemon Chat Game.zip"
  $staging = Join-Path (Split-Path -Parent $root) "_zip_staging"
  $stagingInner = Join-Path $staging "PokemonChatGame"

  if (Test-Path $zipPath) { Remove-Item $zipPath }
  if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }

  New-Item -ItemType Directory -Path $stagingInner | Out-Null

  Write-Host "Staging release files to: $stagingInner..."

  # Only copy the files/folders needed for the release
  Copy-Item -Path (Join-Path $root "GameEngine") -Destination (Join-Path $stagingInner "GameEngine") -Recurse -Force
  Copy-Item -Path (Join-Path $root "Overlay")    -Destination (Join-Path $stagingInner "Overlay")    -Recurse -Force
  Copy-Item -Path (Join-Path $root "image_data") -Destination (Join-Path $stagingInner "image_data") -Recurse -Force
  Copy-Item -Path (Join-Path $root "Streamerbot") -Destination (Join-Path $stagingInner "Streamerbot") -Recurse -Force
  Copy-Item -Path (Join-Path $root "README.md")  -Destination (Join-Path $stagingInner "README.md")  -Force
  Copy-Item -Path (Join-Path $root "SETUP.md")   -Destination (Join-Path $stagingInner "SETUP.md")   -Force

  Write-Host "Creating $zipPath..."
  Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath

  Remove-Item $staging -Recurse -Force
  Write-Host "Done."
}
