# 데이터(data.js·insights.js·apply_dates.js) ↔ 프런트(app.js·index.html) 노출 전수 대조 하네스
# 사용법: python3 verify_frontend.py            # 요약(위반만)
#         python3 verify_frontend.py --detail   # 필드별 전체 + 결측률 표
"""
왜 필요한가 — 데이터를 아무리 정확히 모아도 프런트가 안 뿌리면 사용자에겐 없는 값이다.
verify_data/verify_insights 는 '데이터가 맞는가'를 보고, 이 하네스는 '그 데이터가 화면에
도달하는가'를 본다. 양방향으로 본다 — 수집했는데 미노출 / 화면이 찾는데 데이터·DOM 부재.

🚨 **필드 도달 판정은 신뢰하지 마라 — probe_fields.js 를 쓸 것.**
   변이 테스트(렌더 코드를 일부러 지우고 잡는지 확인) 결과 이 정적 분석은 **미탐 7/10**이었다.
   bullets 렌더를 통째로 막아도, index.html에서 DOM 앵커를 삭제해도 통과시켰다. 이유는 원리적이다 —
   텍스트 매칭은 (a) 조건 게이트(`if (false)`), (b) 동명 필드(cats.label vs row.label),
   (c) 다중 참조 중 하나만 남은 경우를 구분하지 못한다.
   같은 변이를 실행 기반 probe_fields.js 는 6건 중 5건 잡았다.
   → 필드가 화면에 나오는지는 `node probe_fields.js` 로 판정한다.
   → 이 스크립트는 실행 기반이 못 보는 것만 담당한다: 인사이트 order 정합, 접수일 키,
     DOM 앵커 존재, 표시 잘림의 원문 복구 경로, 결측률.

⚠️ 정적 분석의 한계 두 가지를 오탐으로 겪었다(2026-08-21). 아래처럼 보정돼 있다.
  1) 리네임 출력 — std25 는 화면에 `g.b25` 로 이름이 바뀌어 나간다("기준상이 (A → B)").
     속성명만 찾으면 '미노출'로 오판하므로 RENAMED 에 등록해 예외 처리한다.
  2) 동적 id — toast 는 el.id = 'toast' 로 생성된다. id="..." 문자열만 찾으면 '앵커 없음'
     으로 오판하므로 .id = '...' 대입도 함께 본다.
조건부 렌더의 실제 도달 가능성까지는 정적으로 판정할 수 없다 — REVIEW 로 남겨 사람이 본다.
"""
import json, re, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = open(os.path.join(HERE, 'app.js'), encoding='utf-8').read()
HTML = open(os.path.join(HERE, 'index.html'), encoding='utf-8').read()
DETAIL = '--detail' in sys.argv

CODE = re.sub(r'/\*[\s\S]*?\*/', '', APP)
CODE = re.sub(r'(?m)^\s*//.*$', '', CODE)
# 화면 출력 경로 = 템플릿 리터럴 ${...} + textContent/innerHTML 대입
OUT = ' '.join(re.findall(r'\$\{([^}]*)\}', CODE)) + ' ' + \
      ' '.join(re.findall(r'(?:textContent|innerHTML)\s*=\s*([^;]{0,300})', CODE))

# 간접 출력 추적 — 필드를 중간 변수에 담았다가 그 변수를 렌더하는 패턴을 한 단계 따라간다.
#   const tags = (d.tags||[]).map(...)  →  ${tags}
#   const ol = bulletize(d.oneLine)     →  ${esc(ol.head)}
# 이 한 단계가 없으면 oneLine·sections·verdict·text·tags·rows·parent 가 전부 '로직 전용'
# 으로 오판된다(2026-08-21 실측 8건 오탐). 확인 결과 전부 화면에 나오고 있었다.
_INDIRECT = {}
for var, expr in re.findall(r'(?:const|let)\s+(\w+)\s*=\s*([^;\n]{0,200})', CODE):
    if re.search(rf'\$\{{[^}}]*\b{re.escape(var)}\b', CODE) or f'{var}Html' in CODE:
        for fld in re.findall(r'\.(\w+)\b', expr):
            _INDIRECT.setdefault(fld, var)
# 변수가 다시 변수를 거치는 2단계(ol → oneLineHtml → ${oneLineHtml})까지 인정
for var, expr in re.findall(r'(?:const|let)\s+(\w+)\s*=\s*([^;\n]{0,300})', CODE):
    if re.search(rf'\$\{{[^}}]*\b{re.escape(var)}\b', CODE):
        for inner in re.findall(r'\b(\w+)\.\w+', expr):
            for fld, v in list(_INDIRECT.items()):
                if v == inner:
                    _INDIRECT[fld] = var

# 배열로 묶여 이름이 바뀌는 필드 → 프런트에서 쓰는 이름
ALIAS = {'c26': 'c', 'c25': 'c', 'c24': 'c', 'g26': 'g', 'g25': 'g', 'g24': 'g',
         'v26': 'v', 'v25': 'v', 'v24': 'v',
         'chung26': 'chung', 'chung25': 'chung', 'chung24': 'chung'}
# 화면에 다른 이름으로 출력되는 필드 → (출력 시 이름, 근거)
RENAMED = {'std25': ('b25', 'verdict()가 b25로 넘겨 "기준상이 (A → B)" 문구에 출력'),
           'std26': ('b26', '동일 경로 + 기준 배지')}

fails, reviews = [], []


def dump(expr):
    out = subprocess.run(['node', '-e',
        "global.window={};require('./data.js');require('./insights.js');require('./apply_dates.js');"
        f"process.stdout.write(JSON.stringify({expr}))"],
        capture_output=True, text=True, cwd=HERE)
    if out.returncode != 0:
        raise SystemExit('ERROR: node 덤프 실패\n' + out.stderr)
    return json.loads(out.stdout)


def n_ref(name, blob=CODE):
    return len(re.findall(rf'\.{re.escape(name)}\b', blob)) + \
           len(re.findall(rf"\['{re.escape(name)}'\]", blob))


def audit(label, fields, alias=None, soft=False):
    """soft=True 면 미참조를 실패가 아니라 확인 권장으로 낸다.
    meta 처럼 화면 표시용이 아닌 메타데이터가 그렇다 — years 는 verify_data.py 가
    불변식(cur==2027)으로 쓰므로 '화면에 안 나온다'는 이유로 지우면 안 된다."""
    alias = alias or {}
    rows = []
    for f in fields:
        probe = alias.get(f, f)
        ref, out = n_ref(probe), n_ref(probe, OUT)
        if out == 0 and f in RENAMED:
            alt, why = RENAMED[f]
            out = n_ref(alt, OUT)
            if out:
                rows.append(('OK', f, f'참조 {ref} · 출력 {out}(→{alt}) — {why}'))
                continue
        if ref == 0:
            rows.append(('REVIEW' if soft else 'MISS', f,
                         '참조 0회 — ' + ('메타데이터(하네스용일 수 있음)' if soft else '수집했으나 프런트가 안 씀')))
            (reviews if soft else fails).append((label, f, '참조 0회'))
        elif out == 0 and probe in _INDIRECT:
            rows.append(('OK', f, f'참조 {ref} · 간접 출력(→{_INDIRECT[probe]} 변수 경유)'))
        elif out == 0:
            rows.append(('REVIEW', f, f'참조 {ref} · 화면 출력 0 — 로직 전용(필터·정렬·계산)'))
            reviews.append((label, f, '로직 전용'))
        else:
            rows.append(('OK', f, f'참조 {ref} · 출력 {out}'))
    show = rows if DETAIL else [r for r in rows if r[0] != 'OK']
    print(f'\n=== {label} ({len(fields)}) ===')
    for st, n, note in (show or [('OK', '전체', '모두 화면 도달')]):
        print(f"  {{'OK':'✓','MISS':'✗','REVIEW':'?'}}"[0] and
              {'OK': '  ✓', 'MISS': '  ✗', 'REVIEW': '  ?'}[st], f'{n:12s} {note}')


# ---------------------------------------------------------------- 1) data.js
schema = dump('window.IPSI.schema')
dec = re.search(r'const ROWS = D\.rows\.map\([\s\S]*?\n\}\)\);', CODE)
dec_src = dec.group(0) if dec else ''
# ⚠️ 예전 정규식 `(\w+): (?:dc\.\w+\[)?r\[(\d+)\]` 은 38개 중 24개만 봤다.
#    배열(`c: [r[16], r[17], r[18]]`)과 삼항(`std26: dc.std ? (dc.std[r[35]]||'') : ''`)에서 끊겨
#    **연도별 3개조 12개 + std 2개가 통째로 미검사**였다. 하필 연도가 핵심인 필드들이다.
#    실증: c/g/v 의 연도 순서를 뒤집어 2026 자리에 2024가 오게 해도 이 검사도, 실행 프로브도
#    통과했다(프로브는 '어디에 나오는가'만 보고 '올바른 자리인가'는 안 본다).
#    그래서 key: value 쌍을 통째로 떠서 value 안의 r[N] 을 **순서대로** 스키마와 대조한다.
#    ⚠️ 배열을 `\[[^\]]*\]` 로 잡으면 `[r[16], r[17], r[18]]` 이 `r[16` 에서 끊긴다(중첩 대괄호).
#       그래서 key 위치로 구간을 나눠 value 를 통째로 뜬다.
YEARS = ['26', '25', '24']
seen_idx = set()
_keys = [(m.group(1), m.start(), m.end()) for m in re.finditer(r'(?m)(?:^|[,{]\s*)(\w+)\s*:', dec_src)]
_pairs = []
for n, (key, _s, e) in enumerate(_keys):
    end = _keys[n + 1][1] if n + 1 < len(_keys) else len(dec_src)
    _pairs.append((key, dec_src[e:end]))
for key, val in _pairs:
    idxs = [int(x) for x in re.findall(r'r\[(\d+)\]', val)]
    if not idxs:
        continue
    seen_idx.update(idxs)
    if len(idxs) == 1:
        i = idxs[0]
        exp = schema[i] if i < len(schema) else '(범위밖)'
        if key != exp and ALIAS.get(exp) != key:
            fails.append(('디코드', key, f'r[{i}] → SCHEMA는 {exp}'))
    else:
        # 배열로 묶인 연도 3개조 — 위치가 곧 연도다. 뒤바뀌면 2024 값이 2026 자리에 온다.
        for k, i in enumerate(idxs):
            exp = schema[i] if i < len(schema) else '(범위밖)'
            want = f'{key}{YEARS[k]}' if k < len(YEARS) else f'{key}?{k}'
            if exp != want:
                fails.append(('디코드', f'{key}[{k}]', f'r[{i}]={exp} 인데 {want} 자리 — 연도 뒤바뀜'))
miss_idx = sorted(set(range(len(schema))) - seen_idx)
if miss_idx:
    fails.append(('디코드', '미검사 인덱스', f'{[schema[i] for i in miss_idx]} — 디코드 파싱이 놓쳤다'))
audit('data.js SCHEMA', schema, ALIAS)
audit('cats', dump('Object.keys(window.IPSI.cats[0])'))
# window.IPSI.meta 는 감사 대상이 아니었다 — insights meta 와 이름만 같은 다른 객체다.
audit('data.js meta', dump('Object.keys(window.IPSI.meta)'), soft=True)

# ---------------------------------------------------------------- 2) insights.js
def ins_keys(path):
    return dump(f"""(()=>{{const s=new Set();for(const u of Object.values(window.IPSI_INSIGHTS.unis)){path};return [...s]}})()""")

audit('insights uni', ins_keys('Object.keys(u).forEach(k=>s.add(k))'))
audit('insights section', ins_keys('(u.sections||[]).forEach(x=>Object.keys(x).forEach(k=>s.add(k)))'))
audit('insights row', ins_keys('(u.sections||[]).forEach(x=>(x.rows||[]).forEach(r=>Object.keys(r).forEach(k=>s.add(k))))'))
audit('insights verdict', ins_keys('(u.verdict||[]).forEach(v=>Object.keys(v).forEach(k=>s.add(k)))'))
audit('insights meta', dump('Object.keys(window.IPSI_INSIGHTS.meta)'))

# ---------------------------------------------------------------- 3) 키 정합
cov = dump("""(()=>{const D=window.IPSI,I=window.IPSI_INSIGHTS,A=window.IPSI_APPLY||{};
 const u=new Set(D.dicts.uni),k=Object.keys(I.unis);
 return {orderMiss:k.filter(x=>!I.order.includes(x)),orderGhost:I.order.filter(x=>!I.unis[x]),
  insOrphan:k.filter(x=>!u.has(x)),apOrphan:Object.keys(A).filter(x=>!u.has(x)),
  apN:Object.keys(A).length,catNone:0};})()""")
print('\n=== 키 정합 ===')
for key, label, hard in [('orderMiss', 'order 누락(레일 미표시)', True),
                         ('orderGhost', 'order 유령(본문 없음)', True),
                         ('insOrphan', '인사이트 키가 대학명이 아님', False),
                         ('apOrphan', '접수일 키가 데이터에 없음', True)]:
    v = cov[key]
    if v and hard:
        fails.append(('키정합', label, f'{len(v)}건 {v[:5]}'))
        print(f'  ✗ {label}: {len(v)}건 → {v[:5]}')
    elif v:
        reviews.append(('키정합', label, f'{len(v)}건 — 이슈·특집 항목이면 정상'))
        print(f'  ? {label}: {len(v)}건 → {v[:6]} (이슈·특집은 정상)')
    else:
        print(f'  ✓ {label}: 0건')
print(f"  ✓ 접수일 수집 {cov['apN']}교")

# ---------------------------------------------------------------- 3.5) 접수일 값 구조
# ⚠️ 키(대학명)만 보면 값이 통째로 깨져도 통과한다. 실증: from/to/via 를 start/end/src 로
#    리네임하니 164교 전부 접수일이 사라졌는데 하네스는 OK 를 냈다.
#    원서접수 마감 시각은 틀리면 가장 치명적인 값이고, fetch_apply_dates.py 를 접수 주간
#    직전에 다시 돌리기로 돼 있다 — 그때 구조가 바뀌면 여기서 잡아야 한다.
ap = dump("""(()=>{const A=window.IPSI_APPLY||{};const need=['from','to','via'];
 const bad=[],badDate=[];
 for(const [k,v] of Object.entries(A)){
   if(!v||typeof v!=='object'){bad.push(k);continue;}
   if(need.some(f=>!(f in v)||!String(v[f]||'').trim())){bad.push(k);continue;}
   if(isNaN(Date.parse(v.from))||isNaN(Date.parse(v.to))) badDate.push(k);
 }
 return {n:Object.keys(A).length, bad:bad.slice(0,6), nBad:bad.length,
         badDate:badDate.slice(0,6), nBadDate:badDate.length};})()""")
print('\n=== 접수일 값 구조 ===')
if ap['nBad']:
    fails.append(('접수일', 'from/to/via 누락', f"{ap['nBad']}교 {ap['bad']}"))
    print(f"  ✗ from/to/via 누락 {ap['nBad']}교 → {ap['bad']}")
elif ap['nBadDate']:
    fails.append(('접수일', '날짜 파싱 불가', f"{ap['nBadDate']}교 {ap['badDate']}"))
    print(f"  ✗ 날짜 파싱 불가 {ap['nBadDate']}교 → {ap['badDate']}")
else:
    print(f"  ✓ {ap['n']}교 전부 from/to/via 보유 · 날짜 파싱 정상")

# ---------------------------------------------------------------- 4) DOM 앵커
ids_html = set(re.findall(r'id="([^"]+)"', HTML))
ids_made = set(re.findall(r'id="([\w-]+)"', CODE)) | set(re.findall(r"\.id\s*=\s*'([\w-]+)'", CODE))
# ⚠️ `$('#x')` 와 getElementById 만 보면 querySelector('#x') 4곳을 통째로 놓친다.
#    그중 #cutFilter 는 index.html 에 있는 외부 앵커라, 지워지면 app.js 가 `if (!box) return`
#    으로 조용히 빠져나가 입결 컷·고사시기 필터가 콘솔 에러 없이 증발한다.
ids_app = (set(re.findall(r"\$\('#([\w-]+)'\)", CODE))
           | set(re.findall(r"getElementById\(['\"]([\w-]+)['\"]\)", CODE))
           | set(re.findall(r"querySelector\(\s*['\"]#([\w-]+)['\"]", CODE)))
orphan = sorted(ids_app - ids_html - ids_made)
print('\n=== DOM 앵커 ===')
if orphan:
    fails.append(('DOM', '앵커 없음', str(orphan)))
    print(f'  ✗ HTML에도 없고 생성도 안 되는 앵커 {len(orphan)}건 → {orphan}')
else:
    print(f'  ✓ app.js 참조 {len(ids_app)}개 전부 존재(정적 {len(ids_app & ids_html)} · 동적 {len(ids_app & ids_made)})')

# ---------------------------------------------------------------- 5) 잘림 — 원문 복구 경로 확인
print('\n=== 표시 잘림 ===')
# 문자열 필드에서 파생된 지역변수(예: const jn = r.jhname.replace(...))도 잘림 검사 대상에 넣는다.
STR_VAR = {v: src for v, src in re.findall(r'(?:const|let)\s+(\w+)\s*=\s*r\.(\w+)\.replace\(', CODE)}
# ⚠️ 배열 개수 제한(v.sig.slice(0,2) 같은 것)은 문자열 잘림이 아니다. .map(/.forEach( 가 뒤따르면 배열로 본다.
# ⚠️ `.slice(0,N)` 만 보면 헬퍼로 감싼 잘림을 놓친다. cut(r.dept, 16) 같은 형태도 대상이다.
#    (실제로 dept 잘림을 cut() 으로 리팩터하자 검사 대상에서 조용히 빠졌다.)
_slices = [(m.group(1), m.group(2), m.group(0), m.start())
           for m in re.finditer(r'\b(?:r\.)?(\w+)\.slice\(0,\s*(\d+)\)', CODE)]
_slices += [(m.group(1), m.group(2), m.group(0), m.start())
            for m in re.finditer(r'\bcut\(\s*(?:r\.)?(\w+)\s*,\s*(\d+)\s*\)', CODE)]
for f, n, whole, pos in sorted(_slices, key=lambda x: x[3]):
    class _M:                                       # finditer 결과처럼 쓰기 위한 얇은 래퍼
        def __init__(self, s, w): self._s, self._w = s, w
        def start(self): return self._s
        def end(self): return self._s + len(self._w)
    m = _M(pos, whole)
    if not (whole.startswith('r.') or whole.startswith('cut(') or f in STR_VAR):
        continue                                   # 문자열 필드 유래가 아니면 건너뛴다
    tail = CODE[m.end():m.end() + 40]
    if re.match(r'\s*\.(?:map|forEach|filter|join)\b', tail):
        continue                                   # 배열 개수 제한
    # ⚠️ 줄번호는 반드시 원본(APP) 기준으로 낸다. 주석 제거본(CODE) 기준이면 실제 위치와
    #    어긋나 엉뚱한 줄을 고치게 된다(2026-08-21 L1115로 보고됐으나 실제는 L1177).
    hit = re.search(re.escape(whole), APP)
    line = APP[:hit.start()].count('\n') + 1 if hit else 0
    src = STR_VAR.get(f, f)                        # 파생 변수면 원본 필드명으로 환원
    # ⚠️ 앞뒤 320자 '창'으로 title 을 찾으면 이웃 요소의 title 이 새어 들어온다(실증: jn 의
    #    title 을 지워도 옆 반도체 배지 title 때문에 통과했다). slice 가 속한 태그 안만 본다.
    tag_start = CODE.rfind('<', max(0, m.start() - 400), m.start())
    seg = CODE[tag_start:m.start()] if tag_start >= 0 else ''
    has_title = bool(re.search(rf'title="\$\{{esc\((?:r\.)?{re.escape(f)}\)\}}"', seg)
                     or re.search(r'title="\$\{esc\(', seg))
    # ⚠️ full 을 파일 전역에서 찾으면 인쇄 전용 표(모달이 인쇄에서 display:none)까지
    #    '모달에서 전체 표시'로 통과시킨다. 같은 함수 본문 안에서만 복구 경로를 인정한다.
    fn_start = max(CODE.rfind('\nfunction ', 0, m.start()), CODE.rfind('\nconst ', 0, m.start()))
    fn_end = CODE.find('\nfunction ', m.start())
    body = CODE[fn_start if fn_start > 0 else 0: fn_end if fn_end > 0 else len(CODE)]
    full = bool(re.search(rf'\$\{{esc\(r\.{src}\)\}}', body) or
                (src == 'dept' and re.search(r'\$\{esc\(deptDisp\(r\)\)\}', body)))
    note = 'title 툴팁으로 원문 보존' if has_title else ('모달·상세에서 전체 표시' if full else '⚠ 원문 확인 경로 없음')
    st = '✓' if (has_title or full) else '✗'
    if st == '✗':
        fails.append(('잘림', f'{src}@L{line}', '원문 확인 경로 없음'))
    label = src if src == f else f'{src}(→{f})'
    print(f'  {st} {label} {n}자 (L{line}) — {note}')

# ---------------------------------------------------------------- 6) 결측률(참고)
if DETAIL:
    miss = dump("""(()=>{const D=window.IPSI,S=D.schema,R=D.rows,N=R.length,dc=D.dicts;
      const num=['enroll','c26','g26','v26'],out={};
      for(const f of num){const k=S.indexOf(f);out[f]=+(R.filter(r=>r[k]==null).length/N*100).toFixed(1);}
      for(const [f,d] of [['choejeo','choejeo'],['note','note'],['date','date'],['change','change'],['std26','std']]){
        const k=S.indexOf(f);out[f]=+(R.filter(r=>!(dc[d][r[k]]||'').trim()).length/N*100).toFixed(1);}
      return out;})()""")
    print('\n=== 결측률(원천 데이터 · 화면엔 "–"로 표시) ===')
    for f, p in miss.items():
        print(f'  {f:10s} {p:5.1f}%')

# ---------------------------------------------------------------- 결론
print()
if fails:
    print(f'미노출·불일치 {len(fails)}건:')
    for src, f, note in fails:
        print(f'  ✗ [{src}] {f} — {note}')
if reviews:
    print(f'확인 권장 {len(reviews)}건:')
    for src, f, note in reviews:
        print(f'  ? [{src}] {f} — {note}')
if not fails:
    print('OK  키 정합·DOM 앵커·잘림 검사 통과')
print('※ 필드 도달 판정은 이 스크립트를 믿지 말 것 — 정적 분석은 변이 테스트에서 미탐 7/10.')
print('  화면 도달은 실행 기반으로: node probe_fields.js')
sys.exit(1 if fails else 0)
