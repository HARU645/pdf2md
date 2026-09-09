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
   - 다만 코드에 `D:\myfiles\...` 같은 내 폴더 경로가 남아 있습니다.
     그것도 보이기 싫으면 Private으로 하세요
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
