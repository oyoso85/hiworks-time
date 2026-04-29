@echo off
:: [개발용] 소스 코드로 직접 실행 (playwright install chromium 필요)
cd /d "%~dp0"
start "" pythonw src\main.py
