param(
    [string]$Python = ".\venv\Scripts\python.exe"
)

if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python .\scripts\catalog_audit.py validate
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $Python -m pytest
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$ruff = ".\venv\Scripts\ruff.exe"
if (Test-Path $ruff) {
    & $ruff check .
    exit $LASTEXITCODE
}

& $Python -m ruff check .
exit $LASTEXITCODE
