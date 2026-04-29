@echo off
chcp 65001 >nul
echo HiWorks Time Widget 설치 중...
echo.

pip install -r requirements.txt
if errorlevel 1 (
    echo [오류] pip install 실패
    pause
    exit /b 1
)

playwright install chromium
if errorlevel 1 (
    echo [오류] playwright install 실패
    pause
    exit /b 1
)

echo.
echo ✓ 설치 완료!
echo run.bat 을 실행하면 위젯이 시작됩니다.
pause
