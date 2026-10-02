# 대행사 경쟁률 페이지 파서 v2 — v1 의 두 가지 결함을 고쳤다.
#
# 결함1) 전형명을 '경쟁률 현황' 헤더 바로 앞줄로 잡았다.
#        대전대처럼 전형명 다음에 전형방법(`[교과/출석 100%]`)이 오는 페이지에서 방법을 전형명으로 오인했다.
#        → 페이지의 <option> 전형 목록을 먼저 읽고, 헤더 앞 3줄 중 그 목록에 있는 것을 전형명으로 쓴다.
#
# 결함2) '모집단위 다음 3줄이 모집·지원·경쟁률'이라고 가정했다.
#        컬럼이 [대학 | 모집단위 | 학과소개 | 모집 | 지원 | 경쟁률] 인 페이지에서는 학과소개(진로 설명)를
#        모집단위로 잡았다. 한서대·남서울대·상지대·가톨릭관동대의 '진로 설명이 학과명' 현상이 이것이다.
#        게다가 대학·학과소개 열은 rowspan 으로 생략되기도 해 오프셋이 행마다 다르다.
#        → 경쟁률에서 거슬러 올라가며 비숫자 줄을 최대 3개까지 **후보**로 모아 둔다.
#          어느 것이 모집단위인지는 대조하는 쪽에서 우리 학과명과 맞춰 고른다.
import re, html

RATIO = re.compile(r'^([\d.]+)\s*:\s*1$')
NUM   = re.compile(r'^([\d,]+)$')
HDR   = re.compile(r'경쟁률\s*현황')
COLS  = {'모집단위', '모집인원', '지원인원', '경쟁률', '계열', '구분', '캠퍼스', '단과대학', '대학',
         '모집단위명', '총모집인원', '지원', '인원', '전형명', '학부(과)', '학과', '학과소개', '전형'}
SKIP  = {'소계', '합계', '총계', '계', '정원내', '정원외', '누계'}


def _options(s):
    o = set()
    for m in re.finditer(r"<option[^>]*>(.*?)</option>", s, re.S):
        t = html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
        if t and not t.startswith('=') and t not in ('전형 전체',):
            o.add(t)
    for m in re.finditer(r"new Option\('([^']+)'", s):
        t = html.unescape(m.group(1)).strip()
        if t and not t.startswith('='):
            o.add(t)
    return o


def parse(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    opts = _options(s)
    txt = html.unescape(re.sub(r'<[^>]+>', '\n', s))
    L = [l.strip() for l in txt.split('\n') if l.strip()]
    out, cur, active = {}, None, False
    for i, l in enumerate(L):
        if HDR.search(l) or l == '전형 경쟁률':          # 경일대 2027 은 표 제목이 '전형 경쟁률'
            nm = HDR.sub('', l).strip() if l != '전형 경쟁률' else ''
            camp = ''
            if re.fullmatch(r'\((.{1,6})\)', nm):          # '경쟁률 현황 (죽전)' — 캠퍼스 꼬리는 전형명이 아니다(단국대 2027)
                camp, nm = nm, ''
            if not nm:                                    # 헤더 앞 3줄에서 전형 옵션과 일치하는 것을 찾는다
                back_lines = [L[i - b].strip() for b in (1, 2, 3) if i - b >= 0]
                # '(학생부100%)'·'[교과 100%]' 같은 전형방법 줄은 전형명이 아니다 — 한라·한세 2027
                # 대진대 2027 은 괄호 없이 '교과70% + 면접30%' — 비율이 있고 '전형'이 없으면 방법 줄로 본다
                back_lines = [c for c in back_lines
                              if not (re.match(r'^[\[(].*%', c) or (re.search(r'\d\s*%', c) and '전형' not in c))]
                for c in back_lines:
                    if c in opts or any(c == o or (len(c) > 3 and c in o) for o in opts):
                        nm = c
                        break
                if not nm and back_lines:
                    nm = back_lines[0]
            cur = ((nm + ' ' + camp).strip() if nm else '') or cur
            nxt = [x.strip() for x in L[i+1:i+8]]
            # '모집단위(전공명)'(동명대)·'세부 학과(과, 전공)'(선문대) 같은 변형 머리글도 받는다
            active = any(x in ('모집단위', '모집단위명', '학부(과)', '학과')
                         or re.match(r'^(모집단위\(|세부\s*학과)', x) for x in nxt)
            continue
        if not active or cur is None:
            continue
        if not RATIO.match(l):
            continue
        if i < 3 or not (NUM.match(L[i-1]) and NUM.match(L[i-2])):
            continue
        ap = int(L[i-1].replace(',', ''))
        mo = int(L[i-2].replace(',', ''))
        cr = float(RATIO.match(l).group(1))
        cands = []
        for back in range(3, 7):                          # 숫자 앞의 비숫자 줄을 최대 4개까지 후보로
            j = i - back
            if j < 0:
                break
            c = L[j].strip()
            if NUM.match(c) or RATIO.match(c):
                break
            if c in COLS or c in SKIP or not re.search(r'[가-힣A-Za-z]', c):
                continue
            cands.append(c)
        if cands:
            out.setdefault(cur, []).append({'cands': cands, 'mo': mo, 'ap': ap, 'cr': cr})
    return out


def nz(x):
    return re.sub(r'[\s()\[\]{}·,・/\-~ㆍ]', '', x)


def parse_summary(path):
    """'전형별 경쟁률 현황' 합계표 → {전형명: {mo, ap, cr}}.
    교대·한동대 2027 페이지는 모집단위 표 없이 이 표만 있다(모집단위가 사실상 하나라서)."""
    s = open(path, encoding='utf-8', errors='replace').read()
    L = [l.strip() for l in html.unescape(re.sub(r'<[^>]+>', '\n', s)).split('\n') if l.strip()]
    out = {}
    for i, l in enumerate(L):
        if not (re.search(r'전형별\s*경쟁률\s*현황', l) or (l == '경쟁률 현황' and i and L[i-1] == '전형별')):
            continue
        j = i + 1
        while j < len(L) and re.search(r'경쟁률\s*현황', L[j]):    # 유웨이는 제목 줄이 두 번 나온다(서울교대)
            j += 1
        while j + 3 < len(L):
            nm, a, b, c = L[j], L[j+1], L[j+2], L[j+3]
            if nm in SKIP or re.search(r'경쟁률\s*현황', nm):
                break
            if NUM.match(a) and NUM.match(b) and RATIO.match(c) and not NUM.match(nm) and nm not in COLS:
                out[nm] = {'mo': int(a.replace(',', '')), 'ap': int(b.replace(',', '')),
                           'cr': float(RATIO.match(c).group(1)), 'cands': [nm]}
                j += 4
            else:
                j += 1
        break
    return out
