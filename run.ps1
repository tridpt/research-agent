<#
.SYNOPSIS
    Convenience launcher for research-agent on Windows PowerShell.

.DESCRIPTION
    Loads environment variables from a local .env file (if present), applies
    sensible Gemini defaults for anything still unset, then runs the agent.
    All arguments are forwarded as-is to the agent CLI.

.EXAMPLE
    .\run.ps1 "What is retrieval-augmented generation?" -o report.md -v
#>

$ErrorActionPreference = "Stop"

# 1. Load .env (KEY=VALUE lines; '#' comments and blanks ignored).
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

# 2. Apply Gemini defaults for anything not already set.
if (-not $env:RESEARCH_AGENT_BASE_URL) {
    $env:RESEARCH_AGENT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
}
if (-not $env:RESEARCH_AGENT_MODEL) {
    $env:RESEARCH_AGENT_MODEL = "gemini-2.5-flash-lite"
}
if (-not $env:RESEARCH_AGENT_MAX_LLM_ATTEMPTS) {
    $env:RESEARCH_AGENT_MAX_LLM_ATTEMPTS = "5"
}

# 3. Validate the required key.
if (-not $env:RESEARCH_AGENT_API_KEY) {
    Write-Error "RESEARCH_AGENT_API_KEY is not set. Copy .env.example to .env and add your key."
    exit 2
}

# 4. Run the agent from the src/ layout without requiring an install.
$env:PYTHONPATH = (Join-Path $PSScriptRoot "src")
python -m research_agent.cli @args
exit $LASTEXITCODE
