# -*- coding: utf-8 -*-
# 공식 입학처 링크(admissions-links.js) 점검 — 대학명 키 정합성·확인일자 신선도·링크 생존.
#
# 왜 필요한가: admissions-links.js 는 스탬프·훅·verify_render 에는 등록됐지만 **내용을 보는 장치가
# 없었다.** 이 파일은 두 가지가 조용히 썩는다 —
#   ① 대학명 키가 data.js 와 어긋나면 그 대학은 공식 링크 대신 검색 폴백으로 조용히 떨어진다.
#      (실측: '경국대학교'처럼 최근 개명된 대학이 있어 키 오타가 눈에 안 띈다)
#   ② 대학 홈페이지 개편으로 URL 이 죽어도 학생이 클릭할 때까지 아무도 모른다. 접수 주간엔 치명적.
# checkedOn 도 손으로 적는 값이라 같이 본다.
#
# 훅에 넣지 않았다 — 링크 확인은 네트워크가 필요해 커밋을 불안정하게 만든다.
# 기본은 오프라인 검사만 하고, 링크 생존은 `--net` 을 줄 때만 확인한다.
import json, os, re, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
STALE_DAYS = 60


def main():
    src = open(os.path.join(HERE, 'admissions-links.js'), encoding='utf-8').read()
    d = json.loads(open(os.path.join(HERE, 'data.js'), encoding='utf-8').read()[len('window.IPSI = '):-1])
    uni_dict = d['dicts']['uni']
    ui = d['schema'].index('uni')
    live = {uni_dict[r[ui]] if isinstance(r[ui], int) else r[ui] for r in d['rows']}

    m = re.search(r'universities:\s*(\{.*?\n  \})', src, re.S)
    if not m:
        print('FAIL  universities 블록을 찾지 못했다 — 파일 구조가 바뀌었나'); return 1
    keys = re.findall(r"^\s{4}'([^']+)':", m.group(1), re.M)
    urls = sorted(set(re.findall(r"'(https://[^']+)'", src)))
    checked = (re.search(r"checkedOn:\s*'([\d-]+)'", src) or [None, ''])[1]

    fails = []
    bad = [k for k in keys if k not in live]
    print(f'대학명 키 {len(keys)}개 · URL {len(urls)}개 · 확인일 {checked or "(없음)"}')
    if bad:
        fails.append(f'데이터에 없는 대학명 {len(bad)}건')
        for k in bad:
            near = [u for u in live if k[:2] in u][:3]
            print(f'  ✗ {k} — data.js 에 없다. 링크가 절대 표시되지 않는다. 비슷한 이름: {near}')
    else:
        print(f'  ✓ 키 {len(keys)}개 전부 data.js 의 대학명과 일치')
    print(f'  · 공식 링크 {len(keys)}교 / 전체 {len(live)}교 — 나머지 {len(live) - len(keys)}교는 검색 폴백')

    if checked:
        age = (datetime.date.today() - datetime.date.fromisoformat(checked)).days
        print(f'  {"✓" if age <= STALE_DAYS else "✗"} 확인일 {checked} ({age}일 전)')
        if age > STALE_DAYS:
            fails.append(f'확인일이 {age}일 지났다 — 링크 재확인 후 checkedOn 갱신')
    else:
        fails.append('checkedOn 이 없다')

    if '--net' in sys.argv:
        import urllib.request, concurrent.futures
        def chk(u):
            try:
                req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    return (u, r.status, '')
            except Exception as e:
                return (u, 0, f'{type(e).__name__}: {e}'[:60])
        with concurrent.futures.ThreadPoolExecutor(8) as ex:
            res = list(ex.map(chk, urls))
        dead = [(u, s, e) for u, s, e in res if s != 200]
        print(f'  {"✓" if not dead else "✗"} 링크 생존 {len(res) - len(dead)}/{len(res)}')
        for u, s, e in dead:
            print(f'    ✗ {s or e}  {u}')
        if dead:
            fails.append(f'죽은 링크 {len(dead)}건')
    else:
        print('  · 링크 생존은 미확인 — `python3 qa_official_links.py --net` 로 확인한다')

    print('\n' + ('FAIL  ' + ' · '.join(fails) if fails else 'OK  공식 링크 이상 없음'))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
