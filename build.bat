@echo off
cd /d "%~dp0"

:: venv Python 우선, 없으면 시스템 Python 사용
set VENV_PY=D:\axgate\study\toktok-drawing\.venv\Scripts\python.exe
if exist "%VENV_PY%" (
    set PYTHON=%VENV_PY%
) else (
    set PYTHON=python
)

echo [1/3] pip install...
%PYTHON% -m pip install -r requirements.txt -q
if errorlevel 1 ( echo pip failed & pause & exit /b 1 )

echo [2/3] Building exe...
%PYTHON% -m PyInstaller hiworks.spec --clean --noconfirm
if errorlevel 1 ( echo build failed & pause & exit /b 1 )

echo [3/3] Copying...
copy /y "dist\hiworks-time.exe" "hiworks-time.exe" >nul

echo Done: hiworks-time.exe
pause
