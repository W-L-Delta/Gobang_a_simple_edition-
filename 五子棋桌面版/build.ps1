$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --runtime-tmpdir "." `
  --name "五子棋" `
  --icon "assets\gomoku.ico" `
  --add-data "assets;assets" `
  "main.py"

if (-not (Test-Path -LiteralPath "dist\五子棋.exe")) {
    throw "PyInstaller did not produce dist\五子棋.exe"
}

Copy-Item -LiteralPath "dist\五子棋.exe" -Destination ".\五子棋.exe" -Force
Write-Host "Built: $PSScriptRoot\五子棋.exe"
