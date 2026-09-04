# 외부 입결·요강 자료를 대시보드 행과 조인할 때 쓰는 정규화 함수 모음 + 자기검증
#
# ⚠️ 이 파일이 존재하는 이유: 2026-07-22 하루에 조인 버그를 세 번 냈다.
#    ① 계열 필터를 `KD[kk] in dept` 로 써서 항상 참 → 의과 시트 값이 한의·약학으로 샜다.
#    ② 조인 키에서 모집단위를 빠뜨려 이화여대 동일 전형명 두 모집단위가 뒤섞였다.
#    ③ 전형명 정규화가 로마숫자를 지워 '일반전형 I'과 'II', '덕성인재Ⅰ'과 'Ⅱ'가 같아졌다.
#       이것 하나로 불일치가 64건으로 부풀었고(서울시립대 Δ1.46·덕성 Δ0.30이 전부 허위),
#       고치니 24건으로 줄었다.
#
# 규칙 셋. 즉석에서 정규화를 다시 짜지 말고 여기 것을 쓸 것.
#   1) 숫자·로마숫자는 의미를 가르는 유일한 표지다. 절대 지우지 말고 아라비아 숫자로 통일한다.
#   2) 조인 키는 (대학, 전형유형, 모집단위, 전형명) 넷을 모두 포함한다. 하나라도 빼면 섞인다.
#   3) 유사도 매칭(difflib)은 최후 수단이다. 후보가 둘 이상 남으면 매칭하지 말고 건너뛴다 —
#      틀린 매칭은 결측보다 나쁘다.
import re

# 대학명 이형 → 대시보드 표기 기준. 소스마다 약칭·캠퍼스 표기가 달라 여기서 흡수한다.
UNI_ALIAS = {
    '경상국립대': '경상대', '차의과대': '차의과학대', '강원대': '강원대(춘천)',
    '한국외대': '한국외국어대', '경희대(서울)': '경희대', '경희대(국제)': '경희대',
    '전남대(광주)': '전남대', '전남대(여수)': '전남대', '한양대(에리카)': '한양대(ERICA)',
    '중앙대(서울안성)': '중앙대', '홍익대(서울세종)': '홍익대',
    # 국립대 개명(2023~2024) — 대학어디가는 새 이름을, 원천 엑셀은 옛 이름을 쓴다.
    # ⚠️ 키는 **정규화 뒤 형태**여야 한다('대학교'→'대' 치환이 먼저 일어난다).
    #    '국립공주대학교'로 적으면 영원히 매칭되지 않는다 — 실제로 그렇게 30교가 통째로 빠져 있었다.
    '국립공주대': '공주대', '국립군산대': '군산대', '국립금오공과대': '금오공과대',
    '국립목포대': '목포대', '국립목포해양대': '목포해양대', '국립부경대': '부경대',
    '국립순천대': '순천대', '국립창원대': '창원대', '한경국립대': '한경대',
    '국립한국교통대': '한국교통대', '국립한국해양대': '한국해양대', '국립한밭대': '한밭대',
    '국립경국대': '경국대', '국립강릉원주대': '강릉원주대',
}


def norm_uni(x):
    """대학명 정규화. '가천대학교'/'가천대' → '가천대'. 개행 뒤 부기(예: '부산대\\n[학석사]')는 버린다."""
    x = (x or '').split('\n')[0].strip().replace(' ', '')
    x = re.sub(r'대학교', '대', x).replace('여자대', '여대')
    return UNI_ALIAS.get(x, x)


def norm_dept(x):
    """모집단위 정규화. 괄호·가운뎃점·쉼표·공백만 제거하고 글자는 보존한다.
    대소문자는 통일한다 — 'Science기반자유전공학부'와 'SCIENCE기반자유전공학부'가
    다른 것으로 잡혀 서강대 보강 후보 하나를 놓친 적이 있다."""
    return re.sub(r'[\s·,()]', '', (x or '')).lower()


def norm_jh(x):
    """전형명 정규화.
    ⚠️ 로마숫자 Ⅰ/Ⅱ/Ⅲ, 영문 I/II/III는 아라비아 숫자로 바꿔 '보존'한다. 지우면 안 된다.
    '전형'은 위치와 무관하게 제거한다('지역인재 I 유형전형(호남권)'처럼 중간에 오는 경우가 있다)."""
    x = (x or '').split('\n')[0]
    x = x.replace('Ⅲ', '3').replace('Ⅱ', '2').replace('Ⅰ', '1')
    x = re.sub(r'\bIII\b', '3', x)
    x = re.sub(r'\bII\b', '2', x)
    x = re.sub(r'\bI\b', '1', x)
    x = x.replace('전형', '')
    return re.sub(r'[\s·()\[\]\-,]', '', x).lower()


def join_key(uni, jhtype, dept, jhname):
    """조인 키. 넷을 모두 쓴다 — 규칙 2."""
    return (norm_uni(uni), jhtype, norm_dept(dept), norm_jh(jhname))


def pick_one(cands, jhname, key=lambda c: c['jn'], cutoff=0.75):
    """후보 중 전형명이 맞는 하나를 고른다. 모호하면 None(=건너뜀) — 규칙 3.
    반환: (선택된 후보 또는 None, 사유)"""
    want = norm_jh(jhname)
    exact = [c for c in cands if norm_jh(key(c)) == want]
    if len(exact) == 1:
        return exact[0], 'exact'
    if len(exact) > 1:
        return None, f'모호(정확일치 {len(exact)}건)'
    # ⚠️ 규칙 1은 정규화에서만 지키면 소용없다 — **유사도 단계에서 다시 뭉개진다.**
    #    '한림케어2' vs '한림케어1' 은 difflib 유사도 0.80 > cutoff 0.75 라 매칭돼 버렸고,
    #    실제로 한림대 법학과 '한림케어 II' 가 어디가 '한림케어전형1' 에 붙었다(2026-09-04 발견).
    #    숫자가 다르면 다른 전형이다 — fuzzy 후보에서 아예 뺀다.
    import difflib
    def _digits(s):
        return re.findall(r'\d', s)
    want_d = _digits(want)
    names = [norm_jh(key(c)) for c in cands if _digits(norm_jh(key(c))) == want_d]
    if not names:
        return None, '후보없음(숫자 불일치로 전부 제외)'
    m = difflib.get_close_matches(want, names, n=2, cutoff=cutoff)
    if len(m) == 1:
        return next(c for c in cands if norm_jh(key(c)) == m[0]), 'fuzzy'
    return None, ('후보없음' if not m else f'모호(유사 {len(m)}건)')


# ------------------------------------------------------------------ 자기검증
# 실제로 당했던 사례를 그대로 넣었다. 이 파일을 직접 실행하면 돌아간다.
_CASES = [
    # (설명, 기대 '다름' 여부, a, b)
    ('로마숫자 Ⅰ vs Ⅱ 는 달라야 한다', True, '학생부종합전형 I', '학생부종합전형 II'),
    ('덕성인재Ⅰ vs Ⅱ 도 달라야 한다', True, '덕성인재 I (서류형)전형', '덕성인재 II (면접형)전형'),
    ('아라비아/로마 표기는 같아야 한다', False, '지역인재 I 유형전형(호남권)', '지역인재 1유형(호남권)'),
    ('사배자 Ⅲ 도 구분', True, '사회적배려대상자 II 전형', '사회적배려대상자 III 전형'),
    ('공백·괄호 차이는 흡수', False, '학교장추천자 전형', '학교장추천자전형'),
]
_DEPT_CASES = [
    ('대소문자는 흡수', False, 'Science기반자유전공학부', 'SCIENCE기반자유전공학부'),
    ('줄바꿈·괄호는 흡수', False, '인문학부(국어국문학,사학,\n철학,종교학)', '인문학부(국어국문학, 사학, 철학, 종교학)'),
    ('다른 학과는 달라야 한다', True, '의예과', '치의예과'),
]

if __name__ == '__main__':
    bad = 0
    for desc, want_diff, a, b in _CASES:
        got_diff = norm_jh(a) != norm_jh(b)
        ok = got_diff == want_diff
        bad += not ok
        print(f"  {'OK ' if ok else 'FAIL'} {desc}: {norm_jh(a)!r} vs {norm_jh(b)!r}")
    for desc, want_diff, a, b in _DEPT_CASES:
        got_diff = norm_dept(a) != norm_dept(b)
        ok = got_diff == want_diff
        bad += not ok
        print(f"  {'OK ' if ok else 'FAIL'} {desc}: {norm_dept(a)!r} vs {norm_dept(b)!r}")
    # 모호하면 고르지 않는다
    cands = [{'jn': '일반전형 I'}, {'jn': '일반전형 II'}]
    got, why = pick_one(cands, '일반전형')
    ok = got is None
    bad += not ok
    print(f"  {'OK ' if ok else 'FAIL'} 모호할 때 매칭 거부: {why}")
    # ⚠️ 규칙 1은 pick_one 까지 지켜야 한다 — 정규화만 고쳐도 fuzzy 에서 다시 뭉개진다.
    #    '한림케어2' vs '한림케어1' 유사도 0.80 > cutoff 0.75 로 실제 오매칭이 났었다.
    for desc, want, cs, expect in (
            ('숫자 다른 전형에 fuzzy 로 붙지 않는다', '한림케어 II 전형',
             [{'jn': '학교생활우수자전형'}, {'jn': '한림케어전형1'}], None),
            ('숫자가 같으면 정상 매칭된다', '한림케어 I 전형',
             [{'jn': '학교생활우수자전형'}, {'jn': '한림케어전형1'}], '한림케어전형1')):
        got, why = pick_one(cs, want)
        ok = (got is None) if expect is None else (got and got['jn'] == expect)
        bad += not ok
        print(f"  {'OK ' if ok else 'FAIL'} {desc}: {why}")
    print(('실패 %d건' % bad) if bad else '전 케이스 통과')
    raise SystemExit(1 if bad else 0)
