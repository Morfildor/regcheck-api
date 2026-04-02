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

& $Python .\scripts\catalog_audit.py report --minimum-aliases 4 --broad-alias-threshold 3
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$ruff = ".\venv\Scripts\ruff.exe"
if (Test-Path $ruff) {
    & $ruff check .
    exit $LASTEXITCODE
}

& $Python -m ruff check .
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$mypy = ".\venv\Scripts\mypy.exe"
if (Test-Path $mypy) {
    & $mypy .
    exit $LASTEXITCODE
}

& $Python -m mypy .
exit $LASTEXITCODE
