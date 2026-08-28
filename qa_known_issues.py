# 2026-08-28 운용 중 발견된 3건의 회귀 테스트 — 고치기 전엔 실패, 고친 뒤엔 통과해야 한다
# 사용법: python3 qa_known_issues.py
"""
사용자가 실사용 중 잡은 문제를 재현 가능한 형태로 굳혀 둔다. 진단만 하고 넘어가면
다음 세션이 "고쳐졌는지" 알 수 없고, 고친 뒤에도 회귀를 못 잡는다.

지금 상태(미수정)에서는 3건 모두 FAIL 이 정상이다.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(HERE, '..', '입결 및 인사이트',
                    'TongTongTong_2027학년도 수시지원의 모든 것_Final오타 수정 필요.xlsx')

def dump(expr):
    out = subprocess.run(['node', '-e',
        "global.window={};require('./data.js');"
        f"process.stdout.write(JSON.stringify({expr}))"],
        capture_output=True, text=True, cwd=HERE)
    if out.returncode != 0:
        raise SystemExit('node 덤프 실패\n' + out.stderr)
    return json.loads(out.stdout)

fails = []

# ---------------------------------------------------------------- ① 복수 숫자 모집인원
# 원본 엑셀 col8 에 "인:80\n자:40" 처럼 숫자가 둘 이상 든 행이 있고, num() 이 첫 숫자만 읽어
# 나머지가 사라진다(원본 14행 중 7행은 교정 완료, 미교정 6행 58명). 엑셀이 있을 때만 검사한다.
print('=== ① 모집인원 복수 숫자 (원본 대조) ===')
if not os.path.exists(XLSX):
    print('  - 원천 엑셀 없음 → SKIP')
else:
    import openpyxl
    # ⚠️ 원본·산출물 모두 학과명에 줄바꿈이 섞여 있어 그대로 비교하면 매칭이 실패한다
    #    (실측: 한양대(ERICA) 국방지능정보융합 1행을 놓쳤다). 공백을 지우고 맞춘다.
    norm = lambda x: re.sub(r'\s+', '', str(x or ''))
    ws = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)['전체']
    raw = {}
    for r in ws.iter_rows(min_row=4, values_only=True):
        v = r[8]
        if v is None or isinstance(v, (int, float)):
            continue
        nums = re.findall(r'\d+', str(v).replace(',', ''))
        if len(nums) > 1:
            raw[(norm(r[2]), norm(r[4]), norm(r[5]), norm(r[6]))] = \
                (sum(int(x) for x in nums), int(nums[0]), str(v).replace('\n', ' / '))
    print(f'  원본에서 숫자 2개 이상인 행: {len(raw)}건')
    D = dump('window.IPSI')
    S, dc = D['schema'], D['dicts']
    iu, idp, ijt, ijn, ie = (S.index(x) for x in ('uni', 'dept', 'jhtype', 'jhname', 'enroll'))
    built = {}
    for r in D['rows']:
        built[(norm(dc['uni'][r[iu]]), norm(dc['dept'][r[idp]]), norm(r[ijt]), norm(dc['jhname'][r[ijn]]))] = r[ie]
    # ⚠️ 원본만 보고 규모를 재면 안 된다 — data_corrections.json 이 이미 절반을 잡아 뒀다.
    #    (실측: 14행 중 7행은 교정 완료. 원본만 보고 '14행 113명'이라 오판한 적이 있다.)
    bad, already, nomatch = [], [], []
    for k, (total, first, txt) in raw.items():
        got = built.get(k)
        if got is None:
            nomatch.append((k, txt, total))
        elif got == first and total != first:
            bad.append((k, txt, first, total))
        else:
            already.append((k, txt, got, total))
    print(f'  이미 교정됨 {len(already)}행 · 미교정 {len(bad)}행 · 키 매칭 실패 {len(nomatch)}행')
    for k, txt, tot in nomatch:
        print(f'  ? {k[0][:12]} {k[1][:20]} [{txt[:20]}] 합 {tot} — 키 매칭 실패, 수동 확인')
    for (u, d, t, j), txt, first, total in bad:
        print(f'  ✗ {u} {d[:18]} [{t}] 원문[{txt[:24]}] → {first} (정답 후보 {total})')
    if bad:
        fails.append(f'복수 숫자 모집인원 {len(bad)}행 — 첫 숫자만 반영됨 '
                     f'(누락 {sum(t - f for _, _, f, t in bad)}명)')
    else:
        print('  ✓ 복수 숫자 행이 전부 처리됨')

# ---------------------------------------------------------------- ② 약칭 검색
# ⚠️ 2026-08-28 교훈 — 이 검사를 처음 짤 때 app.js 의 expandToken() 을 재현하지 않고
#    원문 매칭만 해서 '진주교대·서울여대 0건'이라는 **가짜 결함**을 만들었다.
#    실제 앱은 '교대$→교육대', '여대→여자' 확장을 이미 하고 있었다.
#    그래서 규칙을 하드코딩하지 않고 **app.js 에서 함수 본문을 그대로 떠다 실행**한다.
#    앱이 규칙을 고치면 이 검사도 자동으로 따라간다.
print('\n=== ② 약칭 검색 ===')
D = dump('window.IPSI')
S, dc = D['schema'], D['dicts']
iu, idp, ijn, ir, ijt, isg, ig = (S.index(x) for x in
                                 ('uni', 'dept', 'jhname', 'region', 'jhtype', 'sigun', 'gye'))
def hay(r):
    return (dc['uni'][r[iu]] + ' ' + dc['dept'][r[idp]] + ' ' + dc['jhname'][r[ijn]] + ' ' +
            dc['region'][r[ir]] + ' ' + r[ijt] + ' ' + dc['sigun'][r[isg]] + ' ' + r[ig]).lower()
HAYS = [hay(r) for r in D['rows']]
APP_SRC = open(os.path.join(HERE, 'app.js'), encoding='utf-8').read()
_m = re.search(r'const expandToken = (t => t[\s\S]*?);\n', APP_SRC)
if not _m:
    raise SystemExit('app.js 에서 expandToken 을 찾지 못했다 — 검색 확장 규칙 위치가 바뀌었는지 확인하라')
EXPAND_SRC = _m.group(1)

def expand_many(tokens):
    """app.js 의 expandToken 을 node 로 실제 실행해 확장 결과를 받는다."""
    js = f'const f = {EXPAND_SRC}; process.stdout.write(JSON.stringify({json.dumps(tokens)}.map(f)))'
    out = subprocess.run(['node', '-e', js], capture_output=True, text=True, cwd=HERE)
    if out.returncode != 0:
        raise SystemExit('expandToken 실행 실패\n' + out.stderr)
    return json.loads(out.stdout)

def count(q, expanded):
    return sum(1 for h in HAYS if all(t in h for t in expanded))

ALIASES = ['진주교대', '서울교대', '경인교대', '서울여대', '숙명여대', '이대',
           '한국외대', '카이스트', '포스텍', '서울과기대', '한기대']
miss = []
_exp = expand_many([a.lower() for a in ALIASES])
for q, e in zip(ALIASES, _exp):
    n = count(q, [e])
    print(f'  {"✓" if n else "✗"} "{q}" → {n}건  (확장: {e})')
    if not n:
        miss.append(q)
if miss:
    fails.append(f'약칭 검색 {len(miss)}건 0건 — {miss}')

# ---------------------------------------------------------------- ③ 대학 패널 캠퍼스 구분
# uniPanel 이 r.uni 로만 묶어 경북대 대구·상주가 섞인다. app.js 소스로 판정한다.
print('\n=== ③ 대학 패널 캠퍼스 구분 ===')
APP = open(os.path.join(HERE, 'app.js'), encoding='utf-8').read()
m = re.search(r'box\.innerHTML = \w+\.map\(\w+ => uniPanelHTML\(\w+, FILTERED\.filter\(([^)]*)\)', APP)
if m and 'campus' not in m.group(1):
    print(f'  ✗ 패널이 캠퍼스를 무시하고 묶는다 — filter({m.group(1).strip()})')
    knu = [r for r in D['rows'] if dc['uni'][r[iu]] == '경북대학교']
    sang = [r for r in knu if dc['sigun'][r[isg]] == '상주']
    print(f'     경북대 {len(knu)}행 중 상주 {len(sang)}행이 대구캠과 한 덩어리로 표시됨')
    fails.append('대학 패널이 캠퍼스를 구분하지 않음(경북대 대구·상주 혼재)')
elif m:
    print('  ✓ 패널이 캠퍼스를 구분한다')
else:
    print('  ? uniPanel 구성 코드를 찾지 못함 — 구조 변경 확인 필요')


# ---------------------------------------------------------------- ④ 추합 단일 오염
# 대학마다 '충원' 정의가 달라(명/배/%) 계통 차이는 손대지 않는다(checklist 🔒).
# 하지만 **같은 행 3개년 중 하나만 자릿수가 튀는 것**은 정의 차이로 설명되지 않는다 —
# 옆 셀 값이 흘러든 오염이다. 실측: 동아대 사회학 [7, 972, 4] 1행(모집 6명·지원 42명).
print('\n=== ④ 추합 단일 오염 (3개년 중 하나만 자릿수 이탈) ===')
_CH = [S.index(k) for k in ('chung26', 'chung25', 'chung24')]
_out = []
for r in D['rows']:
    vals = []
    for ci in _CH:
        t = str(r[ci] or '')
        if re.fullmatch(r'\d+', t): vals.append(int(t))
    if len(vals) < 3: continue
    mx = max(vals); others = [v for v in vals if v != mx]
    if not others: continue
    om = max(others)
    if mx >= 100 and om > 0 and mx / om >= 15:
        _out.append((mx / om, dc['uni'][r[iu]], dc['dept'][r[idp]][:18], vals))
for ratio, u, d, vals in sorted(_out, reverse=True):
    print(f'  ✗ {u} {d} 3개년 {vals} → {ratio:.0f}배 이탈')
if _out:
    fails.append(f'추합 단일 오염 {len(_out)}행 — data_corrections.json "chung" 채널로 처리하라')
else:
    print('  ✓ 3개년이 함께 크거나 함께 작다(계통 차이만 남음)')

# ---------------------------------------------------------------- 결론
print()
if fails:
    print(f'미해결 {len(fails)}건:')
    for f in fails:
        print('  ✗', f)
    print('\n(2026-08-28 진단 시점에는 3건 모두 미수정이 정상이다. 고친 뒤 이 스크립트가 통과해야 한다.)')
    sys.exit(1)
print('OK  알려진 3건이 모두 해소됨')
