# Evaluation stage (Opus): dev report, then the one-time test run with all four systems.
# Resumable: every LLM call is cached.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
if (-not $env:TR_WORKERS) { $env:TR_WORKERS = "8" }
python -u s8_evaluate.py --set dev
python -u s9_report.py --set dev
python -u s7_generate.py --set test --version 2
python -u s7_generate.py --set test --systems guide --version 1
python -u s8_evaluate.py --set test
python -u s9_report.py --set test
Write-Output "EVAL DONE"
