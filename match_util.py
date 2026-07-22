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
    import difflib
    names = [norm_jh(key(c)) for c in cands]
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
    print(('실패 %d건' % bad) if bad else '전 케이스 통과')
    raise SystemExit(1 if bad else 0)
