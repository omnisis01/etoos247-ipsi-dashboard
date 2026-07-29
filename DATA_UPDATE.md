# 데이터 갱신 런북

새 원천 엑셀(`2027학년도 수시지원의 모든 것 V*.xlsx`)을 받았을 때 따르는 검증 루프.
하네스 원칙 적용 — 매번 즉석 스크립트를 다시 짜지 말고 이 순서를 재사용한다.

## 루프

```
1. 새 엑셀을 프로젝트의 `입결/` 폴더에 둔다.
2. build_data.py 의 SRC 를 새 파일 경로로, meta.source 의 버전 라벨을 교체.
   → 검증: 파일 경로 오타 없이 로드되는지
3. python3 build_data.py
   → 검증: rows/uni/dept 수와 카테고리 카운트가 이전과 급변하지 않는지
4. python3 verify_data.py
   → 검증: 불변식 통과(exit 0). 실패하면 위반 항목 전부 수정 후 재빌드.
5. git show HEAD:data.js > <scratchpad>/prev_data.js   # 커밋 전 현재 커밋본을 baseline 으로
   python3 verify_data.py --diff <scratchpad>/prev_data.js
   → 검증: 변경 69행처럼 "의도한 수정"과 diff 가 일치하는지. 신규/삭제 행이 뜻밖이면 중단하고 원인 확인.
6. 미리보기에서 대표 행 1~2개를 fetch 로 값 재확인(예: 부산대 치의예 최저).
7. git commit (한 문장 요약 + 변경 대학·항목 목록) → git push.
```

## 불변식 (verify_data.py 가 강제)

- `meta.nRows == len(rows)`, `meta.nUni == len(dicts.uni)`
- `meta.years.cur == 2027` (연도 프레임 고정 — 2027 vs 2026)
- **입결 등급은 None 또는 1.0~9.0.** 범위 밖 = 환산점수 오입력이 등급칸에 샌 것 → 무데이터 처리.
  등급 숫자가 **작을수록 '높음/우수'**(1.0 최상). 차트·정렬·문구에서 절대 뒤집지 말 것.
- 핵심 카테고리(medical·engineering·nursing_health·business·natural) 카운트 > 0
- `meta.source` 비어 있지 않음

## pre-commit hook (권장 설치)

`data.js`·`build_data.py`·`insights.js` 등이 스테이지되면 해당 하네스를 자동 실행해 **실패 시 커밋을 막는다.**

```bash
cd dashboard
cp hooks/pre-commit .git/hooks/ && chmod +x .git/hooks/pre-commit
```

- `data.js`/`build_data.py` 스테이지 → `verify_data.py`
- `insights.js`/`build_ins.py`/`merge_ins.py` 등 스테이지 → `verify_insights.py`
- 원천 엑셀이 없는 환경이면 인사이트 하네스는 자동 SKIP(차단 안 함).
- 정말 넘겨야 하면 `git commit --no-verify`.

> ⚠️ hook 안에서 **한글 경로를 셸 glob으로 찾지 마라.** macOS는 파일명을 NFD로 저장해
> `../입결*/*.xlsx`(NFC 패턴)가 빈 결과를 낸다. 이 탓에 하네스가 조용히 건너뛰어져
> 잘못된 인사이트가 커밋을 통과한 사고가 있었다. 존재 확인은 `os.path.exists`로 한다
> (파일시스템이 정규화해 주므로 정상 동작).

## 왜 이렇게 하나 (Ratchet)

각 불변식은 실제 겪은 실패에서 나왔다.
- 입결 범위 — 환산점수가 등급칸에 섞여 9건 이상값 발생 → `vgrade()` 도입.
- 연도 프레임 — 2028 vs 2027 기사를 잘못 받아 롤백한 이력.
- diff 재사용 — V6.29 갱신 때 즉석 diff 스크립트를 두 번 짠 낭비를 `--diff` 로 굳힘.
- 최저 방향 — `3합8→2합5`를 합만 보고 강화로 오판(91전형, 유불리 판정이 반대) → `least_direction()` 집합 비교 + 검증 규칙.
- 인사이트 합계 — 권역별로 쪼갠 행 하나를 전형 총원으로 오기(경북대 지역의사 8 ← 26) → `verify_insights.py` 는 스코프 후 **합계**로만 비교.

## 배포 전 필수 — 캐시 버스팅

```bash
python3 stamp_assets.py   # index.html의 styles.css·app.js·data.js 참조에 ?v=<해시> 부여
```

⚠️ **이걸 빼먹으면 배포해도 기존 사용자는 옛 화면을 본다.** index.html이 버전 없이
참조하면 브라우저가 옛 CSS·JS를 계속 쓴다. 실제로 QA 중 서버는 새 파일을 주는데
화면은 옛 CSS로 렌더돼 "수정이 반영 안 된다"고 한참 헤맸다.
해시가 바뀐 파일만 갱신하므로 매번 돌려도 안전하다.
