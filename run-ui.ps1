<#
.SYNOPSIS
    Launch the Research Agent web UI (Streamlit).

.DESCRIPTION
    Loads .env (if present) so your API key/model are pre-filled, then starts
    the Streamlit app and opens it in your browser at http://localhost:8501.

.EXAMPLE
    .\run-ui.ps1
#>

$ErrorActionPreference = "Stop"

# Load .env so the UI can pre-fill API key / base URL / model.
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            $name = $line.Substring(0, $idx).Trim()
            $value = $line.Substring($idx + 1).Trim()
            Set-Item -Path "Env:$name" -Value $value
        }
    }
    Write-Host "Loaded .env" -ForegroundColor DarkGray
}

# Ensure the package is importable.
$env:PYTHONPATH = (Join-Path $PSScriptRoot "src")

Write-Host "Starting Research Agent UI at http://localhost:8501 ..." -ForegroundColor Green
streamlit run (Join-Path $PSScriptRoot "ui\app.py") --server.port 8501
