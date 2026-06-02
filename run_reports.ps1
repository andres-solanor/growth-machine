# Run both report builders from the repository root.
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Project = Join-Path $Root "store-report-builder\store-report-builder"
$Delta = Join-Path $Project "delta builder"

Write-Host "Installing dependencies..."
python -m pip install -r (Join-Path $Project "requirements.txt")

Write-Host "`n=== Sales report ==="
python (Join-Path $Project "report_generator.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Delta report ==="
python (Join-Path $Delta "delta_builder.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`nDone."
Write-Host "  Sales: $(Join-Path $Project 'report.html')"
Write-Host "  Delta: $(Join-Path $Delta 'impact_delta_report.html')"
