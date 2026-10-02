# 2027 수시 최종 경쟁률 페이지 수집기 — agency_links.json 의 2026 주소에서 2027 주소를 찾아 내려받는다.
#
# 주소를 찾는 법 (2026-09-30 실측)
#   · 유웨이: 주소는 base64 로 감싼 뒤섞인 문자열이지만, **'fTf' 바로 앞 한 글자만 연도**다.
#       2024 'z' · 2025 '#' · 2026 '-' · 2027 '7'. 대학 부분은 해마다 같다(경희·중앙·경북·고려·국민 5교로 확인).
#   · 진학: Ratio{대학코드 4자리}{일련번호 3자리}1. 대학코드는 고정, 일련번호는 대학마다 다르게 는다
#       (건국대 2026 031 → 2027 038). 계산할 수 없으므로 2026 번호 다음부터 차례로 열어 본다.
#
# 받은 페이지는 **'2027학년도' + '수시' + 대학명**이 모두 있어야 채택한다. 편입·재외국민·정시 페이지를 거른다.
# '최종' 문구가 없으면 마감 전 중간 집계일 수 있어 따로 표시한다(README ⚠️2).
#
# 저장: 페이지는 Drive 원천자료 폴더(git 밖)에 둔다 — 조사 자료를 /tmp 에 두었다가 재부팅으로 잃은 적이 있다.
#   <Drive>/ipsi-dashboard-2027/2027_수시경쟁률_원문/pages/NNN.html  (전부 UTF-8 로 변환)
#   <Drive>/ipsi-dashboard-2027/2027_수시경쟁률_원문/pages/index.tsv  (2026 과 같은 형식 — ratio_parse 가 그대로 읽는다)
# 찾은 주소는 agency_links.json 의 '27' 키에 적는다.
import os, re, json, time, base64, sys, urllib.request, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(os.path.dirname(DASH), '2027_수시경쟁률_원문', 'pages')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36'
DELAY = 0.4                       # 요청 간격(초) — 대행사 서버 배려
JIN_WINDOW = int(os.environ.get('JIN_WINDOW', 30))   # 진학 일련번호를 2026 다음부터 몇 개까지 볼지
# ⚠️ 2026 추가모집을 많이 한 대학은 30개 창이 전부 '2026 추가' 페이지로 차 2027 수시가 밖으로 밀린다
#    (이화여대 154→183 이 전부 2026 추가였다). 실패하면 JIN_WINDOW=90 으로 그 대학만 다시 돌린다.
CTX = ssl.create_default_context()


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
            raw = r.read()
    except Exception:
        return None
    for enc in ('utf-8', 'euc-kr', 'cp949'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def text(h):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h))


def base_name(uni):
    """'고려대학교(세종)' → '고려대' — 페이지 제목과 대조할 핵심 이름."""
    return re.sub(r'\(.*?\)', '', uni).replace('학교', '').strip()


def is_2027_susi(h, uni):
    if not h or len(h) < 2000:
        return False, ''
    t = text(h)
    title = (re.search(r'<title>(.*?)</title>', h, re.S) or [None, ''])[1]
    # 공백을 지우고 비교한다 — 차의과학대 제목이 '차 의과학대학교'로 띄어 써서 걸렸다.
    if base_name(uni).replace(' ', '') not in (title + t[:3000]).replace(' ', ''):
        return False, 'uni'
    if '2027학년도' not in t:
        return False, 'year'
    head = t[:4000]
    if re.search(r'편입|재외국민|정시모집', head) and '수시' not in head:
        return False, 'kind'
    if '수시' not in head:
        return False, 'kind'
    # '2027학년도 수시 재외국민 경쟁률' 처럼 수시 안의 별도 모집도 걸러야 한다 — 명지·서경·세종·숙명을
    # 이 페이지로 받았었다(숙명은 '수시모집 특별전형' = 재외국민·북한이탈주민).
    m = re.search(r'2027학년도(.{0,40}?)경쟁률', t)
    if m and re.search(r'재외|외국인|특별전형|편입|정시', m.group(1)):
        return False, 'kind'
    return True, ('final' if '최종' in t else 'nonfinal')


def uway27(u26):
    tok = u26.rsplit('/', 1)[1]
    raw = base64.b64decode(tok + '=' * (-len(tok) % 4)).decode('latin1')
    i = raw.rfind('fTf')
    if i < 1:
        return []
    out = []
    for body in {raw, 'J^J' + raw[3:] if raw.startswith('JfJ') else raw}:   # 경희대는 2026 만 'JfJ' 로 시작했다
        s = body[:i - 1] + '7' + body[i:]
        out.append('https://ratio.uwayapply.com/' + base64.b64encode(s.encode('latin1')).decode())
    return out


def jin27(u26):
    m = re.search(r'Ratio(\d{4})(\d{3})1\.html', u26)
    if not m:
        return []
    code, seq = m.group(1), int(m.group(2))
    return ['https://addon.jinhakapply.com/RatioV1/RatioH/Ratio%s%03d1.html' % (code, s)
            for s in range(seq + 1, seq + 1 + JIN_WINDOW)]


def main():
    only = set(sys.argv[1:])
    links = json.load(open(os.path.join(HERE, 'agency_links.json'), encoding='utf-8'))
    os.makedirs(OUT, exist_ok=True)
    idx_path = os.path.join(OUT, 'index.tsv')
    done = {}
    if os.path.exists(idx_path):
        for l in open(idx_path, encoding='utf-8'):
            n, u, k, sz, url = l.rstrip('\n').split('\t')
            done[u] = (int(n), k, url)
    num = max([v[0] for v in done.values()] + [0])
    report = {'ok': [], 'nonfinal': [], 'fail': [], 'skip': []}
    for uni, v in links.items():
        if only and uni not in only:
            continue
        if uni in done:
            report['ok'].append(uni); continue
        u26 = (v.get('links') or {}).get('26', '')
        if 'uwayapply' in u26:
            kind, cands = 'uway', uway27(u26)
        elif 'jinhakapply' in u26:
            kind, cands = 'jinhak', jin27(u26)
        else:
            report['skip'].append((uni, u26[:60])); continue
        hit = None; why = []
        for url in cands:
            h = get(url); time.sleep(DELAY)
            ok, tag = is_2027_susi(h, uni)
            if ok:
                hit = (url, h, tag); break
            if h and tag:
                why.append(tag)
        if not hit:
            report['fail'].append((uni, kind, ','.join(sorted(set(why)))[:40])); continue
        url, h, tag = hit
        num += 1
        open(os.path.join(OUT, '%03d.html' % num), 'w', encoding='utf-8').write(h)
        with open(idx_path, 'a', encoding='utf-8') as f:
            f.write('%d\t%s\t%s\t%d\t%s\n' % (num, uni, kind, len(h), url))
        v.setdefault('links', {})['27'] = url
        (report['nonfinal'] if tag == 'nonfinal' else report['ok']).append(uni)
        print('  %-3s %-16s %-6s %s' % ('✅' if tag == 'final' else '⚠️', uni, kind, url[-40:]), flush=True)
    json.dump(links, open(os.path.join(HERE, 'agency_links.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n최종본 %d · 중간집계 의심 %d · 실패 %d · 건너뜀(대행사 아님) %d'
          % (len(report['ok']), len(report['nonfinal']), len(report['fail']), len(report['skip'])))
    for u, k, w in report['fail']:
        print('  실패  %-16s %-6s 사유:%s' % (u, k, w or '페이지 없음'))
    for u, s in report['skip']:
        print('  건너뜀 %-16s %s' % (u, s))
    json.dump(report, open(os.path.join(OUT, '_fetch_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
