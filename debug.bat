@echo off
cd /d "%~dp0"
python -m pip install playwright keyring -q
python debug_scraper.py
pause
