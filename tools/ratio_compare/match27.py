# 2027 수시 최종 경쟁률 페이지를 우리 행(전형 × 모집단위)에 붙인다 — 결과는 ratio27.json.
#
# 채택 규칙: 전형·학과 매칭(ratio_match, 2026 대조에서 검증된 규칙 그대로)에 더해
#   **페이지 모집인원 == 우리 2027 모집인원(enroll)** 일 때만 c27 로 채택한다.
#   2027 페이지와 2027 요강은 같은 해 자료라 모집인원이 같아야 정상이다. 다르면 행이 어긋났거나
#   1:N 관계라는 신호이므로 버린다(빈칸이 오답보다 낫다).
import os, re, json, collections, sys
import ratio_parse as P
import ratio_match as M

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(os.path.dirname(DASH), '2027_수시경쟁률_원문')

t = open(os.path.join(DASH, 'data.js'), encoding='utf-8').read()
d = json.loads(t[len('window.IPSI = '):-1])
S, D = d['schema'], d['dicts']
DK = {'uni', 'dept', 'jhname'}
rows = [{k: (D[k][v] if k in DK and isinstance(v, int) else v) for k, v in zip(S, r)} for r in d['rows']]
by_uni = collections.defaultdict(list)
for r in rows:
    by_uni[r['uni']].append(r)


# 대행사 페이지가 정본이 아닌 대학 — 값이 맞아 보여도 쓰지 않는다.
EXCLUDE = {
    '창신대학교': '대행사 페이지에 대학 창구 접수분이 빠진다(2026 공식 3,297 vs 대행사 1,240, README ⚠️1). '
                  '2027 도 디지털도시건설 0.30(2026 5.89)처럼 한 자릿수 배율로 작다.',
}


def campus_filter(uni, page):
    """한 페이지에 여러 캠퍼스가 있을 때 우리 대학명의 캠퍼스에 해당하는 표·행만 남긴다.
    · 전형 머리글: '춘천캠퍼스 일반교과전형', '강릉/원주캠퍼스 …', '[종합] DKU인재 (천안)'
    · 행 단위: 강원대는 모집단위 행마다 '삼척캠퍼스'·'도계(삼척제2)캠퍼스' 칸이 있다
    우리 이름에 캠퍼스가 없으면(단국대학교) 형제 대학명(단국대학교(천안))의 캠퍼스 표만 뺀다."""
    base, y = (re.match(r'^(.*?)(?:\((.+)\))?$', uni).groups())
    sib = {m.group(1) for u in by_uni for m in [re.match(re.escape(base) + r'\((.+)\)$', u)] if m}
    for jn in list(page):
        # 꼬리 괄호는 캠퍼스 이름일 때만 — '학생부교과(학교추천)' 의 괄호를 캠퍼스로 읽어 고려대(세종)이 통째로 빠졌었다
        m = re.match(r'^(\S+?)\s*캠퍼스|^.*\s\((%s)\)$' % CAMPUS_NAMES, jn)
        lab = (m.group(1) or m.group(2)) if m else None
        if lab and (y and y not in lab or not y and any(x in lab for x in sib)):
            del page[jn]; continue
        if y:
            keep, cur = [], None
            for it in page[jn]:
                # 캠퍼스 칸은 rowspan 이라 그룹 첫 행에만 있다 — 다음 표기가 나올 때까지 이어받는다
                labs = [c for c in it['cands'] if c.endswith('캠퍼스')]
                cur = labs[0] if labs else cur
                if cur and not cur.startswith(y):
                    continue
                keep.append(it)
            page[jn] = keep


def key(r):
    """행 식별 키. 매칭기가 보는 정보(대학·유형·전형명·학과·모집인원)가 전부다 —
    이 다섯이 같은 행은 매칭 결과도 같아야 정상이라 한 키로 묶어도 된다(완전 동일 행 121개 존재)."""
    return '%s|%s|%s|%s|%s' % (r['uni'], r['jhtype'], r['jhname'], r['dept'], r['enroll'])


CAMPUS_NAMES = '죽전|천안|서울|국제|세종|원주|글로컬|강릉|삼척|춘천|여수|광주|도계|WISE|ERICA|미래'
CAMPUS = re.compile(r'^\S*캠퍼스\s*|\s*\((죽전|천안|서울|국제|세종|원주|글로컬|강릉|삼척|춘천|여수|광주)\)$')


ROMAN = str.maketrans({'Ⅰ': 'I', 'Ⅱ': 'II', 'Ⅲ': 'III', 'Ⅳ': 'IV', 'Ⅴ': 'V'})


def core(jn):
    """페이지 전형명에서 캠퍼스 표기를 뗀 정규화키 — '광주캠퍼스 학생부교과(일반)' → '일반'.
    로마숫자 문자도 알파벳으로 — 우리 '일반교과 I 전형' vs 강원대 페이지 '일반교과Ⅰ전형'."""
    return M.jkey(CAMPUS.sub('', jn).strip().translate(ROMAN))


SHELL = re.compile(r'정원\s*[내외]|모집|학생부\s*(교과|종합)(전형|위주)?|실기\s*/\s*실적(위주|형)?|[\[\]【】_\-]')


def shell_eq(o, jk, full):
    """페이지 전형명의 껍데기를 벗겨 우리 이름과 **완전일치**하는지.
    유형어를 떼면 알맹이가 '일반'·'교과'·'실기' 처럼 짧아져 포함비교로는 위험한 전형들을 위한 단계다.
    '학생부교과전형  일반전형(정원내)' → '일반' (공주대), '정원내 [실기/실적] 실기일반' → '실기일반' (상지대),
    '실기/실적(실기우수자)' → '실기우수자' (안양대). 앞뒤로 세부 분야가 붙은 경우는 4자 이상일 때만 허용 —
    '실기/실적위주(무용실기우수자)' → '실기우수자' 로 끝남(국민대). '학교생활우수자' 는 '실기우수자' 로 끝나지 않는다."""
    c = M._core(SHELL.sub(' ', CAMPUS.sub('', o)).translate(ROMAN))
    if not c:
        return False
    if c in (jk, full):
        return True
    for k in (full, jk):
        if len(k) >= 4 and (c.endswith(k) or c.startswith(k)) and contains(k, c):
            return True
    return False


def contains(a, b):
    """정규화키 포함관계. 두 가지 오매칭을 막는다.
    · 로마숫자 연장 — '기회균형선발I' 이 '기회균형선발II' 의 앞부분이라 붙었다(충남대 2027)
    · 짧은 알맹이 — '실기우수자전형' 은 유형어 '실기'를 떼면 '우수자' 만 남아 '학교생활우수자' 에 붙었다(중부대 2027)"""
    short, long_ = sorted((a, b), key=len)
    if len(short) < 4 or short not in long_:
        return False
    i = long_.index(short) + len(short)
    return not (re.search(r'[IV]$', short) and long_[i:i + 1] in ('I', 'V'))


def uniq(hits):
    """한 행에 걸린 후보들. 값이 하나로 모일 때만 채택한다 — 둘 이상이면 어느 것인지 모르므로 버린다."""
    vals = {(it['mo'], it['ap'], it['cr']) for it, _ in hits}
    return hits[0] if len(vals) == 1 else None


def hits_in(r, items):
    return [(it, h) for it in items for h in [M.dept_match(r['dept'], it['cands'])] if h]


def match_row(r, page, pk, summ, solo):
    """→ (item, 페이지학과, 방식) 또는 (None, 사유, None)."""
    # 1) 2026 대조에서 검증된 규칙 그대로
    cand = M.pick(r['jhname'], r['jhtype'], pk) if pk else None
    if cand:
        h = hits_in(r, cand)
        if h:
            u = uniq(h) or uniq([x for x in h if x[0]['mo'] == r['enroll']] or h)
            return (u[0], u[1], 'pick') if u else (None, 'ambiguous', None)
    # 2) 캠퍼스 접두·꼬리가 붙은 페이지(경희·전남·단국 2027). 유형이 맞는 전형만, 정확키 → 포함키 순서.
    #    여기부터는 **모집인원 일치**를 후보 조건에 넣는다 — 규칙을 넓힌 대가로 그만큼 조인다.
    jk = M.jkey(r['jhname'].replace('\n', '').translate(ROMAN))
    typed = [(o, it) for o, it in page.items() if M.jhtype_of(o) in (None, r['jhtype'])]
    full = M._core(r['jhname'].replace('\n', '').translate(ROMAN))      # 유형어를 떼지 않은 우리 이름
    full = re.sub(r'외$', '', full) if r['jhname'].endswith('(외)') else full
    for stage in ('exact', 'shell', 'contain'):
        if stage == 'exact':
            pool = [(o, it) for o, it in typed if core(o) == jk]
        elif stage == 'shell':
            pool = [(o, it) for o, it in typed if shell_eq(o, jk, full)]
        else:
            pool = [(o, it) for o, it in typed if contains(jk, core(o))]
        h = [x for _, it in pool for x in hits_in(r, it) if x[0]['mo'] == r['enroll']]
        if h:
            u = uniq(h)
            return (u[0], u[1], 'campus') if u else (None, 'ambiguous', None)
    # 3) 학과 표가 없고 전형별 합계표만 있는 페이지(교대·한동대). 그 전형에 우리 행이 하나뿐일 때만.
    if solo:
        s = [v for o, v in summ.items() if M.jhtype_of(o) in (None, r['jhtype']) and core(o) == jk]
        if len(s) == 1 and s[0]['mo'] == r['enroll']:
            return s[0], '(전형 합계)', 'summary'
    return None, 'unmatched', None


# 페이지 목록: 자동 수집분(pages/index.tsv) + 수작업 수집분(pages_extra/{대학}.html)
pages = []
for l in open(os.path.join(SRC, 'pages', 'index.tsv'), encoding='utf-8'):
    num, uni, kind, sz, url = l.rstrip('\n').split('\t')
    pages.append((uni, os.path.join(SRC, 'pages', '%03d.html' % int(num)), url))
ex = os.path.join(SRC, 'pages_extra')
if os.path.isdir(ex):
    srcs = {}                                  # 수작업분의 실제 주소 — pages_extra/_sources.tsv
    if os.path.exists(os.path.join(ex, '_sources.tsv')):
        for l in list(open(os.path.join(ex, '_sources.tsv'), encoding='utf-8'))[1:]:
            f, u = l.split('\t')[:2]
            srcs[f] = u
    for f in sorted(os.listdir(ex)):
        if f.endswith('.html'):
            pages.append((f[:-5], os.path.join(ex, f), srcs.get(f, 'pages_extra/' + f)))

out, stat = {}, collections.Counter()
conflict = []
per_uni = {}
mo_diff = []
for uni, path, url in pages:
    # 수작업 파일명은 '목포대학교(국립목포대)' 처럼 별칭이 붙어 있다. 우리 표기에 없으면 괄호를 뗀다.
    if uni not in by_uni:
        uni = re.sub(r'\(.*\)$', '', uni)
    ours = by_uni.get(uni, [])
    if not ours:
        stat['page_without_rows'] += 1
        print('  행 없음(대학명 불일치?) %s' % uni); continue
    if uni in EXCLUDE:
        stat['excluded'] += len(ours); per_uni[uni] = (len(ours), 0, 0, len(ours)); continue
    page = P.parse(path)
    # 모집인원 0 행이 있는 전형은 표 전체를 버린다 — 대행사가 JS 로 세부트랙을 앞 행에 병합해
    # 화면값이 정적 HTML 과 다르다(중부대 경찰경호 정적 0.75 / 실제 4.58, README 알려진 결함 1).
    dropped = [jn for jn, v in page.items() if any(it['mo'] == 0 for it in v)]
    for jn in dropped:
        del page[jn]
    for jn, v in page.items():
        for it in v:
            it['_jh'] = jn
    campus_filter(uni, page)
    pk = {}
    for jn, items in page.items():
        pk.setdefault(M.jkey(jn), []).append((jn, items))
    summ = P.parse_summary(path)
    nj = collections.Counter((x['jhtype'], x['jhname']) for x in ours)
    c = collections.Counter()
    for r in ours:
        got, why, how = match_row(r, page, pk, summ, nj[(r['jhtype'], r['jhname'])] == 1)
        if got is None:
            c[why] += 1; continue
        if got['mo'] != r['enroll']:
            c['mo_diff'] += 1
            mo_diff.append({'uni': uni, 'jhname': r['jhname'], 'dept': r['dept'], 'enroll': r['enroll'],
                            'page_mo': got['mo'], 'page_dept': why, 'cr': got['cr']})
            continue
        c['ok'] += 1; c['by_' + how] += 1
        k = key(r)
        if k in out and out[k]['c27'] != got['cr']:      # 같은 키에 다른 값 — 있어선 안 된다
            conflict.append(k)
        out[k] = {'c27': got['cr'], 'ap': got['ap'], 'mo': got['mo'], 'how': how, 'pjh': got.get('_jh', ''),
                  'pdept': why, 'src': url}
    per_uni[uni] = (len(ours), c['ok'], c['mo_diff'], c['unmatched'] + c['ambiguous'])
    stat.update(c)

# 한 줄에 한 행 — git diff 로 어느 행 값이 바뀌었는지 바로 보이게. 원문 주소는 대학별로 하나라 따로 둔다.
with open(os.path.join(HERE, 'ratio27.json'), 'w', encoding='utf-8') as f:
    srcs = sorted({v['src'] for v in out.values()})
    f.write('{"_src":%s,\n' % json.dumps(srcs, ensure_ascii=False))
    f.write(',\n'.join('%s:%s' % (json.dumps(k, ensure_ascii=False),
                                   json.dumps(dict(v, src=srcs.index(v['src'])), ensure_ascii=False,
                                              separators=(',', ':')))
                         for k, v in sorted(out.items())))
    f.write('}\n')
json.dump(mo_diff, open(os.path.join(SRC, '_mo_diff.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
tot = len(rows)
print('채택 %d (규칙 %d · 캠퍼스 %d · 합계표 %d) · 모집인원 불일치(버림) %d · 후보 둘 이상(버림) %d · 미매칭 %d'
      % (stat['ok'], stat['by_pick'], stat['by_campus'], stat['by_summary'], stat['mo_diff'], stat['ambiguous'],
         stat['unmatched']))
print('전체 행 %d → 채움률 %.1f%% · 키 충돌 %d · 제외 대학 행 %d' % (tot, 100 * stat['ok'] / tot, len(conflict), stat['excluded']))
if '-v' in sys.argv:
    for u, (n, ok, md, um) in sorted(per_uni.items(), key=lambda x: x[1][1] / x[1][0]):
        print('  %-18s 행%4d 채택%4d(%3.0f%%) 인원불일치%3d 미매칭%4d' % (u, n, ok, 100 * ok / n, md, um))
