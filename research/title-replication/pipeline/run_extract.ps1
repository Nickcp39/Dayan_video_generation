# Extraction stage (Sonnet): title decomposition, content decomposition, neutral briefs.
# Resumable: every LLM call is cached, so re-running continues where it stopped.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
if (-not $env:TR_WORKERS) { $env:TR_WORKERS = "6" }
python -u s4_decompose.py titles
python -u s4_decompose.py content
python -u s6_briefs.py
Write-Output "EXTRACT DONE"
