# 배포 가이드 (이투스247학원 수시 대시보드)

이 대시보드는 **정적 사이트**입니다. 별도 DB·서버가 필요 없습니다.
데이터(`data.js`, 6.5MB)는 읽기 전용 입시자료라 CDN 캐싱이 가장 빠르고 저렴합니다.
(왜 DB로 분리하지 않는지는 README 하단/대화 참고)

배포 전 체크:
1. **로고**: 현재 `logo.svg`(ETOOS·247링·학원 재현본) 사용 중. 원본 PNG를 쓰고 싶으면 `logo.png`로 저장 후 `index.html`의 `<img src="logo.svg">`를 `logo.png`로 바꾸면 됩니다.
2. **GA4 측정 ID**: `index.html` 상단 `window.GA_MEASUREMENT_ID = 'G-XXXXXXXXXX'` **한 곳만** 본인 측정 ID로 교체.
   (GA4 → 관리 → 데이터 스트림 → 웹 스트림 → `측정 ID: G-XXXXXXXXXX`)
   ※ 플레이스홀더(`G-XXXX…`)인 동안은 GA 스크립트를 아예 로드하지 않습니다(불필요한 요청 없음). 실제 ID로 바꾸면 자동 연동·이벤트 수집(카테고리 선택·전형 조회·지원카드 담기 등) 시작.

---

## A. GitHub Pages (가장 간단·무료)
```bash
cd dashboard
git init && git add . && git commit -m "이투스247 수시 대시보드"
git branch -M main
git remote add origin https://github.com/<계정>/<레포>.git
git push -u origin main
```
GitHub 레포 → **Settings → Pages → Source: `main` / `(root)`** 선택 → 저장.
몇 분 뒤 `https://<계정>.github.io/<레포>/` 로 공개됩니다.
> data.js가 6.5MB라 GitHub의 50MB 권장·100MB 제한 안에서 문제없습니다.

## B. Firebase Hosting (커스텀 도메인·향후 기능 확장에 유리)
```bash
npm install -g firebase-tools
firebase login
cd dashboard
firebase init hosting    # 기존 프로젝트 선택 or 새로 생성, public 디렉터리는 "." 유지(이미 firebase.json 있음)
firebase deploy --only hosting
```
배포되면 `https://<프로젝트>.web.app` 으로 공개됩니다. 커스텀 도메인은 콘솔 → Hosting → 도메인 추가.

---

## 데이터 갱신 방법
엑셀이 업데이트되면 아래를 **순서대로 전부** 돌린다. 자세한 런북은 `DATA_UPDATE.md`.

```bash
cd dashboard
python3 build_data.py                                   # 새 data.js 생성
python3 verify_data.py && python3 qa_comp_ratio.py \
  && python3 qa_chungwon.py && python3 verify_insights.py \
  && python3 verify_frontend.py && python3 qa_known_issues.py   # 하네스
node probe_fields.js                                    # 화면 도달(실행 기반)
python3 stamp_assets.py                                 # ★ 캐시버스팅 — 빠뜨리면 배포해도 화면이 안 바뀐다
```

그 후 다시 push(A) 또는 `firebase deploy`(B). **앱 코드는 건드릴 필요 없음.**

> ⚠️ **`stamp_assets.py` 를 빠뜨리지 말 것.** index.html 이 `app.js?v=<해시>` 로 참조하므로,
> 자산만 바꾸고 스탬프를 안 갱신하면 서버는 새 파일을 주는데 브라우저는 옛 파일을 계속 쓴다.
> 실제로 이 절차에 그 줄이 없어서 사고가 났다. 지금은 pre-commit 이 `stamp_assets.py --check` 로
> 막아 주지만, 훅을 우회(`--no-verify`)하거나 훅이 설치되지 않은 클론에서는 여전히 손으로 챙겨야 한다.
>
> 프런트 파일(`app.js`·`styles.css`·`apply_dates.js`·`insights.js`)만 고친 경우에도
> **`stamp_assets.py` 는 똑같이 필요하다.** 데이터 갱신 때만 필요한 것이 아니다.

## (선택) 나중에 DB가 필요해지면
다기기 지원카드 동기화·로그인·관리자 업로드가 필요할 때만:
- **Firebase Auth + Firestore** 추가 → *사용자 즐겨찾기(지원카드)만* 저장.
- **입시 데이터(26,411행)는 계속 정적 `data.js`로 유지** (Firestore에 넣으면 방문당 수만 read로 비용·지연 급증).
