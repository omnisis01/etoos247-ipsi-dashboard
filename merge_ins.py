# 인사이트 병합 스크립트 — 기존 대학에 섹션/태그/판정 추가 + 신규 대학 추가 후 insights.js 재작성
# 사용법: python3 merge_ins.py <merge.json>
#   merge.json = {"new": {대학명: {전체 인사이트 객체}}, "enrich": {대학명: {"section": {...}, "tags": [...], "verdict": [...]}}}
# insights.js는 JS라 node로 덤프해 읽고, 병합 후 균일한 포맷(meta/order/unis 각 1줄 JSON)으로 다시 쓴다.
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
INS = os.path.join(HERE, 'insights.js')

def load_insights():
    out = subprocess.run(
        ['node', '-e', f'global.window={{}};require({json.dumps(INS)});process.stdout.write(JSON.stringify(window.IPSI_INSIGHTS))'],
        capture_output=True, text=True)
    if out.returncode != 0:
        print('ERROR: insights.js 로드 실패\n', out.stderr); sys.exit(1)
    return json.loads(out.stdout)

def write_insights(d):
    lines = ['/* 주요 대학 2027 vs 2026학년도 수시 변화 인사이트',
             '   출처: 넥스트플레이(nextplay.kr) 2027 VS 2026 시리즈 · 의학계열(치·한·수) 변경사항 전략자료 · 각 대학 모집요강',
             '   ※ 이 파일은 build_ins.py / merge_ins.py 로 생성·갱신된다. 수기 편집 시 포맷 유지. */',
             'window.IPSI_INSIGHTS = {',
             '  meta: ' + json.dumps(d['meta'], ensure_ascii=False) + ',',
             '  order: ' + json.dumps(d['order'], ensure_ascii=False) + ',',
             '  unis: {']
    for u in d['order']:
        if u in d['unis']:
            lines.append(f'    {json.dumps(u, ensure_ascii=False)}: {json.dumps(d["unis"][u], ensure_ascii=False)},')
    lines += ['  },', '};', '']
    open(INS, 'w', encoding='utf-8').write('\n'.join(lines))

def main():
    payload = json.load(open(sys.argv[1], encoding='utf-8'))
    d = load_insights()
    n_new = n_sec = 0

    for uni, entry in (payload.get('new') or {}).items():
        if uni in d['unis']:
            print(f'SKIP(이미 존재): {uni}'); continue
        d['unis'][uni] = entry
        d['order'].append(uni)
        n_new += 1

    for uni, patch in (payload.get('enrich') or {}).items():
        if uni not in d['unis']:
            print(f'WARN(대상 없음, 건너뜀): {uni}'); continue
        t = d['unis'][uni]
        if patch.get('section'):
            titles = [s.get('title') for s in t.get('sections', [])]
            if patch['section'].get('title') in titles:
                print(f'SKIP(같은 섹션 존재): {uni} / {patch["section"].get("title")}'); continue
            t.setdefault('sections', []).append(patch['section'])
            n_sec += 1
        for tag in patch.get('tags', []):
            if tag not in t.setdefault('tags', []): t['tags'].append(tag)
        for v in patch.get('verdict', []):
            if v.get('text') not in [x.get('text') for x in t.setdefault('verdict', [])]: t['verdict'].append(v)
        for src in patch.get('sources', []):
            if src.get('url') not in [x.get('url') for x in t.setdefault('sources', [])]: t['sources'].append(src)

    write_insights(d)
    print(f'OK  신규 {n_new}교 · 섹션 보강 {n_sec}교 · 총 {len(d["order"])}교')

if __name__ == '__main__':
    main()
