# c26 대조 v3 — match_util2 의 전형/학과 매칭 규칙 사용.
import json, re, collections
import ratio_parse as P
import ratio_match as M

DASH = '/Users/omnibook/Downloads/ipsi_dashboard/2026 vs 2027/dashboard'
t = open(f'{DASH}/data.js', encoding='utf-8').read()
d = json.loads(t[len('window.IPSI = '):-1])
S, D = d['schema'], d['dicts']
DK = {'uni', 'dept', 'jhname'}
rows = [{k: (D[k][v] if k in DK and isinstance(v, int) else v) for k, v in zip(S, r)} for r in d['rows']]
ours = collections.defaultdict(list)
for r in rows:
    if r['c26'] is not None:
        ours[r['uni']].append(r)

idx = [l.rstrip('\n').split('\t') for l in open('pages/index.tsv', encoding='utf-8')]
BAD_LINK = {'대진대학교'}          # 26 링크가 대전대 페이지를 가리킨다(원본 PDF 오류)
NON_FINAL = set(json.load(open('nofinal_unis.json')))   # '최종' 문구 없는 페이지 = 마감 전 스냅샷

res = {'match': 0, 'mismatch': [], 'unmatched': 0, 'skipped': 0, 'nonfinal': 0}
for num, uni, kind, sz, url in idx:
    if uni in BAD_LINK:
        res['skipped'] += len(ours.get(uni, [])); continue
    page = P.parse('pages/%03d.html' % int(num))
    if not page:
        res['unmatched'] += len(ours.get(uni, [])); continue
    pk = {}                                   # 정규화키 -> [(원본전형명, items)]
    for jn, items in page.items():
        pk.setdefault(M.jkey(jn), []).append((jn, items))
    for r in ours.get(uni, []):
        cand = M.pick(r['jhname'], r['jhtype'], pk)
        if cand is None:
            res['unmatched'] += 1; continue
        pdept = None; got = None
        for it in cand:
            hit = M.dept_match(r['dept'], it['cands'])
            if hit:
                got, pdept = it, hit; break
        if got is None:
            res['unmatched'] += 1; continue
        if abs(got['cr'] - r['c26']) <= 0.005:
            res['match'] += 1
        else:
            rec = {'uni': uni, 'dept': r['dept'].replace('\n', ' '), 'jhtype': r['jhtype'],
                   'jhname': r['jhname'].replace('\n', ' '), 'ours': r['c26'], 'page': got['cr'],
                   'recruit': got['mo'], 'applicants': got['ap'], 'page_dept': pdept,
                   'enroll': r['enroll'], 'c25': r['c25'], 'url': url,
                   'nonfinal': uni in NON_FINAL}
            if rec['nonfinal']:
                res['nonfinal'] += 1
            res['mismatch'].append(rec)

print('일치 %d · 불일치 %d(그중 마감전스냅샷 %d) · 미매칭 %d · 스킵 %d'
      % (res['match'], len(res['mismatch']), res['nonfinal'], res['unmatched'], res['skipped']))
json.dump(res, open('c26_compare_v3.json', 'w'), ensure_ascii=False, indent=1)
real = [m for m in res['mismatch'] if not m['nonfinal']]
c = collections.Counter(m['uni'] for m in real)
print('\n마감전스냅샷 제외 불일치 %d건 · 대학별 상위 12:' % len(real))
for u, n in c.most_common(12):
    print('  %-18s %d' % (u, n))
