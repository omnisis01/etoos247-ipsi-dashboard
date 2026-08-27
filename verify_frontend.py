# 데이터(data.js·insights.js·apply_dates.js) ↔ 프런트(app.js·index.html) 노출 전수 대조 하네스
# 사용법: python3 verify_frontend.py            # 요약(위반만)
#         python3 verify_frontend.py --detail   # 필드별 전체 + 결측률 표
"""
왜 필요한가 — 데이터를 아무리 정확히 모아도 프런트가 안 뿌리면 사용자에겐 없는 값이다.
verify_data/verify_insights 는 '데이터가 맞는가'를 보고, 이 하네스는 '그 데이터가 화면에
도달하는가'를 본다. 양방향으로 본다 — 수집했는데 미노출 / 화면이 찾는데 데이터·DOM 부재.

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


def audit(label, fields, alias=None):
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
            rows.append(('MISS', f, '참조 0회 — 수집했으나 프런트가 안 씀'))
            fails.append((label, f, '참조 0회'))
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
for name, i in re.findall(r'(\w+)\s*:\s*(?:dc\.\w+\[)?r\[(\d+)\]', dec_src):
    i = int(i)
    exp = schema[i] if i < len(schema) else '(범위밖)'
    if name != exp and ALIAS.get(exp) != name:
        fails.append(('디코드', name, f'r[{i}] → SCHEMA는 {exp}'))
audit('data.js SCHEMA', schema, ALIAS)
audit('cats', dump('Object.keys(window.IPSI.cats[0])'))

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

# ---------------------------------------------------------------- 4) DOM 앵커
ids_html = set(re.findall(r'id="([^"]+)"', HTML))
ids_made = set(re.findall(r'id="([\w-]+)"', CODE)) | set(re.findall(r"\.id\s*=\s*'([\w-]+)'", CODE))
ids_app = set(re.findall(r"\$\('#([\w-]+)'\)", CODE)) | set(re.findall(r"getElementById\('([\w-]+)'\)", CODE))
orphan = sorted(ids_app - ids_html - ids_made)
print('\n=== DOM 앵커 ===')
if orphan:
    fails.append(('DOM', '앵커 없음', str(orphan)))
    print(f'  ✗ HTML에도 없고 생성도 안 되는 앵커 {len(orphan)}건 → {orphan}')
else:
    print(f'  ✓ app.js 참조 {len(ids_app)}개 전부 존재(정적 {len(ids_app & ids_html)} · 동적 {len(ids_app & ids_made)})')

# ---------------------------------------------------------------- 5) 잘림 — 원문 복구 경로 확인
print('\n=== 표시 잘림 ===')
for m in re.finditer(r'r\.(\w+)\.slice\(0,\s*(\d+)\)', CODE):
    f, n = m.group(1), m.group(2)
    line = CODE[:m.start()].count('\n') + 1
    seg = CODE[max(0, m.start() - 200):m.start() + 60]
    has_title = f'title="${{esc(r.{f})}}"' in seg
    full = re.search(rf'\$\{{esc\(r\.{f}\)\}}', CODE) or re.search(rf'\$\{{esc\(deptDisp\(r\)\)\}}', CODE) if f == 'dept' else None
    note = 'title 툴팁으로 원문 보존' if has_title else ('모달·상세에서 전체 표시' if full else '⚠ 원문 확인 경로 없음')
    st = '✓' if (has_title or full) else '✗'
    if st == '✗':
        fails.append(('잘림', f'{f}@L{line}', '원문 확인 경로 없음'))
    print(f'  {st} {f} {n}자 (L{line}) — {note}')

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
    print('OK  수집한 데이터가 전부 프런트 화면에 도달함')
sys.exit(1 if fails else 0)
