@echo off
cd /d "%~dp0"
if not exist ".venv-ram\Scripts\pythonw.exe" (
  echo Khong tim thay Python cua EnglishLens. Hay kiem tra thu muc project.
  pause
  exit /b 1
)
start "" ".venv-ram\Scripts\pythonw.exe" "%~dp0launch.py"
exit /b 0

