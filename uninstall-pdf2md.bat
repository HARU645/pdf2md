@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================
echo   pdf2md 배포 되돌리기
echo ============================================
echo.
echo 어디까지 지울지 고르세요.
echo.
echo   1  잠깐 끄기          - 프로그램만 종료. 언제든 다시 켜집니다
echo   2  자동 시작 해제     - 위 + 컴퓨터 켜도 안 돌아가게
echo   3  주소까지 없애기    - 위 + 터널 삭제 (pdf2md.tnmy.uk 사용 불가)
echo   0  취소
echo.
set /p LEVEL=번호를 입력하세요:

if "%LEVEL%"=="0" goto :done
if "%LEVEL%"=="" goto :done

echo.
echo [1] 돌고 있는 프로그램을 종료합니다...
taskkill /F /IM cloudflared.exe >nul 2>&1 && echo     - 터널 종료됨 || echo     - 터널이 꺼져 있었습니다
taskkill /F /IM streamlit.exe >nul 2>&1 && echo     - 앱 종료됨 || echo     - 앱이 꺼져 있었습니다
if "%LEVEL%"=="1" goto :done

echo.
echo [2] 자동 시작을 해제합니다...
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\pdf2md.lnk" >nul 2>&1 && echo     - 바로가기 삭제됨 || echo     - 바로가기가 없었습니다
if "%LEVEL%"=="2" goto :done

echo.
echo [3] Cloudflare 터널을 삭제합니다.
echo     이건 되돌릴 수 없습니다. pdf2md.tnmy.uk 주소가 못 쓰게 됩니다.
set /p SURE=정말 삭제할까요? (y 를 입력):
if /i not "%SURE%"=="y" (
    echo     - 취소했습니다. 터널은 그대로 있습니다.
    goto :done
)
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel delete pdf2md
echo.
echo     터널을 지웠습니다. 다만 DNS 기록은 아직 남아 있습니다.
echo     아래에서 직접 지우셔야 완전히 정리됩니다:
echo.
echo       1. https://dash.cloudflare.com 접속
echo       2. tnmy.uk 선택 - DNS - Records
echo       3. 이름이 pdf2md 인 CNAME 줄을 찾아 Delete
echo.

:done
echo.
echo ============================================
echo   끝났습니다.
echo.
echo   다시 켜려면:  run-pdf2md.vbs
echo   자동 시작 재등록이나 완전 삭제는 DEPLOY.md 참고
echo ============================================
echo.
pause
