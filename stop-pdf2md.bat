@echo off
chcp 65001 >nul
echo pdf2md 를 종료합니다...
taskkill /F /IM cloudflared.exe >nul 2>&1 && echo   - 터널 종료됨 || echo   - 터널이 돌고 있지 않았습니다
taskkill /F /IM streamlit.exe >nul 2>&1 && echo   - 앱 종료됨 || echo   - 앱이 돌고 있지 않았습니다
echo.
echo 다시 켜려면 run-pdf2md.vbs 를 실행하세요.
timeout /t 3 >nul
