@echo off
REM run_test_copy.bat
REM 이 배치 파일은 항상 Anaconda 파이썬(pyhwpx가 설치된 환경)을 사용해서
REM test_copy.py를 실행합니다. 어떤 터미널/에디터에서 실행하든 상관없이
REM 항상 같은 파이썬을 쓰도록 경로를 고정합니다.

cd /d "%~dp0"
echo 현재 폴더: %cd%
echo.
echo Anaconda 파이썬으로 test_copy.py 실행합니다...
echo.

C:\Users\user\anaconda3\python.exe test_copy.py

echo.
echo ============================================
echo 스크립트 실행이 종료되었습니다.
pause
