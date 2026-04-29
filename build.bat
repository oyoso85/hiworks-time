@echo off
chcp 65001 >nul
echo ========================================
echo  HiWorks Time Widget — exe 빌드
echo ========================================
echo.

:: 1. 의존성 설치
echo [1/3] 패키지 설치 중...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [오류] pip install 실패. Python 및 pip 설치를 확인하세요.
    pause & exit /b 1
)

:: 2. PyInstaller로 단일 exe 빌드
echo [2/3] exe 빌드 중... (수 분 소요)
pyinstaller hiworks.spec --clean --noconfirm
if errorlevel 1 (
    echo [오류] PyInstaller 빌드 실패.
    pause & exit /b 1
)

:: 3. 결과물을 프로젝트 루트로 복사
echo [3/3] 결과물 복사 중...
copy /y "dist\hiworks-time.exe" "hiworks-time.exe" >nul

echo.
echo ========================================
echo  완료: hiworks-time.exe 생성됨
echo  이 파일 하나만 배포하면 됩니다.
echo ========================================
pause
