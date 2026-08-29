# 데이터 갱신 런북

새 원천 엑셀(`2027학년도 수시지원의 모든 것 V*.xlsx`)을 받았을 때 따르는 검증 루프.
하네스 원칙 적용 — 매번 즉석 스크립트를 다시 짜지 말고 이 순서를 재사용한다.

## 루프 (V7.24 기준 현행)

```
1. 새 엑셀을 `../입결 및 인사이트/` 폴더에 둔다.
2. 경로 교체 — 두 곳이다. 하나만 바꾸면 하네스가 구버전을 대조한다(실제로 V7.24 승격 때
   verify_insights.py가 V7.15를 계속 보고 있었다).
   · build_data.py 의 SRC + meta.source 버전 라벨
   · verify_insights.py 의 SRC
3. python3 build_data.py
   → 검증: rows/uni 수·카테고리 카운트 급변 없는지 + 교정 리포트 전건 적용인지
     [구분교정] [일자교정] [기준교정] [경쟁률교정] [지역교정] [입결교정] [enroll교정]
   → "미적용 N건 — SystemExit"가 뜨면 아래 '가드가 중단시켰을 때' 절차.
4. python3 verify_data.py && python3 qa_comp_ratio.py && python3 verify_insights.py \
     && node probe_fields.js && python3 verify_frontend.py
   → verify_data: 불변식(stdK 버킷 화이트리스트 포함).
   → qa_comp_ratio: 경쟁률 산술 래칫 — 신규 의심이 늘면 커밋 차단. 교정으로 기존 의심이
     줄었다면 --save-baseline 으로 기준선 갱신(현재 30건).
   → verify_insights: 인사이트 to(새 엑셀)·from(enroll26.json 스냅샷) 양쪽 대조.
     ⚠️ enroll26.json 은 2026 확정 스냅샷이라 엑셀이 갱신돼도 바꾸지 않는다.
   → probe_fields(실행 기반): 그 데이터가 **화면에 도달하는지**. app.js를 최소 DOM 스텁으로
     진짜 돌려(verify_render.js) 필드마다 마커를 주입하고 렌더 결과에서 찾는다.
     필드를 새로 추가했는데 프런트가 안 뿌리면 여기서 잡힌다. 새 필드는 probe_fields.js의
     DATA_FIELDS/INS_FIELDS 에 등재할 것. 숫자 필드는 NUMERIC 에도 등재(문자열 마커는 포맷
     함수가 걸러낸다).
   → verify_frontend(정적): **필드 도달 판정은 믿지 마라.** 변이 테스트에서 미탐 7/10이었다.
     키 정합·DOM 앵커·잘림 원문 복구 경로만 이쪽이 담당한다.
5. git show HEAD:data.js > <scratchpad>/prev_data.js
   python3 verify_data.py --diff <scratchpad>/prev_data.js
   → "의도한 수정"과 diff 가 일치하는지. 뜻밖의 신규/삭제 행이면 중단하고 원인 확인.
6. 미리보기에서 대표 행 1~2개 값 재확인(예: 부산대 치의예 최저).
7. python3 stamp_assets.py   # 캐시 버스팅 — 배포 전 필수(아래 절 참조)
8. git commit → git push. (pre-commit hook 이 4번 하네스를 다시 강제한다)
```

## 가드가 중단시켰을 때 ("미적용 N건 — SystemExit")

교정은 전부 **old 값이 엑셀 원문과 일치할 때만 적용**되고, 미적용이 남으면 빌드가 멈춘다.
이는 오류가 아니라 **엑셀이 그 값을 바꿨다는 신호**다. 항목별로 판정한다.
- 엑셀이 우리 교정과 같은 값으로 고쳤다 → 교정 임무 완료. data_corrections.json 에서 그 항목 제거.
- 엑셀이 또 다른 값으로 바꿨다 → 원 근거(why에 적힌 출처)로 재판정 후 old를 새 원문으로 갱신.
- ⚠️ 가드를 지우거나 --no-verify 로 넘기지 마라. 부경대·공주대 오교정을 배포 전에 잡은 게 이 가드다.

## 교정 타입 (data_corrections.json)

| 타입 | 키 | 대상 | 비고 |
|---|---|---|---|
| enroll/drop/add/rename | (uni,dept,jht,jhn) | 2027 모집인원·행 | 112교 요강 전수 대조 유래 |
| ipgyeol | (uni,dept,jht,jhn) | 2026 입결(g26) | 신설 행에 걸면 무효화 가드가 잡는다 |
| dkind | (uni,dept,jht,jhn)+from | 전년대비 구분 | to='none'이면 prev도 자동 '-' 동기화(인쇄물이 prev를 직접 찍는다) |
| date | (uni,jhn,old) | 대학별고사 일자 | 요일 검산 유래 |
| region | (uni,dept,from_region,from_sigun) | 캠퍼스 | ⚠️ 4키 필수 — 2키 매칭은 멀쩡한 행을 덮는다 |
| std | (uni,from) | 입결 기준 원문 | std26·std25 양쪽에 적용(한쪽만 하면 추세 차단 회귀) |
| comp | (uni,dept,jht,jhn)+old | 2026 경쟁률 | 모집인원 산술로 방향 판정된 것만 |

각 항목의 why에 근거를 반드시 남긴다. 근거 없는 교정은 넣지 않는다.

## stdK 버킷 (입결 기준)

`avg / cut50 / cut70 / cut80(75~85%) / cut90 / lowest(최저=사실상 100%컷) / stage1(1단계·최종지표 아님)`

⚠️ 버킷을 추가·변경하면 **세 곳을 함께** 고친다 — 하나만 바꾸면 verify가 잡는다.
1. build_data.py `std_kind()`  2. verify_data.py allowed 집합  3. app.js `CUT_LABELS`·`CUT_SHORT`·컷 필터 배열

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

## ⚠️ 원천 엑셀의 함정 — 한 칸에 숫자가 여럿

모집인원 칸에 `"인:80\n자:40"`·`"남:15\n여:5"`·`"일반:18\n수상:5"` 처럼 **숫자가 둘 이상**
들어간 행이 있다(2026-08-28 실측 14행). `num()` 은 첫 숫자만 뽑으므로 나머지가 조용히 사라진다.
실제로 서울여대 논술 120명이 80명으로 나왔다.
⚠️ **원본만 보고 규모를 재지 마라.** 14행 중 7행은 `data_corrections.json` 이 이미 잡아 뒀다
(초기에 이걸 무시해 '14행 113명'으로 오판했고, 실제 미교정은 6행 58명이었다).
반드시 산출물 data.js 와 대조할 것 — `python3 qa_known_issues.py` 가 그 대조를 한다.

```bash
# 새 엑셀을 받을 때마다 이 스캔을 돌려라 — 행이 늘거나 새 패턴이 생겼는지 본다
python3 - <<'EOF'
import openpyxl, re
ws = openpyxl.load_workbook('<새 엑셀>', read_only=True, data_only=True)['전체']
for r in ws.iter_rows(min_row=4, values_only=True):
    v = r[8]
    if v is None or isinstance(v, (int, float)): continue
    n = re.findall(r'\d+', str(v).replace(',', ''))
    if len(n) > 1: print(r[2], r[4], r[5], repr(str(v))[:40], n)
EOF
```

합산이 늘 옳은 건 아니다 — 성별 분리는 합산이 맞지만 계열 분리(인/자)는 별도 행으로 쪼개는 게
맞을 수 있다(계열 필터·입결 비교가 갈린다). 패턴별로 판정하고 근거를 남길 것.

## ⚠️ 새 엑셀이 오면 — 컬럼 매핑부터 확인하라

`build_data.py` 가 **읽지 않는 열**이 생기면 그 정보는 통째로 사라진다. 실측(2026-08-28)으로
35열 중 3열이 100% 채워진 채 버려지고 있었다.
- col30 2024학년도 기준 → **std25 는 쓰면서 std24 만 빠져 있었다.** 3개년 입결 추이가
  기준이 다른 값을 이어 그렸다(5,371행·20.3%에서 연도별 기준 상이).
- col14 복수 지원 → 22.2%(5,860행)에 '불가'·'학종 불가'·'3회' 제약이 있는데 화면에 없었다.
- col13 필요 서류 → 추천서 필요 250행 등.

```bash
python3 qa_known_issues.py    # ⑤ 원천 컬럼 사용 여부 — 미사용인데 5% 이상 채워진 열이면 실패
```

## 하네스를 하네스로 검수하기 (변이 테스트)

검사기가 "전부 통과"라고 말할 때가 가장 위험하다. 그 말이 사실인지 확인하려면
**렌더 코드를 일부러 지우고 잡는지** 보면 된다.
실제로 이 방법으로 정적 검사기의 미탐 7/10을 찾아냈다(bullets 렌더·DOM 앵커를 삭제해도 통과).
새 검사기를 만들면 반드시 이 검수를 거칠 것 — 통과 여부가 아니라 **검출력**을 봐야 한다.

## 왜 이렇게 하나 (Ratchet)

각 불변식은 실제 겪은 실패에서 나왔다.
- 입결 범위 — 환산점수가 등급칸에 섞여 9건 이상값 발생 → `vgrade()` 도입.
- 연도 프레임 — 2028 vs 2027 기사를 잘못 받아 롤백한 이력.
- diff 재사용 — V6.29 갱신 때 즉석 diff 스크립트를 두 번 짠 낭비를 `--diff` 로 굳힘.
- 최저 방향 — `3합8→2합5`를 합만 보고 강화로 오판(91전형, 유불리 판정이 반대) → `least_direction()` 집합 비교 + 검증 규칙.
- 인사이트 합계 — 권역별로 쪼갠 행 하나를 전형 총원으로 오기(경북대 지역의사 8 ← 26) → `verify_insights.py` 는 스코프 후 **합계**로만 비교.
- 인사이트 from — to(2027)만 검증하니 2026 오기 6건이 숨어 있었다(한양대 621←616 등) → from 축을 enroll26 스냅샷과 대조.
- 기준 뭉개기 — 75·80·85%컷을 cut70에 합류시켜 어디가 대조에서 229건이 계통 불일치로 오인 → cut80 분리, 버킷 3곳 동기화 규칙.
- 스왑 방향 — '두 값이 정확히 뒤바뀜'만으로 방향을 정했다가 청주대에서 반증(어디가 쪽이 뒤바뀜) → 방향은 모집인원 산술·대학 공식 자료 같은 제3의 근거로만.

## 원서접수 기간 갱신 (접수 주간 전 필수)

```bash
python3 fetch_apply_dates.py   # 진학어플라이 공통 원서검색 → apply_dates.js (155/164교)
```

⚠️ **D-30 부터는 주 1회 재수집하라. '접수 주간 직전 1회'로는 부족하다.**
실측(2026-08-29): 8/11 수집본과 대조하니 **18일 만에 7개교가 바뀌었다** — 공주교대는 시작이
하루 밀리고 마감이 17:00→16:00 으로 **앞당겨졌다**(1시간 일찍 닫힌다). 서울여대는 8/11 수집본에
마감이 `09-11T06:00`(새벽 6시)로 들어 있었다 — 12시간제 파싱 오류이며 재수집으로 18:00 으로 교정됐다.
마감 시각은 원서를 넣는 마지막 순간을 좌우하므로 틀리면 곧바로 지원 실패다.

```bash
python3 qa_known_issues.py   # ⑦ 새벽 마감·주말 마감·시작>마감 + 수집본 신선도 경고
```
조기마감 대학 수가 급변하면 원자료를 눈으로 확인할 것(현재 9교 — SKY·시립대·이대·과기원 4곳).
미커버 9교 = 과기원 5(자체 일정) + 계명대·공주교대·동의대·송원대(유웨이 단독, 집계 미등재).
수집 실패(200건 미만) 시 기존 파일을 보존하고 중단한다.

## 배포 전 필수 — 캐시 버스팅

```bash
python3 stamp_assets.py   # index.html의 styles.css·app.js·data.js 참조에 ?v=<해시> 부여
```

⚠️ **이걸 빼먹으면 배포해도 기존 사용자는 옛 화면을 본다.** index.html이 버전 없이
참조하면 브라우저가 옛 CSS·JS를 계속 쓴다. 실제로 QA 중 서버는 새 파일을 주는데
화면은 옛 CSS로 렌더돼 "수정이 반영 안 된다"고 한참 헤맸다.
해시가 바뀐 파일만 갱신하므로 매번 돌려도 안전하다.
