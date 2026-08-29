# dashboard/CLAUDE.md — 조종사 체크리스트

이 파일은 이 대시보드 프로젝트(dashboard/)에만 적용되는 하네스 규칙이다. 상위 `CLAUDE.md`(전역)와 병합 로드된다. 60줄 이내 유지, "매번 지켜야 할 것"만 담는다.

## 세션 재개 절차 (반드시 이 순서)
1. 이 파일을 읽는다(자동 로드됨).
2. `dashboard/DATA_UPDATE.md`, `dashboard/context-notes.md`, `dashboard/checklist.md` 를 순서대로 읽는다.
3. `python3 dashboard/verify_data.py` — 통과해야 작업 시작. **실패하면 위반 항목을 전부 고친 뒤 다시 실행**. 통과 안 하면 아무 코드도 건드리지 마라.
4. `checklist.md` 의 첫 pending 항목을 in_progress 로 옮기고 시작한다.

## 불변 규칙 (실제 겪은 실수에서 유래)
- **입결 등급 방향**: 등급 숫자가 작을수록 '높음/우수'. 1.0 최상, 9.0 최하. 차트·정렬·문구에서 절대 뒤집지 마라. 상세: `memory/ipsi-grade-direction-rule.md`.
- **연도 프레임**: 입결·경쟁률·추합은 2026 vs 2025 / 모집인원·수능최저 변화는 2027 vs 2026. 인사이트는 2027 vs 2026 프레임 고정. 섞지 마라.
- **`(외)` 표기 금지**: 학과명에 `(외)` 잔존하면 안 됨. 정원 외 채용조건형은 `semiconductor_contract` 카테고리 + 🔗 배지로 노출. 상세: `memory/ipsi-semiconductor-contract.md`.
- **입결 컷 필터 표현**: "이하"·"≤" 금지. **"X.X 이내"** 로만 표기. 상세: `memory/ipsi-cut-filter.md`.
- **한국어 문장 종결**: 콜론(:)으로 끝내지 마라. 마침표/물음표/느낌표만.
- **수정 범위**: 원인을 찾으면 **그 데이터를 쓰는 소비처를 전수 열거**하고 각각 판정하라. 버그가 보인 곳만 고치면 재발한다(std24가 40여 일 미수집이었던 이유). 상세: `memory/ipsi-fix-scope-rule.md`.

## 데이터 갱신 (엑셀 새 버전 도착 시)
`dashboard/DATA_UPDATE.md` 런북을 그대로 따른다. 즉석 diff 스크립트를 다시 짜지 말고 `python3 verify_data.py --diff <이전>` 을 재사용.

## 커뮤니케이션
- 배포는 자동 승인(2026-08-10 사용자 지시 "앞으로 배포는 전부 자동 승인") — 하네스 통과·검증 완료 후 커밋과 함께 푸시한다. 커밋은 논리 단위마다 즉시.
- UI 변경은 preview_start 후 preview_eval 로 렌더 상태 확인 → 스크린샷 저장 → 커밋.
- 정보 소스가 불확실하면 WebSearch/WebFetch 로 근거 확보 후 발언.

## 새 세션 첫 프롬프트 (사용자가 복사 붙여넣기)
```
이 프로젝트 재개. 아래 순서 따라.
1. dashboard/CLAUDE.md → context-notes.md → checklist.md 읽기.
2. 메모리 ipsi-* 전부 확인.
3. `cd dashboard && python3 verify_data.py` 통과 확인.
4. checklist.md 남은 항목 중 우선순위대로 in_progress 표시하고 착수.
```
