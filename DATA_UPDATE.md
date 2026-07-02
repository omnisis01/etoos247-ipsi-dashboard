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

## 왜 이렇게 하나 (Ratchet)

각 불변식은 실제 겪은 실패에서 나왔다.
- 입결 범위 — 환산점수가 등급칸에 섞여 9건 이상값 발생 → `vgrade()` 도입.
- 연도 프레임 — 2028 vs 2027 기사를 잘못 받아 롤백한 이력.
- diff 재사용 — V6.29 갱신 때 즉석 diff 스크립트를 두 번 짠 낭비를 `--diff` 로 굳힘.
