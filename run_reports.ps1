# Run both report builders from the repository root.
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Reports = Join-Path $Root "reports"
$Delta = Join-Path $Reports "delta_builder"

Write-Host "Installing dependencies..."
python -m pip install -r (Join-Path $Root "requirements.txt")

Write-Host "`n=== Sales report ==="
python (Join-Path $Reports "report_generator.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Delta report ==="
python (Join-Path $Delta "delta_builder.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`nDone."
Write-Host "  Sales: $(Join-Path $Reports 'report.html')"
Write-Host "  Delta: $(Join-Path $Delta 'impact_delta_report.html')"
