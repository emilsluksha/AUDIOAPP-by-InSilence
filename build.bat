@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.12 -m venv .venv
  if errorlevel 1 exit /b 1
)
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe scripts\make_assets.py
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pytest -q
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m PyInstaller --noconfirm KEYWAVE.spec
if errorlevel 1 exit /b 1
if not exist dist\KEYWAVE\KEYWAVE.exe exit /b 1
powershell -NoProfile -Command "$p = Start-Process -FilePath 'dist\KEYWAVE\KEYWAVE.exe' -ArgumentList '--smoke-test' -WindowStyle Hidden -Wait -PassThru; exit $p.ExitCode"
if errorlevel 1 exit /b 1
echo Build ready: dist\KEYWAVE\KEYWAVE.exe
