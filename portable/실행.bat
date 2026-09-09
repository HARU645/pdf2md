@echo off
chcp 65001 >nul
cd /d "%~dp0"
title pdf2md
python\python.exe start.py
if errorlevel 1 (
    echo.
    echo 문제가 생겼습니다. 위 내용을 확인해 주세요.
    pause
)
