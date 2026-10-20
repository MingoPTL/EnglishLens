@echo off
setlocal
title EnglishLens
cd /d "%~dp0"
if not exist ".venv-ram\Scripts\python.exe" goto missing_python
if not exist "app.py" goto missing_app
if /I "%~1"=="--check" goto check

echo EnglishLens: http://127.0.0.1:7860/
echo Giu cua so nay mo trong luc dung app.
echo Nhan Ctrl+C de dung may chu.
echo.

".venv-ram\Scripts\python.exe" -c "import json,sys,urllib.request; c=urllib.request.build_opener(urllib.request.ProxyHandler({})); r=c.open('http://127.0.0.1:7860/api/status',timeout=2); d=json.load(r); sys.exit(0 if isinstance(d.get('models'),dict) and 'camera' in d else 1)" >nul 2>&1
if not errorlevel 1 goto already_running

".venv-ram\Scripts\python.exe" -u app.py --open
if errorlevel 1 echo App gap loi. Vui long gui noi dung loi trong cua so nay.
pause
exit /b

:already_running
echo EnglishLens dang chay. Dang mo lai giao dien...
start "" "http://127.0.0.1:7860/"
pause
exit /b 0

:check
".venv-ram\Scripts\python.exe" -c "import ast; from pathlib import Path; ast.parse(Path('app.py').read_text(encoding='utf-8')); import requests; from PIL import Image; print('PASS: Python, app.py and required UI libraries are ready.')"
exit /b %ERRORLEVEL%

:missing_python
echo Khong tim thay .venv-ram\Scripts\python.exe.
echo Hay giu run.bat trong thu muc D:\Dow\EnglishLens.
pause
exit /b 1

:missing_app
echo Khong tim thay app.py. Hay giu run.bat trong thu muc project.
pause
exit /b 1
