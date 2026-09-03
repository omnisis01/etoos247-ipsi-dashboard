# -*- coding: utf-8 -*-
# 어디가 수집분(adiga_raw.json) ↔ data.js 의 2026 입결(g26) 대조.
#
# 표 구조(학생부종합·학생부교과):
#   구분 | 모집단위 | 최초(A) | 이월(B) | 최종(A+B) | 경쟁률 | 충원인원 | 환산점수50 | 환산점수70 | 환산등급50 | 환산등급70 | 총점
# ⚠️ '구분'이 수시/정시 혼재 — 수시만 본다.
# ⚠️ 경쟁률을 매칭 검증자로 쓴다. 등급이 안 맞을 때 '행을 잘못 짝지었나'와 '값이 다른가'를
#    가르는 게 전부다(context-notes 46). 경쟁률이 맞으면 매칭은 확실하고 값만 다른 것이다.
import json, os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, DASH)
from match_util import norm_uni, norm_dept, norm_jh, pick_one

JHT = {'학생부종합': '학생부종합', '학생부교과': '학생부교과'}


def num(x):
    if x is None: return None
    t = str(x).strip().replace(',', '')
    if t in ('', '-', '0.0', '0'): return None
    try: return float(t)
    except ValueError: return None


# 어디가 표 제목은 세 형식이 섞인다 — 괄호형 167 · 콜론형 12 · 대괄호형.
#   학생부종합(융합형) · 학생부종합:계열적합전형 · 학생부종합[기회균형전형I-장애인 등 대상자(정원외)]
# 유형 접두어를 떼고 바깥 괄호를 벗기는 것이 전부다. **매칭을 느슨하게 푸는 게 아니라
# 전형명을 정확히 뽑는 것**이다 — 콜론형을 안 벗겨서 고려대 196행이 통째로 미매칭이었다.
# '학생부종합전형(…)' 처럼 유형 뒤에 '전형'이 또 붙는 표기도 있다(서울대). 선택적으로 흡수한다.
_TYPE = r'(?:학생부종합|학생부교과|수능위주|수능|논술|실기/실적|실기|실적)(?:전형)?'


def _jhname(cap):
    s = cap.strip()
    s = re.sub(r'^\s*' + _TYPE + r'\s*[:：]\s*', '', s)          # 콜론형
    m = re.match(r'^\s*' + _TYPE + r'\s*[\(\[](.*)[\)\]]\s*$', s)  # 괄호·대괄호형
    if m:
        s = m.group(1)
    s = re.sub(r'^\s*수시모집\s*', '', s)
    return s.strip()


def parse(raw):
    """(대학 → [{jh, dept, comp, g50, g70, v50, v70, cap}])"""
    # ⚠️ 수집분의 키는 어디가 표기('가야대학교[본교]')다. 대시보드 표기와 잇기 전에
    #    캠퍼스 꼬리표를 떼고 norm_uni 로 정규화한다 — 안 하면 조인이 통째로 0건이 된다.
    out = collections.defaultdict(list)
    for uni_raw, tabs in raw.items():
        uni = norm_uni(uni_raw.split('[')[0])
        for label, tables in tabs.items():
            if label not in JHT: continue
            for tb in tables:
                jhname = _jhname(tb['jh'])
                for r in tb['rows']:
                    if not r or r[0] not in ('수시',): continue
                    if len(r) < 12: continue
                    out[uni].append({'jht': JHT[label], 'jh': jhname, 'dept': r[1],
                                     'comp': num(r[5]),
                                     'v50': num(r[7]), 'v70': num(r[8]),
                                     'g50': num(r[9]), 'g70': num(r[10]), 'cap': num(r[11])})
    return out


def main():
    raw = json.load(open(os.path.join(HERE, 'adiga_raw.json'), encoding='utf-8'))
    ext = parse(raw)
    d = json.loads(open(os.path.join(DASH, 'data.js'), encoding='utf-8').read()[len('window.IPSI = '):-1])
    S, D = d['schema'], d['dicts']
    def v(r, k):
        x = r[S.index(k)]
        return D[k][x] if (k in D and isinstance(x, int)) else x

    stat = collections.Counter(); diffs = []
    for uni, items in ext.items():
        idx = collections.defaultdict(list)
        for it in items:
            idx[(it['jht'], norm_dept(it['dept']))].append(it)
        for r in d['rows']:
            if norm_uni(v(r, 'uni')) != uni or v(r, 'g26') is None: continue
            stat['대상'] += 1
            cands = idx.get((v(r, 'jhtype'), norm_dept(v(r, 'dept'))))
            if not cands: stat['미매칭(모집단위)'] += 1; continue
            c, _ = pick_one(cands, v(r, 'jhname'), key=lambda x: x['jh'])
            if not c: stat['미매칭(전형모호)'] += 1; continue
            stdk = v(r, 'stdK26')
            want = c['g70'] if stdk == 'cut70' else c['g50'] if stdk == 'cut50' else None
            if want is None: stat['기준외/어디가결측'] += 1; continue
            stat['판정가능'] += 1
            # 경쟁률로 매칭 검증
            ours_c = v(r, 'c26')
            cmatch = (ours_c is not None and c['comp'] is not None
                      and abs(ours_c - c['comp']) <= max(0.05, 0.01 * c['comp']))
            g = v(r, 'g26')
            if abs(g - want) < 0.005: stat['일치'] += 1
            else:
                stat['불일치'] += 1
                diffs.append((abs(g - want), uni, v(r, 'dept'), v(r, 'jhname'), stdk,
                              g, want, c['g50'], c['g70'], ours_c, c['comp'], cmatch))
    print('=== 어디가 ↔ 대시보드 입결 대조 ===')
    for k in ('대상', '판정가능', '일치', '불일치', '미매칭(모집단위)', '미매칭(전형모호)', '기준외/어디가결측'):
        print('  %-18s %5d' % (k, stat[k]))
    if stat['판정가능']:
        print('  일치율 %.1f%%' % (100 * stat['일치'] / stat['판정가능']))
    diffs.sort(reverse=True)
    print('\n--- 차이 큰 순 (경쟁률 일치 = 매칭 확실) ---')
    print('%-12s %-20s %-16s %-6s %6s %6s | %6s %6s | %s' %
          ('대학', '모집단위', '전형', '기준', '우리', '어디가', '50%', '70%', '경쟁률'))
    for dv, u, dp, jn, sk, g, w, g50, g70, oc, ac, cm in diffs[:25]:
        print('%-12s %-20s %-16s %-6s %6s %6s | %6s %6s | %s' %
              (u[:11], dp.replace('\n', ' ')[:18], jn[:14], sk, g, w, g50, g70,
               ('✓ %s' % oc) if cm else ('✗ %s vs %s' % (oc, ac))))
    json.dump([[u, dp, jn, sk, g, w, g50, g70, oc, ac, cm] for _, u, dp, jn, sk, g, w, g50, g70, oc, ac, cm in diffs],
              open(os.path.join(HERE, 'adiga_diff.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
