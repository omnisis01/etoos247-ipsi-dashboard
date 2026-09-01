# 대행사 페이지 ↔ 우리 데이터 전형/학과 매칭 규칙. 여기만 고치면 대조기 전체가 따라온다.
#
# 실패 원인이었던 것들.
#  · 우리 쪽에서만 '전형' 접미를 떼고 페이지 쪽은 안 뗐다 → '기회균형' vs '기회균형전형' 불일치.
#    이 한 줄이 미매칭 9,275건의 큰 몫이었다.
#  · 페이지 전형명에 '정원내/정원외', '[학생부종합]', '학생부교과(...)' 같은 껍데기가 붙는다.
#  · 껍데기를 벗기면 '일반' 같은 짧은 키가 여러 전형에 포함돼 후보가 여러 개가 된다
#    → 전형유형(교과/종합/논술/실기)으로 먼저 거르고, 그래도 남으면 가장 가까운 하나를 고른다.
import re

TYPE_PAT = [('학생부교과', re.compile(r'학생부\s*교과|교과\s*위주|학생부위주\(교과\)')),
            ('학생부종합', re.compile(r'학생부\s*종합|종합\s*위주|학생부위주\(종합\)')),
            ('논술',       re.compile(r'논술')),
            ('실기/실적',  re.compile(r'실기|실적|특기자')),
            ('특기자',     re.compile(r'특기자'))]


def nz(x):
    return re.sub(r'[\s()\[\]{}·,・/\-~ㆍ:]', '', x)


def _core(x):
    """공백·기호를 지운 뒤 끝의 '전형'을 뗀다. 순서가 중요하다 —
    '학생부교과(일반전형)' 은 괄호 때문에 문자열 끝이 ')' 라서 기호를 먼저 지워야 '전형' 이 잡힌다."""
    x = nz(x)
    y = re.sub(r'전형$', '', x)
    return y or x


def jkey(s):
    """전형명 정규화 — 껍데기를 벗겨 비교 가능한 알맹이만 남긴다.

    ⚠️ 벗기다가 알맹이까지 없어지면 안 된다. '학생부종합 II 전형' 에서 유형어를 떼면 'II' 만 남아
       아무 전형에나 걸린다. 한글이 하나도 안 남으면 유형어를 붙인 형태로 되돌린다.
    """
    s0 = re.sub(r'^\[[^\]]+\]\s*', '', s)                    # [학생부종합] 접두
    s0 = re.sub(r'\(?\s*정원\s*[내외]\s*\)?', '', s0)        # 정원내/정원외
    s0 = s0.strip()
    s1 = re.sub(r'^(학생부위주)?\s*(학생부\s*교과|학생부\s*종합|논술위주|논술|실기/?실적위주|실기/?실적|실기)\s*',
                '', s0)
    k1 = _core(s1)
    # 유형어를 떼고 남은 것이 껍데기뿐이면(예: '학생부교과전형' → '전형') 전형명 자체가 유형명이라는 뜻이다.
    STOP = {'전형', '위주', '선발', '모집', ''}
    if len(k1) >= 2 and re.search(r'[가-힣]', k1) and k1 not in STOP:
        return k1
    k0 = _core(s0)                                            # 유형어를 남긴 형태로 후퇴
    return k0 or k1


def jhtype_of(page_jhname):
    """페이지 전형명 문자열에서 전형유형을 읽어낸다. 못 읽으면 None."""
    for t, p in TYPE_PAT:
        if p.search(page_jhname):
            return t
    return None


def pick(our_jhname, our_jhtype, page_keys):
    """page_keys: {정규화키: [(원본전형명, items)]}
    → 우리 전형에 대응하는 **원본 전형 하나**의 items. 없거나 애매하면 None.

    ⚠️ 키만 보고 합치면 안 된다. 계명대는 '정원내 학생부교과(일반전형)' 과 '정원내 학생부종합(일반전형)'
       이 둘 다 정규화키 '일반' 이라, 키 단위로 합치면 교과 154행과 종합 행이 한 통에 섞인다.
       그래서 유형(교과/종합/논술/실기)까지 맞는 원본이 정확히 하나일 때만 채택한다.
    """
    jk = jkey(our_jhname.replace('\n', ''))
    keys = [jk] if jk in page_keys else [k for k in page_keys if k and jk and (k in jk or jk in k)]
    if not keys:
        return None
    origs = [(orig, items) for k in keys for orig, items in page_keys[k]]
    if len(origs) == 1:
        return origs[0][1]
    # 유형으로 거른다
    typed = [(o, it) for o, it in origs if jhtype_of(o) == our_jhtype]
    if len(typed) == 1:
        return typed[0][1]
    if len(typed) > 1:                       # 같은 유형이 여럿이면 정규화키가 정확히 같은 것 우선
        exact = [(o, it) for o, it in typed if jkey(o) == jk]
        if len(exact) == 1:
            return exact[0][1]
        return None                          # 그래도 애매하면 포기한다(오탐이 미탐보다 비싸다)
    # 유형을 못 읽는 페이지(유형 표기가 없는 사이트)면 키 완전일치만 인정
    exact = [(o, it) for o, it in origs if jkey(o) == jk]
    return exact[0][1] if len(exact) == 1 else None


def is_desc(c):
    """모집단위 칸이 아니라 '학과소개' 칸인지."""
    return c.count(',') >= 2 or c.count('\u00b7') >= 3 or len(c) >= 30


UNIT_TAIL = re.compile(r'(학부|학과|전공|계열|대학|과)$')


def dept_match(our_dept, cands):
    """모집단위 후보에서 우리 학과와 맞는 것을 고른다.

    ⚠️ 부분일치는 함정이 많다. 실제로 겪은 오매칭들.
       · '경영학과' ⊂ '관광경영학과',  '국어교육과' ⊂ '한국어교육과'   → 중간 포함 금지
       · '인문대학 자율학부' vs '인문대학'  → 접두는 같지만 **다른 모집단위**다
       · '화학과' 가 '일본지역문화학과' 의 끝 3자와 우연히 같다        → 접미 경계 확인 필요
       · '상경학부(야)' vs '상경학부'      → 야간/주간은 다른 모집단위다
    그래서 아래 셋만 인정한다.
      (1) 완전일치
      (2) 우리가 페이지명으로 시작하고, 남는 꼬리가 단위어(학부/학과/전공/계열/대학)로 끝나지 않을 것
          — '글로벌어문학부(독어독문…)' 는 허용, '인문대학 자율학부' 는 배제
      (3) 페이지가 우리명으로 끝나고, 앞에 붙은 머리가 단위어로 끝날 것
          — '컴퓨터공학부'+'컴퓨터공학전공' 은 허용, '일본지역문'+'화학과' 는 배제
    """
    raw = our_dept.replace('\n', '')
    night = ('(야)' in raw) or ('（야）' in raw)
    dn = nz(raw)
    pool = [c for c in cands if not is_desc(c)]
    for c in pool:
        if nz(c) == dn:
            return c
    # 야간 학과는 표기가 정확히 같지 않으면 붙이지 않는다(주간과 값이 전혀 다르다)
    if night:
        return None
    # (2) 우리 표기에서 **괄호 안 세부전공만** 벗겨 페이지 원본과 완전일치하는지 본다.
    #     '글로벌어문학부(독어독문,…)' → '글로벌어문학부' 는 허용되지만,
    #     '전자공학부-인공지능'·'첨단기술융합대학 자율학부2'·'자유전공학부(수원)(수리)' 처럼
    #     페이지보다 잘게 쪼개진 별개 트랙은 걸러진다(1:N 이라 자동 매칭이 불가능하다).
    bare = nz(re.sub(r'[（(][^)）]*[)）]', '', raw))
    if len(bare) > 2 and bare != dn:
        for c in pool:
            if nz(c) == bare:
                return c
    for c in pool:
        cz = nz(c)
        if len(cz) > 2 and len(dn) > 2 and len(cz) - len(dn) >= 3 and cz.endswith(dn):
            if UNIT_TAIL.search(cz[:len(cz) - len(dn)]):
                return c
    return None
