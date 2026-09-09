' pdf2md 자동 실행
' 앱과 Cloudflare 터널을 창 없이 띄웁니다.
' 이 파일의 바로가기가 시작프로그램 폴더에 들어가면 로그인할 때 자동으로 돌아갑니다.
' 끄려면 stop-pdf2md.bat 를 실행하세요.

Option Explicit

Dim shell, fso, root, streamlit, cloudflared
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
streamlit = root & "\venv\Scripts\streamlit.exe"
cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"

If Not fso.FileExists(streamlit) Then
    MsgBox "앱을 찾을 수 없습니다:" & vbCrLf & streamlit, 16, "pdf2md"
    WScript.Quit 1
End If

shell.CurrentDirectory = root

' 0 = 창 숨김, False = 끝날 때까지 기다리지 않음
shell.Run """" & streamlit & """ run app.py --server.port 8511 --server.headless true", 0, False

' 앱이 포트를 잡을 시간을 준 뒤 터널을 연결합니다.
WScript.Sleep 8000

If fso.FileExists(cloudflared) Then
    shell.Run """" & cloudflared & """ tunnel run pdf2md", 0, False
End If
