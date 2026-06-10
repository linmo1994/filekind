@echo off
setlocal
cd /d "%~dp0"
if not exist "filekind.exe" (
  echo filekind.exe not found. Run build first.
  exit /b 1
)
filekind.exe run --apply --no-dry-run
echo.
pause
