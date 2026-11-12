param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
python -m uvicorn server.app:app --host $BindHost --port $Port
