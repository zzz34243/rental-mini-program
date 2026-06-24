$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$localEnvPath = Join-Path $scriptPath 'local.env'
$pythonPath = Join-Path $scriptPath '.venv\Scripts\python.exe'
$serverPath = Join-Path $scriptPath 'server.py'

if (Test-Path -LiteralPath $localEnvPath) {
  foreach ($line in Get-Content -LiteralPath $localEnvPath -Encoding utf8) {
    $trimmed = $line.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith('#')) {
      continue
    }

    $parts = $trimmed.Split('=', 2)
    if ($parts.Count -ne 2) {
      continue
    }

    $name = $parts[0].Trim()
    $value = $parts[1].Trim()
    if ([string]::IsNullOrWhiteSpace($name)) {
      continue
    }

    [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
  }
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
  throw "Python virtual environment not found: $pythonPath"
}

& $pythonPath $serverPath
