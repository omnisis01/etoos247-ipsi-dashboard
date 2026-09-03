# -*- coding: utf-8 -*-
# 대학어디가(대교협 대입정보포털) 전형결과 수집 — 2026학년도 결과를 대학×전형유형별로 받는다.
#
# 왜 어디가인가: 대학이 법령에 따라 제출하는 **공식 등록 자료**이고 표기가 표준화돼 있다.
#   개별 대학 홈페이지는 형식이 제각각이고 아예 안 올리는 곳도 있다(서울대는 학과별 입결 미공개).
#   다만 어디가도 무오류가 아니다 — context-notes (46) 참조. |Δ|가 큰 건은 반드시 개별 확인.
#
# 엔드포인트 (2026-09-02 재확인. 2026-07 이후 사이트 개편으로 예전 경로·코드가 바뀌었다):
#   ① 대학 목록  POST /uct/acd/ade/criteriaAndResultPopupUnvAjax.do
#   ② 결과       POST /uct/acd/ade/criteriaAndResultItemNewAjax.do
#        searchSyr=2027 · unvCd=<7자리> · tsrdCmphSlcnArtclUpCd=<20|30|40> · compUnvCd=<빈 문자열>
#   ⚠️ compUnvCd 를 빠뜨리거나 'null' 로 보내면 {"error":{"code":"041"}} 가 온다. **빈 문자열이어야 한다.**
#   ⚠️ CSRF 토큰은 필요 없다. 홈으로 세션 쿠키만 한 번 받으면 된다.
#   탭 코드: 20=학생부종합 · 30=학생부교과 · 40=수능위주(정시). 10=공통(결과표 없음).
import json, os, re, sys, time, html, urllib.request, urllib.parse, http.cookiejar

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 'https://www.adiga.kr'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36'
TABS = {'20': '학생부종합', '30': '학생부교과', '40': '수능위주'}

_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _post(path, data, referer=BASE + '/'):
    req = urllib.request.Request(BASE + path, data=urllib.parse.urlencode(data).encode(),
                                 headers={'User-Agent': UA, 'Referer': referer,
                                          'X-Requested-With': 'XMLHttpRequest'})
    return _op.open(req, timeout=60).read().decode('utf-8', 'replace')


def warmup():
    _op.open(urllib.request.Request(BASE + '/', headers={'User-Agent': UA}), timeout=60).read()


def uni_list():
    t = _post('/uct/acd/ade/criteriaAndResultPopupUnvAjax.do',
              {'searchSyr': '2027', 'unvCd': '0000019', 'compUnvCd': '', 'searchUnvComp': '0',
               'tsrdCmphSlcnArtclUpCd': '30', 'searchStdClsfRgnCn': ''})
    out = {}
    for code, body in re.findall(r'<li onclick="fnSelUnv\(&quot;(\d{7})&quot;\);">(.*?)</li>', t, re.S):
        nm = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', body))).strip()
        if nm:
            out[nm] = code
    return out


def _cells(tr):
    return [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', c))).strip()
            for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', tr, re.S)]


def fetch(unv_cd, tab):
    """(전형명, [행]) 목록. 행은 셀 문자열 배열 그대로 — 해석은 소비자 몫."""
    t = _post('/uct/acd/ade/criteriaAndResultItemNewAjax.do',
              {'searchSyr': '2027', 'unvCd': unv_cd, 'tsrdCmphSlcnArtclUpCd': tab, 'compUnvCd': ''},
              referer=BASE + '/uct/acd/ade/criteriaAndResultPopup.do')
    if '"error"' in t[:200]:
        raise SystemExit(f'FAIL adiga 응답 오류 (unvCd={unv_cd} tab={tab}): {t[:120]}')
    # h5 제목과 바로 뒤 table 을 문서 순서로 짝짓는다 — 제목이 표 바깥이라 DOM 중첩으론 못 잡는다.
    parts = re.split(r'(<h5[^>]*>.*?</h5>)', t, flags=re.S)
    out, cap = [], None
    for p in parts:
        if p.startswith('<h5'):
            cap = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', p))).strip()
        elif cap and '<table' in p:
            tb = re.search(r'<table.*?</table>', p, re.S)
            if tb:
                rows = [_cells(tr) for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', tb.group(0), re.S)]
                out.append({'jh': cap, 'rows': [r for r in rows if r]})
                cap = None
    return out


def main():
    warmup()
    unis = uni_list()
    json.dump(unis, open(os.path.join(HERE, 'uni_codes.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'대학 코드 {len(unis)}개')
    want = sys.argv[1:] or list(unis)
    res = {}
    for i, nm in enumerate(want, 1):
        code = unis.get(nm) or next((v for k, v in unis.items() if k.startswith(nm)), None)
        if not code:
            print(f'  ? {nm} — 코드 없음'); continue
        res[nm] = {}
        for tab, label in TABS.items():
            try:
                res[nm][label] = fetch(code, tab)
            except Exception as e:
                print(f'  ! {nm}/{label}: {e}'); res[nm][label] = []
            time.sleep(0.3)
        n = sum(len(v) for v in res[nm].values())
        print(f'  [{i}/{len(want)}] {nm} ({code}) — 표 {n}개')
    out = os.path.join(HERE, 'adiga_raw.json')
    json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'저장 {out} ({os.path.getsize(out)//1024} KB)')


if __name__ == '__main__':
    main()
