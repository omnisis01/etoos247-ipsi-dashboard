# build_data.py가 만든 data.js의 불변식을 검증하고, 이전 버전과의 변경점을 진단하는 하네스
# 사용법:
#   python3 verify_data.py                 # 불변식 검증 (통과=조용히, 실패=시끄럽게, 위반 시 exit 1)
#   python3 verify_data.py --diff OLD.js    # OLD.js 대비 행 단위 변경 리포트 (엑셀 갱신 시)
"""
하네스 원칙 적용:
- Silent success, verbose failure: 통과하면 한 줄, 실패하면 위반 항목을 전부 출력하고 exit 1.
- Ratchet: 실제로 겪은 실패만 규칙으로 넣는다(입결 등급 범위·연도 프레임·행수 급변).
- 재사용 스킬: 매 갱신마다 즉석 diff를 다시 짜지 말고 --diff로 재사용.
"""
import json, os, sys

HERE = os.path.dirname(__file__)

def load(path):
    t = open(path, encoding='utf-8').read()
    prefix = 'window.IPSI = '
    if not t.startswith(prefix):
        raise SystemExit(f'FAIL: {path} 가 "{prefix}"로 시작하지 않음')
    return json.loads(t[len(prefix):-1])  # 끝의 ';' 제거

# ---------------------------------------------------------------- 불변식 검증
def col(sch, name):
    return sch.index(name)

def verify(d):
    fails = []
    sch = d['schema']; rows = d['rows']

    # 1) 메타 정합성
    if d['meta'].get('nRows') != len(rows):
        fails.append(f"meta.nRows({d['meta'].get('nRows')}) != 실제 행수({len(rows)})")
    if d['meta'].get('nUni') != len(d['dicts']['uni']):
        fails.append(f"meta.nUni != 실제 대학수({len(d['dicts']['uni'])})")

    # 2) 연도 프레임(확정): 올해=2027
    if d['meta'].get('years', {}).get('cur') != 2027:
        fails.append(f"meta.years.cur != 2027 (현재 {d['meta'].get('years',{}).get('cur')})")

    # 3) 입결 등급 불변식 — 1.0~9.0 범위 밖이면 무데이터(None)여야 한다.
    #    (등급 숫자가 작을수록 '높음/우수'. 환산점수 오입력이 등급칸에 새는 것을 차단.)
    ig = [col(sch, c) for c in ('g26', 'g25', 'g24')]
    bad_grade = 0
    for r in rows:
        for i in ig:
            v = r[i]
            if v is not None and not (1.0 <= v <= 9.0):
                bad_grade += 1
    if bad_grade:
        fails.append(f"입결 등급 범위(1.0~9.0) 위반 {bad_grade}건 — vgrade() 확인 필요")

    # 4) 핵심 카테고리 카운트 > 0 (분류 로직이 통째로 깨졌는지 감지)
    cats = {c['key']: c['count'] for c in d['cats']}
    for k in ('medical', 'engineering', 'nursing_health', 'business', 'natural'):
        if cats.get(k, 0) <= 0:
            fails.append(f"핵심 카테고리 '{k}' 카운트가 0 — 분류 로직 점검")

    # 5) 출처 라벨 존재
    if not d['meta'].get('source'):
        fails.append("meta.source 비어 있음")

    return fails, {
        'rows': len(rows), 'uni': len(d['dicts']['uni']),
        'source': d['meta'].get('source', ''),
    }

# ---------------------------------------------------------------- 변경점 진단(--diff)
def key(row, d, sch):
    iu, idp, ijt, ijn, ija = (col(sch, x) for x in ('uni', 'dept', 'jhtype', 'jhname', 'jagyeok'))
    return (d['dicts']['uni'][row[iu]], d['dicts']['dept'][row[idp]], row[ijt],
            d['dicts']['jhname'][row[ijn]], d['dicts']['jagyeok'][row[ija]])

STR_FIELDS = {'change', 'choejeo', 'method', 'note'}
DIFF_FIELDS = ['enroll', 'prev', 'change', 'choejeo', 'hasChoejeo', 'chKind',
               'c26', 'c25', 'c24', 'g26', 'g25', 'g24', 'v26', 'v25', 'v24', 'method', 'note']

def resolve(row, f, d, sch):
    v = row[col(sch, f)]
    if f in STR_FIELDS and isinstance(v, int):
        return d['dicts'][f][v]
    return v

def diff(old, new):
    sch = old['schema']
    om, nm = {}, {}
    for r in old['rows']: om.setdefault(key(r, old, sch), []).append(r)
    for r in new['rows']: nm.setdefault(key(r, new, sch), []).append(r)
    changed = 0
    for k, orows in om.items():
        nrows = nm.get(k)
        if not nrows:
            continue
        o, n = orows[0], nrows[0]
        rd = [(f, resolve(o, f, old, sch), resolve(n, f, new, sch))
              for f in DIFF_FIELDS
              if resolve(o, f, old, sch) != resolve(n, f, new, sch)]
        if rd:
            changed += 1
            print(f"--- {k[0]} | {k[1]} | {k[3]}")
            for f, ov, nv in rd:
                print(f"    {f}: {ov!r} -> {nv!r}")
    added = [k for k in nm if k not in om]
    removed = [k for k in om if k not in nm]
    print(f"\n변경 {changed}행 · 신규 {len(added)}행 · 삭제 {len(removed)}행")

# ---------------------------------------------------------------- main
def main():
    data_js = os.path.join(HERE, 'data.js')
    if len(sys.argv) >= 3 and sys.argv[1] == '--diff':
        diff(load(sys.argv[2]), load(data_js))
        return
    fails, info = verify(load(data_js))
    if fails:
        print(f"검증 실패 ({len(fails)}건):")
        for m in fails:
            print(f"  ✗ {m}")
        sys.exit(1)
    print(f"OK  rows={info['rows']} uni={info['uni']}  {info['source']}")

if __name__ == '__main__':
    main()
