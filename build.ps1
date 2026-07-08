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

  if (Test-Path $zipPath) { Remove-Item $zipPath }
  if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }

  Write-Host "Copying to staging: $staging..."
  Copy-Item -Path $root -Destination $staging -Recurse -Force

  # Replace live settings with the blank template
  $templateSrc  = Join-Path $root    "Config\settings.template.json"
  $templateDest = Join-Path $staging "Config\settings.json"
  Copy-Item -Path $templateSrc -Destination $templateDest -Force

  Write-Host "Creating $zipPath..."
  Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath

  Remove-Item $staging -Recurse -Force
  Write-Host "Done."
}


