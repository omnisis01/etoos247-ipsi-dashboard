# -*- coding: utf-8 -*-
# 입결(g26) 외부 대조 래칫 — '24~26년 3개년 입결 자료.xlsx'(최종등록 50%컷·70%컷 3개년)와 대조한다.
#
# 왜 필요한가: 유원대 63행이 공식 발표와 통째로 무관한 값이었는데(context-notes 101),
#   그 전까지 어디가 192교 전수 대조를 '통과'했다. 발견 계기는 g26=9.0 이 몇 행 보인다는 우연한 관찰이었다.
#   입결은 대학마다 기준(50/70/90%컷·평균)과 척도가 달라 "다르면 우리 오류"라고 단정할 수 없어
#   전수 대조가 계속 미뤄져 왔다 — 그래서 **래칫**으로 만든다. 지금 상태를 기준선에 박아 두고
#   **새로 생기는 불일치만** 실패로 잡는다.
#
# ⚠️ 불일치가 곧 우리 오류가 아니다 — 실측으로 확인된 것:
#   · 외부 파일은 소수 첫째 자리로 반올림된 곳이 있다(홍익대 38건이 전부 이것). 우리가 더 정밀하다.
#   · 광운대는 외부의 '70%컷' 열 값이 등급으로 보기 어렵고(7.09 등) 우리 값은 '50%컷' 열을 따라간다.
#     열 자체가 어긋난 것으로 보여 우리 값을 바꾸면 안 된다.
#   그래서 이 스크립트는 **판정하지 않고 변화만 감시한다.**
import json, os, sys, collections, openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from match_util import norm_uni, norm_dept, pick_one

SRC = os.path.join(HERE, '..', '입결 및 인사이트', '24~26년 3개년 입결 자료.xlsx')
BASE = os.path.join(HERE, 'qa_ipgyeol_baseline.json')
JHT = {'교과': '학생부교과', '종합': '학생부종합', '논술': '논술', '실기': '실기/실적', '실적': '실기/실적'}


def num(x):
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    t = str(x).strip().replace(',', '')
    if t in ('', '-', '–', '—', '없음', '미정', 'N/A'): return None
    try: return float(t)
    except ValueError: return None


def load_ext():
    ws = openpyxl.load_workbook(SRC, read_only=True, data_only=True)['입결정리']
    ext = collections.defaultdict(list)
    for r in ws.iter_rows(min_row=4, values_only=True):
        if not r[0] or not r[4]: continue
        jt = JHT.get(str(r[1]).strip())
        if not jt: continue
        ext[(norm_uni(r[0]), jt, norm_dept(r[4]))].append(
            {'jn': str(r[2] or ''), 'c50': num(r[16]), 'c70': num(r[19])})
    return ext


def main():
    if not os.path.exists(SRC):
        print(f'SKIP  외부 자료 없음: {SRC}'); return 0
    ext = load_ext()
    d = json.loads(open(os.path.join(HERE, 'data.js'), encoding='utf-8').read()[len('window.IPSI = '):-1])
    S, D = d['schema'], d['dicts']
    def v(r, k):
        x = r[S.index(k)]
        return D[k][x] if (k in D and isinstance(x, int)) else x

    stat = collections.Counter(); cur = {}
    for r in d['rows']:
        g = v(r, 'g26')
        if g is None: continue
        stat['대상'] += 1
        cands = ext.get((norm_uni(v(r, 'uni')), v(r, 'jhtype'), norm_dept(v(r, 'dept'))))
        if not cands: stat['미매칭'] += 1; continue
        c, _ = pick_one(cands, v(r, 'jhname'))
        if not c: stat['미매칭'] += 1; continue
        stdk = v(r, 'stdK26')
        want = c['c70'] if stdk == 'cut70' else c['c50'] if stdk == 'cut50' else None
        if want is None: stat['기준외/외부결측'] += 1; continue
        stat['판정가능'] += 1
        if abs(g - want) < 0.005: stat['일치'] += 1; continue
        stat['불일치'] += 1
        key = '|'.join([v(r, 'uni'), v(r, 'dept'), v(r, 'jhtype'), v(r, 'jhname'), v(r, 'jagyeok') or ''])
        cur[key] = round(g - want, 3)

    print(f"판정가능 {stat['판정가능']}행 · 일치 {stat['일치']} · 불일치 {stat['불일치']}"
          f" (대상 {stat['대상']} · 미매칭 {stat['미매칭']} · 기준외 {stat['기준외/외부결측']})")
    if stat['판정가능']:
        print(f"  일치율 {100 * stat['일치'] / stat['판정가능']:.1f}%")

    if '--save-baseline' in sys.argv:
        json.dump({'_note': '입결 외부 대조 기준선. 값은 (우리 g26 − 외부컷). 새 불일치만 실패로 잡는다.',
                   'v': cur}, open(BASE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
        print(f'  기준선 저장 {len(cur)}건'); return 0

    if not os.path.exists(BASE):
        print('기준선이 없다 — `python3 qa_ipgyeol_xcheck.py --save-baseline` 로 만들 것'); return 1
    old = json.load(open(BASE, encoding='utf-8'))['v']
    new = sorted(set(cur) - set(old))
    gone = sorted(set(old) - set(cur))
    worse = sorted(k for k in cur if k in old and abs(cur[k]) > abs(old[k]) + 0.005)
    if gone: print(f'  해소 {len(gone)}건 — 기준선 갱신 권장(--save-baseline)')
    if new or worse:
        for k in (new + worse)[:12]:
            print(f'  ✗ {k}  Δ={cur[k]}' + ('' if k in new else f' (이전 {old[k]})'))
        print(f'FAIL  신규 불일치 {len(new)}건 · 악화 {len(worse)}건')
        return 1
    print(f'OK  신규 불일치 없음 (기준선 {len(old)}건 유지)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
