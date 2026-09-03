# -*- coding: utf-8 -*-
# 입결(g26) ↔ 대학어디가 2026 전형결과 대조 래칫.
#
# 어디가는 대학이 법령에 따라 제출하는 공식 등록 자료다. 지역 엑셀(qa_ipgyeol_xcheck)보다
# 판정 가능 행이 두 배 이상이고, **환산등급을 50%컷·70%컷으로 나눠 줘서 우리 stdK26 라벨 자체를
# 검증**할 수 있다(실측 — 서울시립대 지역균형 27행이 라벨은 70%컷인데 값은 50%컷이었다).
#
# ⚠️ **불일치가 곧 우리 오류가 아니다.** 실측으로 확인된 것 —
#   · 어디가는 대학에 따라 소수 1자리로 싣는다(홍익대 34건). 우리가 더 정밀하다.
#   · 대학이 여러 지표를 공개하면 어디가가 다른 열을 고른다. 한밭대 45건은 공식 파일 대조 결과
#     **우리=내신등급(일반교과)·어디가=내신등급(진로선택)** 이었다 — 우리가 옳다.
#   · context-notes (47) 에서 14교 595건을 대학 공식으로 판정한 결론도 '대시보드가 옳다'였다.
#   그래서 판정하지 않고 **변화만 감시하는 래칫**이다. 현재 불일치를 기준선에 박고 신규·악화만 잡는다.
#
# 지문 갱신: python3 tools/adiga/adiga_fetch.py && python3 tools/adiga/make_fixture.py
import json, os, sys, hashlib, collections

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, 'adiga_verified.json')
BASE = os.path.join(HERE, 'qa_adiga_baseline.json')


def main():
    if not os.path.exists(REF):
        print(f'SKIP  지문 없음: {REF}'); return 0
    ref = json.load(open(REF, encoding='utf-8'))
    d = json.loads(open(os.path.join(HERE, 'data.js'), encoding='utf-8').read()[len('window.IPSI = '):-1])
    S, D = d['schema'], d['dicts']
    def v(r, k):
        x = r[S.index(k)]
        return D[k][x] if (k in D and isinstance(x, int)) else x

    stat = collections.Counter(); cur = {}
    for r in d['rows']:
        g = v(r, 'g26')
        if g is None: continue
        key = '|'.join([v(r, 'uni'), v(r, 'dept'), v(r, 'jhtype'), v(r, 'jhname'), v(r, 'jagyeok') or ''])
        h = hashlib.sha1(key.encode()).hexdigest()[:10]
        rec = ref['v'].get(h)
        if not rec: stat['미수록'] += 1; continue
        g50, g70, comp = rec
        stdk = v(r, 'stdK26')
        want = g70 if stdk == 'cut70' else g50 if stdk == 'cut50' else None
        if want is None: stat['기준외'] += 1; continue
        stat['판정가능'] += 1
        if abs(g - want) < 0.005: stat['일치'] += 1; continue
        stat['불일치'] += 1
        cur[h] = round(g - want, 3)

    print(f"판정가능 {stat['판정가능']}행 · 일치 {stat['일치']} · 불일치 {stat['불일치']}"
          f" (미수록 {stat['미수록']} · 기준외 {stat['기준외']})")
    if stat['판정가능']:
        print(f"  일치율 {100 * stat['일치'] / stat['판정가능']:.1f}%")

    if '--save-baseline' in sys.argv:
        json.dump({'_note': '어디가 대조 기준선. 값은 (우리 g26 − 어디가컷). 신규·악화만 실패로 잡는다.',
                   'v': cur}, open(BASE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
        print(f'  기준선 저장 {len(cur)}건'); return 0
    if not os.path.exists(BASE):
        print('기준선이 없다 — `python3 qa_adiga_xcheck.py --save-baseline` 로 만들 것'); return 1
    old = json.load(open(BASE, encoding='utf-8'))['v']
    new = sorted(set(cur) - set(old))
    gone = sorted(set(old) - set(cur))
    worse = sorted(k for k in cur if k in old and abs(cur[k]) > abs(old[k]) + 0.005)
    if gone: print(f'  해소 {len(gone)}건 — 기준선 갱신 권장(--save-baseline)')
    if new or worse:
        for k in (new + worse)[:12]:
            print(f'  ✗ {k}  Δ={cur[k]}' + ('' if k in new else f' (이전 {old[k]})'))
        print(f'FAIL  신규 불일치 {len(new)}건 · 악화 {len(worse)}건'); return 1
    print(f'OK  신규 불일치 없음 (기준선 {len(old)}건 유지)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
