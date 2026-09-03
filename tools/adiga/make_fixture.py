# -*- coding: utf-8 -*-
# adiga_raw.json(6MB, 네트워크 수집분) → 회귀 감시용 경량 지문 파일로 압축한다.
# 하네스가 매번 어디가를 때리면 느리고 사이트 개편에 취약하다. c26_verified.json 과 같은 방식.
import json, os, sys, hashlib, collections
HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, DASH); sys.path.insert(0, HERE)
from match_util import norm_uni, norm_dept, pick_one
import adiga_compare as AC

ext = AC.parse(json.load(open(os.path.join(HERE, 'adiga_raw.json'), encoding='utf-8')))
d = json.loads(open(os.path.join(DASH, 'data.js'), encoding='utf-8').read()[len('window.IPSI = '):-1])
S, D = d['schema'], d['dicts']
def v(r, k):
    x = r[S.index(k)]
    return D[k][x] if (k in D and isinstance(x, int)) else x

out, n = {}, 0
for uni, items in ext.items():
    idx = collections.defaultdict(list)
    for it in items:
        idx[(it['jht'], norm_dept(it['dept']))].append(it)
    for r in d['rows']:
        if norm_uni(v(r, 'uni')) != uni or v(r, 'g26') is None: continue
        c = idx.get((v(r, 'jhtype'), norm_dept(v(r, 'dept'))))
        if not c: continue
        p, _ = pick_one(c, v(r, 'jhname'), key=lambda x: x['jh'])
        if not p or (p['g50'] is None and p['g70'] is None): continue
        key = '|'.join([v(r, 'uni'), v(r, 'dept'), v(r, 'jhtype'), v(r, 'jhname'), v(r, 'jagyeok') or ''])
        h = hashlib.sha1(key.encode()).hexdigest()[:10]
        out[h] = [p['g50'], p['g70'], p['comp']]
        n += 1
json.dump({'_note': '대학어디가 2026 전형결과 지문. 값은 [환산등급50, 환산등급70, 경쟁률]. '
                    'qa_adiga_xcheck.py 가 g26 회귀를 감시한다. 갱신은 tools/adiga/adiga_fetch.py 재수집 후 이 스크립트.',
           'asof': '2026-09-02', 'n': n, 'v': out},
          open(os.path.join(DASH, 'adiga_verified.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f'지문 {n}행 저장 → adiga_verified.json ({os.path.getsize(os.path.join(DASH, "adiga_verified.json"))//1024} KB)')
