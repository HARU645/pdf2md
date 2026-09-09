# 배포하기 (Streamlit 클라우드)

링크만 알면 어느 컴퓨터에서든 쓸 수 있게 올리는 방법입니다.
전부 무료이고, 15분쯤 걸립니다.

## 배포하면 달라지는 점

올린 앱에는 이 컴퓨터의 폴더가 없습니다. 그래서 화면이 이렇게 바뀝니다.

| | 내 PC에서 실행 | 배포한 앱 |
|---|---|---|
| 폴더 통째로 변환 | 됨 | 안 됨 |
| 파일 올려서 변환 | 됨 | 됨 |
| 폴더에 저장 | 됨 | 안 됨 |
| ZIP으로 내려받기 | 됨 | 됨 |

앱이 알아서 판단해서, 배포된 곳에서는 업로드 화면만 보여줍니다.

---

## 1단계 — GitHub에 빈 저장소 만들기

1. <https://github.com/new> 접속
2. **Repository name**: `pdf2md` (다른 이름도 됩니다)
3. **Public** 또는 **Private** 선택
   - VISK 본문은 이미 저장소에서 빠져 있어서 Public도 안전합니다
   - 내 폴더 경로는 코드에서 빠져 있습니다 (.streamlit/secrets.toml 에만 있고
     그 파일은 올라가지 않습니다)
4. **아래 세 개는 체크하지 마세요** — 이미 이쪽에 파일이 있어서 충돌합니다
   - Add a README file
   - Add .gitignore
   - Choose a license
5. **Create repository**

## 2단계 — 코드 올리기

만들고 나면 GitHub가 주소를 보여줍니다.
`https://github.com/내아이디/pdf2md.git` 같은 모양입니다.

그 주소를 아래 `<주소>` 자리에 넣고 실행하세요.

```
cd D:\haru\claude_code_project\pdf2md
git remote add origin <주소>
git branch -M main
git push -u origin main
```

처음이면 GitHub 로그인 창이 뜹니다.

## 3단계 — 배포하기

1. <https://share.streamlit.io> 접속 → GitHub 계정으로 로그인
2. **Create app** → 방금 만든 저장소 선택
3. **Main file path**: `app.py`
4. **Deploy** 클릭

몇 분 기다리면 `https://이름.streamlit.app` 같은 링크가 나옵니다.
**이 링크를 아는 사람은 누구나 들어올 수 있습니다.** 그래서 다음 단계가 필요합니다.

## 4단계 — 비밀번호 걸기

1. 앱 화면 오른쪽 아래 **Manage app** → **⋮** → **Settings** → **Secrets**
2. 아래 한 줄을 넣고 저장 (비밀번호는 원하는 걸로)

```
password = "고른비밀번호"
```

3. 앱이 저절로 다시 시작됩니다. 이제 접속하면 비밀번호를 먼저 묻습니다.

비밀번호를 안 넣으면 잠금 없이 열립니다. 언제든 지웠다 다시 넣을 수 있습니다.

---

## 알아둘 것

- **한동안 안 쓰면 앱이 잠듭니다.** 다시 열면 30초쯤 걸리고, 그 다음부터는 빠릅니다.
- **올린 파일은 서버에 남지 않습니다.** 변환이 끝나면 사라지므로 결과는 ZIP으로 받아두세요.
- **코드를 고친 뒤에는** `git push` 하면 배포된 앱도 알아서 갱신됩니다.

```
cd D:\haru\claude_code_project\pdf2md
git add -A
git commit -m "설명"
git push
```

- **정답지 검사는 이 컴퓨터에서만** 돌아갑니다. 원본 PDF가 여기 있어야 하기 때문입니다.
  코드를 고쳤다면 push 하기 전에 한 번 돌려보세요.

```
venv\Scripts\python tests\test_golden.py
```

---

# 실제 배포한 방식 (Cloudflare 터널)

Streamlit 클라우드 대신 **이 컴퓨터에서 앱을 돌리고 Cloudflare가 바깥 주소를
연결해주는** 방식으로 배포했습니다. 폴더 기능이 그대로 살아있는 것이 장점입니다.

```
주소:  https://pdf2md.tnmy.uk
```

비밀번호는 `.streamlit/secrets.toml` 에 있습니다 (git에 올라가지 않습니다).

## 왜 비밀번호가 꼭 필요한가

이 앱은 폴더 경로를 입력받아 **이 컴퓨터의 파일을 읽고 씁니다.** 주소가 공개된
상태에서 잠금이 없으면, 주소를 아는 사람이 이 컴퓨터의 폴더를 지정해서 PDF를
읽고 결과 파일을 아무 데나 쓸 수 있습니다. 그래서 터널을 열기 전에 비밀번호부터
걸었습니다. **비밀번호를 지우지 마세요.**

## 켜고 끄기

컴퓨터를 켜고 로그인하면 자동으로 돌아갑니다. 시작프로그램에 등록해 두었습니다.

| 하고 싶은 것 | 실행할 파일 |
|---|---|
| 켜기 | `run-pdf2md.vbs` |
| 끄기 | `stop-pdf2md.bat` |

창이 뜨지 않으므로, 돌고 있는지는 작업 관리자에서 `streamlit.exe` 와
`cloudflared.exe` 를 찾아보면 됩니다.

## 안 될 때

**502 오류가 뜬다** — 터널은 살아있는데 앱이 꺼진 겁니다. `run-pdf2md.vbs` 실행.

**주소가 아예 안 열린다** — 터널이 꺼졌거나 컴퓨터가 꺼져 있습니다.
이 방식은 **이 컴퓨터가 켜져 있어야만** 접속됩니다.

**비밀번호를 바꾸고 싶다** — `.streamlit/secrets.toml` 의 값을 고치고
앱을 다시 시작하세요 (`stop-pdf2md.bat` 실행 후 `run-pdf2md.vbs` 실행).

## 자동 시작을 끄고 싶으면

시작프로그램 폴더에서 `pdf2md.lnk` 를 지우면 됩니다.
탐색기 주소창에 `shell:startup` 을 치면 그 폴더가 열립니다.

## 배포를 되돌리려면

`uninstall-pdf2md.bat` 를 실행하면 단계를 골라서 되돌릴 수 있습니다.

| 단계 | 하는 일 | 되돌릴 수 있나 |
|---|---|---|
| 1 | 프로그램만 종료 | ✅ `run-pdf2md.vbs` 로 바로 복구 |
| 2 | 위 + 자동 시작 해제 | ✅ 바로가기만 다시 만들면 됨 |
| 3 | 위 + 터널 삭제 | ❌ 주소를 다시 만들어야 함 |

3단계까지 하면 **DNS 기록은 따로 지워야 합니다.**
<https://dash.cloudflare.com> → `tnmy.uk` → DNS → Records 에서
이름이 `pdf2md` 인 CNAME 줄을 찾아 삭제하세요.

### 흔적까지 완전히 지우려면

위 3단계를 마친 뒤에 추가로:

```
winget uninstall Cloudflare.cloudflared
```

그리고 `C:\Users\yeong\.cloudflared` 폴더를 통째로 지우면 Cloudflare 로그인
정보까지 사라집니다.

GitHub 저장소는 <https://github.com/HARU645/pdf2md/settings> 맨 아래
Danger Zone 에서 삭제할 수 있습니다.

### 앱 자체는 그대로 남습니다

배포를 전부 되돌려도 이 컴퓨터에서 쓰는 것은 아무 영향이 없습니다.

```
venv\Scripts\python cli.py "C:\myfiles\pdf" -o "C:\myfiles\markdown"
venv\Scripts\streamlit run app.py
```
