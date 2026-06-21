param(
  [int]$Port = 4141,
  [string]$ConfigPath = ""
)

$ErrorActionPreference = "Stop"

$pluginRoot = Split-Path -Parent $PSScriptRoot

if (-not $ConfigPath) {
  $ConfigPath = $env:CODEX_MULTI_MODEL_LITELLM_CONFIG
}

if (-not $ConfigPath) {
  $ConfigPath = Join-Path $pluginRoot "examples\litellm-config.example.yaml"
}

$envKeys = @(
  "OPENAI_API_KEY",
  "ANTHROPIC_API_KEY",
  "DEEPSEEK_API_KEY",
  "ZAI_API_KEY",
  "GEMINI_API_KEY",
  "MOONSHOT_API_KEY",
  "MINIMAX_API_KEY"
)

foreach ($name in $envKeys) {
  if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue)) {
    $value = (Get-ItemProperty "HKCU:\Environment" -ErrorAction SilentlyContinue).$name
    if ($value) {
      Set-Item "Env:$name" $value
    }
  }
}

$availableKeys = @()
foreach ($name in $envKeys) {
  if (Get-Item "Env:$name" -ErrorAction SilentlyContinue) {
    $availableKeys += $name
  }
}

if ($availableKeys.Count -eq 0) {
  throw "No provider API keys are set. Set at least one supported API key before starting the router."
}

try {
  Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -Method Get -TimeoutSec 2 | Out-Null
  return
} catch {
}

$litellm = $null
$localLiteLLM = Join-Path $env:USERPROFILE ".codex\litellm-proxy-venv\Scripts\litellm.exe"
if (Test-Path $localLiteLLM) {
  $litellm = $localLiteLLM
} else {
  $cmd = Get-Command litellm -ErrorAction SilentlyContinue
  if ($cmd) {
    $litellm = $cmd.Source
  }
}

if (-not $litellm) {
  throw "LiteLLM was not found. Install it with: python -m pip install litellm"
}

if (-not (Test-Path $ConfigPath)) {
  throw "LiteLLM config was not found: $ConfigPath"
}

Start-Process -WindowStyle Hidden -FilePath $litellm -ArgumentList @(
  "--config", $ConfigPath,
  "--host", "127.0.0.1",
  "--port", "$Port",
  "--telemetry", "False"
)
