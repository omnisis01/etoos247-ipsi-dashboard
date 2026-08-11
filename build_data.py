# -*- coding: utf-8 -*-
"""Build compact, dictionary-encoded data.js for the 수시 dashboard from the master xlsx."""
import openpyxl, re, json, os, html

# 원천 폴더가 '입결' → '입결 및 인사이트'로 개명됨(원천 xlsx 이동). 개명 시 이 경로도 갱신.
SRC = os.path.join(os.path.dirname(__file__), '..', '입결 및 인사이트', 'TongTongTong_2027학년도 수시지원의 모든 것_Final오타 수정 필요.xlsx')
OUT_DIR = os.path.dirname(__file__)

# ---------------------------------------------------------------- load
wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
ws = wb['전체']
raw = [r for r in ws.iter_rows(min_row=4, values_only=True) if r[2] not in (None, '')]

def s(v):
    if v is None: return ''
    return str(v).strip()

def num(v):
    """to float or None"""
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    t = str(v).strip().replace(',', '')
    if t in ('', '-', '–', '—', '없음', '미정', 'N/A'): return None
    m = re.search(r'-?\d+\.?\d*', t)
    return float(m.group()) if m else None

def norm(t):
    return re.sub(r'\s+', '', t or '')

def vgrade(v):
    """입결 등급은 1.0~9.0 범위만 유효. 범위 밖(환산점수 오입력·오타 등)은 무데이터 처리."""
    return v if (v is not None and 1.0 <= v <= 9.0) else None

def std_kind(k):
    """대학이 발표한 입결 기준을 버킷으로 정규화: avg / cut50 / cut70 / cut80 / cut90 / lowest / stage1 / 기타.
       ⚠️ 서로 다른 기준을 한 버킷에 넣으면 필터가 왜곡된다. 실제로 세 건이 섞여 있었다.
        · 50%컷(132행: 서울대·전남대·홍익대)이 cut70에 편입돼 있었다. 50%컷은 70%컷보다
          확실히 낮은(좋은) 값이라 같은 버킷이면 '70%컷 이내' 필터가 과대 포함된다 → cut50 분리.
        · '1단계합격자평균'(345행)·'지원자교과평균'(15행)이 avg에 편입돼 있었다. 1단계 합격자와
          지원자는 최종등록자보다 훨씬 넓은 풀이라 등급이 나쁘게 나온다 → stage1 분리.
        · '최종등록자 논술 정답 개수 평균'(22행, 삼육대)은 등급이 아니라 정답 개수다.
          현재 값이 전부 비어 있어 실해는 없지만 avg로 잡히므로 '' 처리한다.
        · 75·80·85%컷(2,025행 23교)이 cut70에 합류돼 있었다. 관행 범위라 한 묶음으로 봤는데,
          대학어디가 70%컷과 대조하니 영남대(85%컷) 88건·강원대 강릉(75%컷) 71건·
          대전대(80%컷) 56건·동국대 WISE(80%컷) 14건이 계통적으로 어긋났다. 대전대 입학처가
          "성적은 80점수, 평균점수, 최고점수가 기재"라고 공지한 것과 원문이 이미 일치한다 —
          원천 엑셀은 옳았고 이 함수가 뭉갠 것이다 → cut80 분리(2026-07-28)."""
    z = norm(k)
    if not z: return ''
    if '정답' in z: return ''                      # 등급이 아닌 지표
    if '1단계' in z or '지원자' in z: return 'stage1'
    if '평균' in z or '퍙균' in z or '동륵' in z or '차평균' in z: return 'avg'
    import re as _re
    m = _re.search(r'(\d+)%?컷', z) or _re.search(r'(\d+)%?', z)
    if m:
        pct = int(m.group(1))
        if pct >= 88: return 'cut90'
        if pct <= 55: return 'cut50'
        if pct >= 75: return 'cut80'  # 75·80·85% — 70%컷보다 확실히 뒤라 섞으면 필터가 왜곡된다
        return 'cut70'
    if '최저' in z: return 'lowest'   # 최종등록자 최저 = 사실상 100%컷. 90%컷보다도 뒤다.
    if '컷' in z: return 'cut70'
    return ''

# ---------------------------------------------------------------- 전년대비 -> delta int
def parse_delta(prev):
    p = s(prev)
    if not p or p == '-': return ('none', 0)
    if '신설' in p: return ('new', None)
    if '폐지' in p: return ('closed', None)
    if '분리' in p: return ('split', None)
    if '통합' in p: return ('merge', None)
    m = re.search(r'([▲▼△▽▴▾↑↓+\-증감])\s*(\d+)', p)
    if m:
        sign = m.group(1)
        n = int(m.group(2))
        if sign in '▲△▴↑+증': return ('up', n)
        if sign in '▼▽▾↓-감': return ('down', -n)
    m2 = re.search(r'(\d+)', p)
    if m2:
        # bare arrow without number handled above; default neutral
        return ('change', 0)
    return ('change', 0)

# ---------------------------------------------------------------- 최저 변화 (heuristic)
from itertools import product as _product
_LEAST_DIR_CACHE = {}
def least_direction(n1, m1, n2, m2):
    """'N합M' 변화의 방향을 충족 가능 등급조합 집합의 포함관계로 엄밀 판정.
       합(M)만 비교하면 영역 수(N)가 바뀔 때 오판한다.
       실제 사례: 홍익대 '3합8 → 2합5'는 M이 8→5로 줄어 강화처럼 보이지만,
       상위 2개만 보면 되므로 3합8 통과자를 모두 포함하는 '완화'다(72개 전형 오분류였음)."""
    key = (n1, m1, n2, m2)
    if key in _LEAST_DIR_CACHE: return _LEAST_DIR_CACHE[key]
    old, new = set(), set()
    for g in _product(range(1, 10), repeat=4):      # 국·수·영·탐 4개 영역, 1~9등급
        k = tuple(sorted(g))
        if sum(k[:n1]) <= m1: old.add(k)
        if sum(k[:n2]) <= m2: new.add(k)
    if old == new: r = '변경'
    elif old < new: r = '완화'          # 새 조건이 기존 통과자를 전부 포함 + 더 넓음
    elif new < old: r = '강화'
    else: r = '변경'                     # 엇갈림(일부만 유리) → 방향 단정 불가
    _LEAST_DIR_CACHE[key] = r
    return r

def parse_choejeo_change(change_text):
    """returns (kind, detail) where kind in 신설/폐지/완화/강화/변경/None.
    'N합M' 방향은 least_direction()으로 엄밀 판정한다(합 단순 비교는 N 변화 시 오판)."""
    t = s(change_text)
    if not t: return (None, '')
    segs = re.split(r'[\n/·;]', t)
    cseg = None
    for seg in segs:
        if '최저' in seg or ('합' in seg and re.search(r'\d합\d', norm(seg))) or '등급' in seg:
            cseg = seg.strip(); break
    if cseg is None: return (None, '')
    z = norm(cseg)
    if '신설' in z and '최저' in z: return ('신설', cseg)
    if '폐지' in z: return ('폐지', cseg)
    # 합 변경이 '최저'가 든 구간이 아니라 다음 구간에 오는 경우가 있다.
    # 예: '최저:탐,탐→탐(2)과(1) 택1 / 3합6→3합5 / 수학 필수' → 첫 구간엔 영역 지정만 있음.
    # 그래서 구간이 아니라 전체 텍스트에서 'N합M→N합M'을 먼저 찾는다.
    m_all = re.search(r'(\d)합(\d+)→(\d)합(\d+)', norm(t))
    if m_all:
        return (least_direction(int(m_all.group(1)), int(m_all.group(2)),
                                int(m_all.group(3)), int(m_all.group(4))), cseg)
    if '→' in z:
        L, R = z.split('→', 1)
        Lh = re.search(r'(\d)합(\d+)', L); Rh = re.search(r'(\d)합(\d+)', R)
        if '없음' in R and not Rh and ('합' in L or '등급' in L or Lh): return ('폐지', cseg)
        if '없음' in L and (Rh or '합' in R): return ('신설', cseg)
        if Lh and Rh:
            oc, ov = int(Lh.group(1)), int(Lh.group(2))
            nc, nv = int(Rh.group(1)), int(Rh.group(2))
            return (least_direction(oc, ov, nc, nv), cseg)
        Lk = re.search(r'(\d)개(\d+)', L); Rk = re.search(r'(\d)개(\d+)', R)
        if Lk and Rk:
            ov, nv = int(Lk.group(2)), int(Rk.group(2))
            if nv > ov: return ('완화', cseg)
            if nv < ov: return ('강화', cseg)
            return ('변경', cseg)
        return ('변경', cseg)
    if '최저' in z: return ('변경', cseg)
    return (None, '')

# ---------------------------------------------------------------- categorization
# Hardened against substring false-matches per category audit (17 reviewers).
# 정원 외 채용조건형 반도체 계약학과 (산학협력법 근거) — (uni-substring, exact dept)
# ※ 학과명은 '(외)' 표기 제거 후 정규화된 이름 기준.
SEMI_CONTRACT_WHITELIST = [
    ('고려대학교', '반도체공학과'),
    ('연세대학교', '시스템반도체공학과'),
    ('성균관대학교', '반도체시스템공학과'),
    ('서강대학교', '시스템반도체공학과'),
    ('한양대학교', '반도체공학과'),
    ('KAIST', '반도체공학과'),
    ('한국과학기술원', '반도체공학과'),
    ('UNIST', '반도체공학과'),
    ('울산과학기술원', '반도체공학과'),
    ('POSTECH', '반도체공학과(계약학과)'),
    ('포항공과대학교', '반도체공학과(계약학과)'),
]

def categorize(uni, gye, dept, jhname, jagyeok):
    d = norm(dept); head = norm(dept.split('(')[0])
    full = d + norm(jhname) + norm(jagyeok)
    tags = set()
    has = lambda *ks: any(k in d for k in ks)

    # --- teaching (사범): require 교육 as the head noun, not a sub-track ---
    is_edu = (('사범' in d or head.endswith('교육과') or head.endswith('교육학과') or head.endswith('교육학부')
               or head.endswith('교육전공') or '교직' in d or '유아교육' in head or '초등교육' in head)
              and not any(k in d for k in ['평생교육', '교육대학원', '교육사업', '교육서비스', '교육공무', '애견', '반려', '펫']))

    # --- engineering ---
    ENG = ['공학', '공과', '컴퓨터', '소프트웨어', '소프트웨', '전자', '전기', '기계', '신소재', '재료공', '토목',
           '건축', '조선', '항공우주', '우주항공', '자동차', '로봇', '메카트로', '정보통신', '데이터사이언스', '데이터과학',
           '인공지능', '빅데이터', '에너지', '화공', '나노', '제어계측', '시스템공', '반도체', '드론', '모빌리티',
           '정보보안', '사이버보안', '디지털보안', '해킹', '네트워크', 'ICT', '배터리', '이차전지', '산업경영공',
           '자동화', '스마트팩토리', '임베디드', '게임공', '소프트웨어', '인공지능', '정보보호', '통신공']
    eng_exc = (is_edu
               or ('항공' in d and any(x in d for x in ['서비스', '관광', '호텔', '승무', '경영', '외국어']))
               or '도시행정' in d or ('행정' in d and '도시' in d and '공학' not in d)
               or ('보안' in d and any(x in d for x in ['경호', '산업보안']) and '공학' not in d))
    if any(k in d for k in ENG) and not eng_exc:
        tags.add('engineering')
        # 공학 세부 분류 (우선순위 순서대로 1개 배정)
        if any(k in d for k in ['컴퓨터', '소프트웨어', '소프트웨', '인공지능', '데이터사이언스', '데이터과학', '빅데이터',
                                '정보보안', '사이버보안', '정보보호', '게임', 'ICT', '임베디드', '정보시스템', '클라우드',
                                '블록체인', '응용소프트', 'SW']):
            tags.add('eng_cs')
        elif any(k in d for k in ['전자', '전기', '통신', '정보통신', '광공학', '제어', '계측', '반도체', '디스플레이', '전파']):
            tags.add('eng_ee')
        elif any(k in d for k in ['기계', '자동차', '항공', '우주', '조선', '로봇', '메카트로', '자동화', '모빌리티', '드론', '정밀기계']):
            tags.add('eng_mech')
        elif any(k in d for k in ['토목', '건축', '도시', '환경공학', '조경', '교통', '건설', '방재', '지반', '수자원']):
            tags.add('eng_civil')
        elif any(k in d for k in ['화공', '화학공학', '신소재', '재료공', '고분자', '에너지', '나노', '배터리', '이차전지',
                                  '섬유', '생명공학', '바이오공학', '식품공학', '유전공학', '제약공학', '응용화학']):
            tags.add('eng_chem')
        else:
            tags.add('eng_etc')

    # --- natural science (anchored; many excludes) ---
    NAT_EXC = ['공학', '공과', '교육', '의예', '의학', '약학', '간호', '보건', '물리치료', '디자인', '게임', '미디어',
               '콘텐츠', '의류', '패션', '화장품', '뷰티', '향장', '소방', '방재', '경찰', '항해', '철도', '보안',
               '스포츠', '체육', '경영', '경제', '국방', '사관', '문화', '조리', '외식', '반려', '수의', '애견', '펫', '미용']
    NAT_POS = ['수학', '수리과학', '통계', '물리', '생명과학', '생물', '생화학', '미생물', '분자생물', '지구', '지질',
               '천문', '대기과학', '해양학', '해양과학', '농학', '농업', '원예', '산림', '임학', '식물자원', '동물자원',
               '축산', '수산', '식품영양', '영양', '조경', '생태', '자연과학', '화학과', '화학부', '화학전공', '과학기술',
               '바이오', '생명자원', '응용생물', '환경과학']
    if any(k in d for k in NAT_POS) and not any(x in d for x in NAT_EXC):
        tags.add('natural')
        if any(k in d for k in ['수학', '통계', '수리과학']): tags.add('nat_math')
        elif any(k in d for k in ['생명', '생물', '생화학', '미생물', '분자', '유전', '바이오']): tags.add('nat_bio')
        elif any(k in d for k in ['물리', '화학과', '화학부', '화학전공', '응용화학']): tags.add('nat_phys')
        elif any(k in d for k in ['지구', '지질', '천문', '대기', '해양', '우주과학']): tags.add('nat_earth')
        else: tags.add('nat_agri')

    # --- medical core (의·치·한·수·약), head-anchored with blockers ---
    MED_BLOCK = ['스포츠', '식물', '수산', '데이터', '과학수사', '재활', '한방', '제약', '신약', '의약', '창의',
                 '계약', '동물', '보건', '의공', '의료', '문화', '생명의학']
    if not any(x in head for x in MED_BLOCK):
        if '약학' in head or any(t in head for t in ['의예', '의학과', '의학부', '의학전공', '의학계열',
                                                     '치의예', '치의학', '한의예', '한의학', '수의예', '수의학']):
            tags.add('medical')
            # 세부 분류 (의·치·한·수·약) — 우선순위: 치 > 한 > 수 > 약 > 의
            if '치의' in head: tags.add('med_dent')
            elif '한의' in head: tags.add('med_oriental')
            elif '수의' in head: tags.add('med_vet')
            elif '약학' in head: tags.add('med_pharm')
            else: tags.add('med_med')

    # --- nursing & allied health (human) ---
    NH = ['간호', '방사선', '물리치료', '작업치료', '임상병리', '치위생', '응급구조', '재활', '언어치료', '언어청각',
          '언어병리', '청각학', '안경광학', '안경공학', '의공학', '의료공학', '바이오의료', '보건행정', '보건학',
          '보건과학', '보건관리', '보건정보', '보건정책', '보건경영', '치기공', '치과기공', '약과학', '제약', '신약',
          '의약학', '바이오의약', '의생명', '의료정보', '스포츠재활', '운동처방', '의료경영', '의료산업', '보건의료']
    if any(k in d for k in NH) and not any(x in d for x in ['동물', '반려', '수의', '애견', '펫']):
        tags.add('nursing_health')

    # --- business / 상경 ---
    BIZ = ['경영', '경제', '회계학', '무역', '통상', '금융', '세무', '경상', '소비자학', '소비자아동', '부동산',
           '보험', '계리', '외식', '호텔관광', '관광경영', '관광학', '물류', '유통', '핀테크', '경영정보', '비즈니스',
           '상경', '국제통상', '글로벌경영', '자산', '재무', '조세', '마케팅', '이커머스', '무역학']
    if any(k in d for k in BIZ) and not any(x in d for x in ['공학', '공과', '교육', '항공서비스', '승무']):
        tags.add('business')
        if any(k in d for k in ['관광', '호텔', '외식', '카지노', '컨벤션', '레저']): tags.add('biz_tour')
        elif any(k in d for k in ['부동산', '보험', '계리', '소비자', '마케팅', '물류', '유통', '핀테크', '광고']): tags.add('biz_etc')
        elif any(k in d for k in ['경제', '무역', '통상', '금융', '세무', '회계']): tags.add('biz_econ')
        else: tags.add('biz_mgmt')

    # --- language / 어문 ---
    LANG = ['국어국문', '한국어문', '한국어학', '한국언어문화', '영어영문', '영어과', '영어학', '영어전공', '영미',
            '중어중문', '중국어', '중국학', '중국언어문화', '일어일문', '일본어', '일본학', '일본언어문화', '불어불문',
            '프랑스', '독어독문', '독일어', '노어', '러시아', '서어서문', '스페인', '포르투갈', '이탈리아', '아랍',
            '베트남', '태국', '인도', '몽골', '터키', '폴란드', '체코', '헝가리', '우크라이나', '불가리아', '그리스어',
            '문예창작', '통번역', '한문학', '외국어', '글로벌언어', '실용영어', '동양어', '서양어', '언어학', '언어문화', '아시아언어']
    if any(k in d for k in LANG) and not is_edu:
        tags.add('language')
        if any(k in d for k in ['국어국문', '한국어', '국문학', '문예창작', '한문']): tags.add('lang_kor')
        elif any(k in d for k in ['영어', '영문', '영미']): tags.add('lang_eng')
        elif any(k in d for k in ['중어', '중국', '일어', '일본', '동아시아', '아시아언어']): tags.add('lang_asia')
        else: tags.add('lang_etc')

    # --- 문사철(어문 제외) (history/philosophy + non-language literature), anti-greedy ---
    # 어문 계열(국어국문·영어영문 등 language 태그)은 문사철에서 제외한다(사용자 확정).
    # 이전엔 '문학과' substring이 영어영'문학과' 등 외국어문학과 638건을 끌어들이고,
    # 국어국문 등 국문 계열 384건도 이중 태깅돼 문사철 1,558건 중 66%가 어문과 겹쳤다.
    HUM = ['국어국문', '국문학', '한문학', '문예창작', '문학과', '사학과', '한국사', '국사학', '동양사', '서양사',
           '역사학', '역사문화', '미술사', '고고', '철학', '윤리학', '종교', '신학과', '신학부', '기독교', '불교',
           '선교', '목회', '인문학부', '인문콘텐츠', '문화재', '역사학과', '사학전공']
    if (any(k in d for k in HUM) and 'language' not in tags
            and not any(x in d for x in ['교육', '군사', '수사', '천문', '통신', '과학수사'])):
        tags.add('humanities_core')

    # --- social science ---
    SOC = ['정치외교', '행정', '사회학', '심리', '미디어', '언론', '신문방송', '커뮤니케이션', '광고홍보', '홍보광고',
           '광고', '사회복지', '지리', '국제관계', '국제학', '문화인류', '경찰행정', '경찰', '법학', '법률', '정책',
           '공공인재', '공공행정', '사회과학', '문헌정보', '상담', '아동', '가족복지', '복지', '휴먼서비스']
    soc_arts = any(x in d for x in ['디자인', '웹툰', '애니', '크리에이터', '뷰티', '미용', '게임'])
    if any(k in d for k in SOC) and not is_edu and not soc_arts:
        tags.add('social_science')

    # --- 비상경 = 인문계 minus 상경 ---
    if gye == '인문' and 'business' not in tags:
        tags.add('non_business_humanities')

    # --- statistics ---
    if '통계' in d:
        tags.add('statistics')

    # --- semiconductor (all) ---
    if '반도체' in d:
        tags.add('semiconductor')

    # --- contract markers (explicit only) ---
    MARK = ['계약학과', '채용조건', '채용연계', '취업연계', '고용연계', '채용약정', '취업약정', '삼성전자', 'SK하이닉스', '하이닉스']
    contract = any(k in full for k in MARK)
    if 'semiconductor' in tags and (contract or any(a in uni and dept.strip() == b for a, b in SEMI_CONTRACT_WHITELIST)):
        tags.add('semiconductor_contract')

    # --- military contract ---
    branch = any(b in dept for b in ['(공군)', '(육군)', '(해군)', '(해병대)', '(해병)', '국군'])
    mil = (has('군사학', '사관', '사이버국방', '항공시스템공학', '국방시스템', '국방AI', '국방기술', '우주국방',
               '드론봇군사', '군사안보', '해군사관', '첨단국방', '국방디지털', '국방반도체', '국방지능융합') or branch)
    if mil and not has('국방경찰행정', '국방산업경영', '국방XR', '국방디자인'):
        tags.add('military')

    # --- other contract (non-semi, non-military) ---
    if contract and 'semiconductor_contract' not in tags and 'military' not in tags:
        tags.add('contract_other')

    # --- teaching ---
    if is_edu:
        tags.add('teaching')

    # --- primary education / 교대 (exclude 한국기술교육대학교) ---
    if ('교육대학교' in uni and '기술' not in uni) or '초등교육' in head:
        tags.add('primary_ed')
        tags.add('teaching')

    # --- IST (the four government science institutes only) ---
    if any(k in uni for k in ['KAIST', '한국과학기술원', 'DGIST', '대구경북과학기술원', 'UNIST', '울산과학기술원',
                              'GIST', '광주과학기술원']) or uni in ('DGIST', 'UNIST', 'GIST', 'KAIST'):
        tags.add('ist')

    # --- 예체능 3분류: 미술 / 음악 / 체육 ---
    # 함정(실측으로 확인): '전공예약'이 '공예'에, '철도자율'이 '도자'에 걸린다. 미술사학은 인문(사학).
    # '디자인'은 공학·뷰티에도 흔해 예체능 계열일 때만 미술로 세고, 뷰티·헤어·메이크업은 미용 계열이라 제외.
    ART = ['미술', '회화', '동양화', '서양화', '조소', '판화', '도예', '도자', '조형', '공예', '서예']
    if ((has(*ART) and not has('전공예약', '철도자', '미술사'))
            or ('디자인' in d and gye.startswith('예체') and not has('뷰티', '헤어', '메이크업', '미용'))):
        tags.add('art_college')
    MUS = ['음악', '성악', '기악', '피아노', '작곡', '관현악', '국악', '타악', '뮤지컬', '보컬']
    if has(*MUS):
        tags.add('music_college')
    PE = ['체육', '스포츠', '무용', '태권도', '유도', '골프', '축구', '야구', '씨름', '승마', '경호']
    if has(*PE):
        tags.add('pe_college')

    # --- free / undeclared major (무전공·광역) ---
    FREE = ['자유전공', '자율전공', '무전공', '전공자유', '전공자율', '자율학부', '자율설계', '자율융합', '자율미래',
            '계열자유', '광역', '학부대학', '열린전공', '전공개방', '첨단융합학부', '계열모집', '자유공학', '광역모집']
    if any(k in d for k in FREE):
        tags.add('free_major')

    # ---------------------------------------------------------------- 미분류 보강
    # 카테고리 감사에서 1,783행(모집 21,260명·8.4%)이 어느 계열에도 안 잡혀 사이드바 탐색에서
    # 통째로 빠지는 문제가 확인됐다. 아래는 그 유형별 보강 규칙이다.
    #  ⚠️ 아래 블록은 '보강'이라 기존 태그를 지우지 않는다(중복 태깅 허용 구조).

    # 소방·재난안전 — 공학(그 외)으로. '안전'만으로는 보건환경안전 등이 섞여 소방/재난과 함께 쓰일 때만.
    if has('소방') or (has('재난') and has('안전')):
        tags.add('eng_etc'); tags.add('engineering')

    # 의류·패션 / 뷰티·미용·화장품 — 의류패션은 예체능(디자인)과 생활과학에 걸치나
    # 학생 탐색 관점에서 '미술'(디자인)로 묶는 것이 실용적이다. 뷰티·미용은 별도 계열이 없어 보건 인접.
    if has('의류', '패션', '섬유'):
        tags.add('art_college')
    if has('뷰티', '미용', '화장품', '메이크업', '헤어'):
        tags.add('art_college')

    # 항공 — 운항·정비·무인기는 공학(기계·항공), 서비스·관광은 상경(관광)으로 이미 분리돼 있다.
    if '항공' in d and not any(x in d for x in ['서비스', '관광', '호텔', '승무', '경영', '외국어']):
        tags.add('eng_mech'); tags.add('engineering')

    # 반려동물·동물보건 — 농림·식품·동물(자연) 하위로.
    if has('반려', '애견', '동물', '펫') and not has('동물자원생명', '동물바이오'):
        tags.add('nat_agri'); tags.add('natural')

    # 웹툰·만화·애니메이션·게임그래픽 — 미술(예체능)로. 단 게임'공학'·게임소프트웨어는 공학이라 제외.
    if has('웹툰', '만화', '애니메이션') or ('게임' in d and not has('공학', '소프트웨어', 'SW', '테크')):
        tags.add('art_college')

    # 영화·영상·사진·방송 — 미술(예체능 영상)로. 미디어커뮤니케이션(사회과학)과는 이미 구분된다.
    if has('영화', '영상', '사진', '방송', '연극', '공연'):
        tags.add('art_college')

    # 수산·해양생명 — 농림·수산(자연). 해양'공학'·조선은 공학이라 제외.
    if has('수산', '해양') and not has('공학', '토목', '조선', '플랜트'):
        tags.add('nat_agri'); tags.add('natural')

    # AI·SW — 기존 ENG 목록의 '인공지능'은 붙여쓴 형태만 잡혀 'AI학과'·'AI.SW학'류가 샜다.
    # ⚠️ \bAI\b 는 한글과 붙은 'AI학과'에서 단어경계가 성립하지 않아 못 잡는다(실측). 대문자 AI를 직접 본다.
    if 'AI' in dept.upper().replace('MAI', '').replace('CHAI', '') or '인공지능' in d:
        tags.add('eng_cs'); tags.add('engineering')

    # 항해·해기·기관 — 해양대 계열. 선박 운항이라 기계·운송 공학으로.
    if has('항해', '해기', '해상운송', '기관시스템', '항만물류'):
        tags.add('eng_mech'); tags.add('engineering')

    # 철도 — 차량·운전·인프라는 기계·건설 공학.
    if '철도' in d and not has('경영', '서비스'):
        tags.add('eng_mech'); tags.add('engineering')

    # 도시계획·조경 — 건설·건축·환경(공학).
    if has('도시계획', '도시공학', '조경', '국토'):
        tags.add('eng_civil'); tags.add('engineering')

    # 스마트팜·농업기계 — 농림(자연).
    if has('스마트팜', '농업시스템', '농기계', '식물의학'):
        tags.add('nat_agri'); tags.add('natural')

    # 통합·묶음 모집 — 개별 학과가 아니라 '전 모집단위'·'단일계열'·'계열N' 형태로 묶여 있어
    # 계열 지정이 원천적으로 불가하다. 누락으로 두지 말고 별도 카테고리로 노출한다.
    if re.search(r'전\s*모집단위|단일계열|^계열\s*\d|그\s*외\s*모집단위|모집단위\s*전체|인터칼리지|'
                 r'미래융합학부|통합선발|자연계열학부|첨단융합계열|글로컬인재학부|창의융합학부', d):
        tags.add('integrated')

    return tags

# 유불리 판정(score/reasons)과 입결·경쟁률 추세(gtrend/ctrend)는 여기서 계산하지 않는다.
# app.js의 verdict()·yoyGrade()·yoyComp()가 브라우저에서 전부 재계산하므로 data.js에 넣으면
# 아무도 읽지 않는 중복 데이터(약 1MB)가 된다. 판정 로직은 app.js 한 곳에만 둔다.

# ---------------------------------------------------------------- build rows
# dictionaries for interning
dicts = {k: {} for k in ['region','sigun','uni','dept','jhname','jagyeok','choejeo','change','method','gradeRatio','subjects','careerSubj','note','date','std']}
order = {k: [] for k in dicts}
def intern(key, val):
    val = s(val)
    dd = dicts[key]
    if val not in dd:
        dd[val] = len(order[key]); order[key].append(val)
    return dd[val]

rows = []
# 알려진 원천(마스터 xlsx) 수능최저 오기 교정 — 외부 소스(2027 요강·토마스·입시위키)로 확인된 것만.
# 마스터 파일을 직접 수정하지 않고 빌드 시 패치한다. (uni, dept, [jhname], old 원문) → new 원문.
LEAST_CORRECTIONS = [
    # 세명대 한의예: '합5'에 합산 영역수(3) 누락 → 3합5 (입시위키·토마스 확인). SMU의료인재·농어촌·기초차상위 3행 공통 문자열.
    {'uni': '세명대학교', 'dept': '한의예과', 'old': '국,수(기미),영 합5', 'new': '국,수(기미),영 3합5'},
    # 계명대 혁신신약 면접전형: 2합12 → 2합10 (2027 요강 원문 + 토마스 확인). 교과 일반/지역은 2합9로 정상.
    {'uni': '계명대학교', 'dept': '혁신신약학과', 'jhname': '면접전형', 'old': '국,수,영,탐(1) 2합12', 'new': '국,수,영,탐(1) 2합10'},
]
_least_fixed = [0]
def apply_least_correction(uni, dept, jhname, choejeo):
    for c in LEAST_CORRECTIONS:
        if c['uni'] == uni and c['dept'] == dept and c.get('jhname', jhname) == jhname and choejeo == c['old']:
            _least_fixed[0] += 1
            return c['new']
    return choejeo

# ---------------------------------------------------------------- 전년대비 재계산
# 원본 엑셀의 '전년대비' 마크는 2026 마스터(ver 8.2) 실측 대조 결과 99.72% 정확하지만
# 52건이 틀렸다(충남대 의예 종합II ▼7 → 실제 변동 없음 등 — 형제 전형 인원을 끌어온 오기).
# 마크는 표시(18▼7)뿐 아니라 유불리 엔진에 최고 가중치(±2)로 들어가 판정을 뒤집는다.
# → 마크를 믿는 대신 작년 실측 스냅샷(enroll26.json)으로 전년대비를 재계산한다.
# 안전장치 3중:
#  · 양쪽 파일 모두 키(대학|학과|전형유형|전형명|지원자격)가 유일한 1:1 행만 —
#    분할/합산(그래뉼래러티) 오해 차단(건양대 사회복지 22+21행 사례)
#  · 마크가 순수 기호(▲N/▼N/-/공란)인 행만 — '신설'·'폐지'·'분리'·'통합'·텍스트는 원본 유지
#    ('신설'인데 2026 존재 13건은 학과 개명 의심 → (B) 전형 변경 과제에서 별도 처리)
#  · 재계산 값이 기존 마크와 같으면 원본 문자열 그대로(불필요한 diff 방지)
_SNAP26 = json.load(open(os.path.join(os.path.dirname(__file__), 'enroll26.json'), encoding='utf-8'))
_E26 = _SNAP26['enroll26']
_KEYS3_26 = set(_SNAP26['keys3'])
_PURE_MARK = re.compile(r'^(-?|[▲▼△▽↑↓]\s*\d+)$')

# ---------------------------------------------------------------- 전형 변경 판정
# 2026 파일에 (대학|학과|전형명)이 — 표기 정규화 후에도 — 존재하지 않는 2027 전형은
# 개편·개명·통합의 결과다(청주대 담임추천→미래인재 실사례). 이때 '전년대비' 마크는
# 전신(前身)이 다른 전형이라 그대로 쓰면 오해를 부른다(사용자 결정: '전형 변경'으로 표기).
# 마크가 숫자여도 대체한다 — 값이 맞더라도 비교 기준 자체가 바뀐 행이기 때문.
# 신설·폐지·분리·통합 마크는 원본 의미가 이미 정확하므로 유지.
def _nz_name(t):
    t = re.sub(r'\s', '', t)
    t = t.replace('Ⅰ', 'I').replace('Ⅱ', 'II').replace('Ⅲ', 'III').replace('·', '').replace('ㆍ', '')
    return re.sub(r'전형$', '', t)
_changed_count = [0]
def is_changed_track(uni, dept_raw, jhname_raw, prev):
    if not _PURE_MARK.fullmatch(prev): return False     # 신설·폐지·분리·통합·텍스트는 원본 유지
    k3 = '|'.join((uni, _nz_name(dept_raw), _nz_name(jhname_raw)))
    if k3 in _KEYS3_26: return False
    _changed_count[0] += 1
    return True
_rawkey = lambda r: '|'.join((s(r[2]), s(r[4]), s(r[5]), s(r[6]), s(r[7])))
_key27_count = {}
for _r in raw:
    _k = _rawkey(_r)
    _key27_count[_k] = _key27_count.get(_k, 0) + 1
# 재계산 예외 — 52건 전건을 '재계산에 쓴 2026값 ↔ 2026 경쟁률' 산술로 재검해 모순 3건을
# 개별 판정한 결과(2건 예외, 1건은 소수1자리 반올림에 따른 검사 오탐으로 재계산 유지).
_E26_OVERRIDES = {
    # 경상국립대 자율전공학부 교과 일반: ver 8.2의 40이 아니라 41이 맞다.
    #  근거 ① 2026 수시요강 총괄표 '자율전공학부 41 41' ② 경쟁률 16.24는 모집 41(지원자 666)로만 재현(40 불가)
    ('경상대학교', '자율전공학부', '학생부교과', '일반전형'): 41,
    # ↓ 경쟁률 산술 래칫(qa_comp_ratio.py)이 지목한 37건 중, 2026 요강 원문으로 확정한 4건.
    #   공통 절차: '경쟁률 × 2026인원 = 지원자(정수)' 제약으로 가능한 인원을 역산 → 인접 후보가
    #   유일한 건만 추려 2026 요강으로 대조. 네 건 모두 역산값과 요강값이 일치했다.
    #   ⚠️ 이 값은 전년대비 마크(▲/▼) 재계산의 근거라 틀리면 증원/감원 신호가 뒤집힌다.
    #      실제로 단국대는 ▲2(유리)로 표시되고 있었으나 교정 후 ▼2(불리)다.
    # 경상국립대 2026 요강(megastudy X26C09003) p28 모집단위표: 약학과 학생부교과 일반 7.
    ('경상대학교', '약학과', '학생부교과', '일반전형'): 7,
    # 국립공주대 2026 요강(CDN) p19 '모집단위 및 모집인원': 한문교육과 학생부종합 일반전형 9.
    ('공주대학교', '한문교육과', '학생부종합', '일반전형'): 9,
    # 국립군산대 2026 요강(megastudy X26C06001) p12 총괄표: 전자공학과 학생부교과 지역인재 I 6.
    ('군산대학교', '전자공학과', '학생부교과', '지역인재 I 전형'): 6,
    # 단국대 2026 요강(megastudy X26C01010) p30 총괄표: 건축학전공(5년제) DKU인재 서류형 8·면접형 8.
    #   스냅샷 4는 서류형/면접형 두 칸 중 하나를 잘못 집은 것으로 보인다.
    ('단국대학교', '건축학전공(5년제)', '학생부종합', 'DKU인재(면접형)전형'): 8,
    # ※ 가톨릭대 AI의공학과 잠재능력우수자서류(역산 9)는 2026 요강 p10이 8로 확인돼 교정하지 않는다.
    #    인원이 아니라 경쟁률(10.56) 쪽 오차다.
}
_RECOMPUTE_SKIP = {
    # 경북대 IT대학 자율학부 논술: 동명이단위 함정. 2026엔 'IT대학 자율학부'(논술 5)와
    # 'IT 첨단자율학부'(논술 10)가 별개로 공존(2026 요강 521·522행 확인). 2027 파일의
    # 'IT대학 자율학부' 논술 10의 전신은 후자다(2026 경쟁률 11.3은 모집 10으로만 재현,
    # 2027에 IT 첨단자율 논술 행이 없음). 동명 키 재계산(5 기준 ▲5)은 오히려 틀리고
    # 원본 마크 '-'(변동 없음)가 단위 연속 관점에서 옳다.
    ('경북대학교', 'IT대학 자율학부', '논술', '논술전형'),
}
_prev_recomputed = []
def recompute_prev(key, enroll_cell, prev):
    # 모집인원 셀이 '순수 숫자'일 때만. '남:4\n여:4' 같은 특수 표기는 num()이 앞 숫자(4)만
    # 뽑아 총원(8)과 달라지므로 재계산하면 오히려 틀린다(단국대 성악전공 실사례 — 제외).
    if not isinstance(enroll_cell, (int, float)) or not _PURE_MARK.fullmatch(prev): return prev
    if _key27_count.get(key) != 1: return prev
    k4 = tuple(key.split('|')[:4])
    if k4 in _RECOMPUTE_SKIP: return prev
    e26 = _E26_OVERRIDES.get(k4) or _E26.get(key)
    if e26 is None: return prev          # 2026에 동일 키 없음(개명·신설·표기차) → 원본 유지
    real = int(enroll_cell) - e26
    new = '-' if real == 0 else (f'▲{real}' if real > 0 else f'▼{-real}')
    old_norm = re.sub(r'\s', '', prev).replace('△', '▲').replace('↑', '▲').replace('▽', '▼').replace('↓', '▼') or '-'
    if new == old_norm: return prev
    _prev_recomputed.append((key, prev or '(공란)', new, e26, int(enroll_cell)))
    return new

# ---------------------------------------------------------------- 모집인원(enroll) 교정
# (A) 2.5라운드 — 대교협 CDN 2027 수시모집요강 원문 대조로 확인된 원본 엑셀(V7.15) 모집인원 오류.
# 근거는 요강 총괄표·모집단위표·정정공지·개편공지(단일 추론 아님). 교정 목록은 data_corrections.json에
# 두어 verify_insights.py(인사이트↔교정후 엑셀 대조)와 공유한다 — 두 곳에 중복 정의하면 표류하므로.
# 키는 (대학, 학과['(외)' 제거후], 전형유형, 전형명). old와 일치할 때만 교정 — 엑셀 갱신으로 값이
# 바뀌면 자동으로 적용을 멈춰(오적용 방지) 최종 리포트에서 미적용으로 드러난다.
_CORR = json.load(open(os.path.join(os.path.dirname(__file__), 'data_corrections.json'), encoding='utf-8'))
_ENROLL_CORRECTIONS = {(c['uni'], c['dept'], c['jht'], c['jhn']): (c['old'], c['new']) for c in _CORR['enroll']}
# 일부 교정은 실제 증감(엑셀이 전년값 방치)이라 전년대비 마크도 함께 바로잡는다(선택 'prev' 필드).
_ENROLL_PREV = {(c['uni'], c['dept'], c['jht'], c['jhn']): c['prev'] for c in _CORR['enroll'] if 'prev' in c}
_enroll_fixed = {}
def apply_enroll_correction(uni, dept, jhtype, jhname, enroll):
    c = _ENROLL_CORRECTIONS.get((uni, dept, jhtype, jhname))
    if c and enroll == c[0]:
        _enroll_fixed[(uni, dept, jhtype, jhname)] = c
        return c[1]
    return enroll

# 유령 행 제거(예: 전남대 여수 '공학계열' — 2026 모집단위가 2027 개편으로 폐지됐으나 엑셀에 잔존).
# 같은 키(대학|학과|전형유형|전형명)에 행이 둘인 경우가 있어(한양대 경제금융 8·17) 선택 'e'(모집인원)로
# 특정한다. 'e' 없으면 해당 키 전체 제거.
_ROW_DROP = {}
for _c in _CORR['drop']:
    if _c.get('dedupe'): continue
    _ROW_DROP.setdefault((_c['uni'], _c['dept'], _c['jht'], _c['jhn']), set()).add(_c.get('e'))
# 완전 중복 행(인원·자격까지 동일) 제거 — 첫 행만 남긴다. 엑셀에 같은 전형이 두 줄 실린 경우.
_ROW_DEDUPE = {(c['uni'], c['dept'], c['jht'], c['jhn']) for c in _CORR['drop'] if c.get('dedupe')}
_dedupe_seen = set()
_dropped = []
_new_wiped = []
_grade_wiped = []

# 전년대비 구분(dkind) 교정. 원천 엑셀이 '신설'로 적었지만 실제로는 기존 전형의 분리·개편인 경우.
# 실사례: 서강대 학생부종합 일반전형 II — 요강 p5 '주요 변경사항'이 "학생부종합 일반전형 전형 분리:
#         학생부종합(일반) → 학생부종합(일반Ⅰ)/(일반Ⅱ)"라고 명시한다. 신설이 아니라 분리다.
#         'new'로 두면 신설 실적 제거가 걸려 같은 모집단위의 2026 입결까지 사라진다.
# 'changed'는 app.js가 '전형 변경(개편·개명) — 전년 대비 인원 비교 불가'로 안내한다.
_DKIND_CORR = {}
for _c in _CORR.get('dkind', []):
    _DKIND_CORR[(_c['uni'], _c['dept'], _c['jht'], _c['jhn'])] = (_c['from'], _c['to'])
_dkind_fixed = set()

# 2026 입결(70%컷) 교정. 원천 엑셀의 입결이 비었거나 다른 판본 값인 경우를 외부 입결자료로 보정한다.
# 근거: '대학전형및3개년입결_메디컬.xlsx'(대학×전형별, 비고에 기준 명시)와
#       '24~26년 3개년 입결 자료.xlsx'(50%/70%컷 분리) 두 종.
# ⚠️ 두 자료는 서로도 메디컬 70%컷 기준 약 25% 불일치한다(판본 차이). 그래서
#    ① 두 자료가 일치하는데 대시보드만 다른 경우와 ② 대시보드가 비어 있는 경우만 반영한다.
#    한쪽 자료만 대시보드와 다른 경우(19건)는 판정 근거가 부족해 손대지 않는다.
# ⚠️ 반영 대상은 전부 std26='최종등록자70%컷' 행이다 — 기준이 다르면 값을 섞으면 안 된다.
_GRADE_CORR = {}
for _c in _CORR.get('ipgyeol', []):
    _GRADE_CORR[(_c['uni'], _c['dept'], _c['jht'], _c['jhn'])] = (_c.get('old'), _c['new'])
_grade_fixed = set()

# 전형명 오기 교정. 인원은 맞는데 이름이 틀린 경우가 있다 —
# 한남대는 실기전형 163명(미술교육·스포츠과학·융합디자인·회화)이 '일반전형'으로 실려
# 교과 일반전형 1,350명과 한 이름으로 섞였고, 중부대는 요강상 별개인 두 전형
# ('학교생활우수자' 교과70+면접30 8명 / '학교생활우수자(항공운항서비스)' 교과50+면접50 21명)이
# 같은 이름으로 실렸다. 학생이 전형을 고르는 화면이라 이름이 틀리면 인원이 맞아도 오해를 부른다.
# 같은 키에 행이 둘이면 'e'(모집인원)로 특정한다.
_ROW_RENAME = {}
for _c in _CORR.get('rename', []):
    _ROW_RENAME.setdefault((_c['uni'], _c['dept'], _c['jht'], _c['jhn']), []).append((_c.get('e'), _c['to']))
_renamed = set()

# 대학별고사 일자 교정. 원본 엑셀에 2026학년도(작년) 일정이 잔존한 13교 — 요일을 2026년
# 달력으로 검산해 검출했고(어긋난 것 전부 2025년 달력과 일치), 각 교 2027 요강 원문으로 확정.
# old가 엑셀 원문과 완전일치할 때만 적용한다. 엑셀이 갱신되면 미적용으로 남아 아래 검증에 걸린다.
_DATE_CORR = {}
for _c in _CORR.get('date', []):
    _DATE_CORR[(_c['uni'], _c['jhn'], _c['old'])] = _c['new']
_date_fixed = set()

# 입결 기준(std) 원문 교정. 원천 엑셀이 '최종등록자컷'처럼 퍼센트 없이 적은 대학을
# 입학처 공식 발표로 확정해 실제 기준으로 바꾼다. 원문만 바꾸면 std_kind()가 버킷을 다시 잡는다.
# ⚠️ 값(g26)은 건드리지 않는다 — 값은 대학 공식값이 맞고 라벨만 틀렸다.
_STD_CORR = {}
for _c in _CORR.get('std', []):
    _STD_CORR[(_c['uni'], _c['from'])] = _c['to']
_std_fixed = set()

# 2026 경쟁률(c26) 교정. 어디가 경쟁률과 대조해 어긋난 건 중, **2026 모집인원 산술로 방향이
# 판정된 것만** 넣는다 — '경쟁률 × 모집인원 = 지원자(정수)' 제약에서 대시보드는 부적합인데
# 어디가는 정합인 경우다. 판정 규약은 qa_comp_ratio.py와 동일하게 맞춘다.
# ⚠️ 두 값의 소수 자릿수가 다르면 판정이 비대칭이다 — 자릿수가 낮은 쪽은 구간이 넓어
#    무조건 통과한다(영남대 7.745 vs 어디가 7.8이 실제로 그랬고, 31/4=7.75라 대시보드가
#    더 정확했다). **양쪽 자릿수가 같을 때만 판정에 쓴다.**
# ⚠️ '두 학과 값이 정확히 뒤바뀌었다'는 것만으로는 방향을 못 가른다 — _note_ipgyeol 참조.
_COMP_CORR = {}
for _c in _CORR.get('comp', []):
    _COMP_CORR[(_c['uni'], _c['dept'], _c['jht'], _c['jhn'])] = (_c['old'], _c['new'])
_comp_fixed = set()

# 캠퍼스(지역) 교정. 원본 엑셀이 학과 소재 캠퍼스를 잘못 배정한 경우(예: 중앙대 약학부 안성→서울).
# ⚠️ 키에 '기존 지역'을 반드시 포함한다. (uni, dept)만으로 매칭하면 같은 학과명이 여러
#    캠퍼스에 있을 때(경상대 진주/통영, 유원대 영동/아산 등) 멀쩡한 행까지 덮어써 버린다.
#    실제로 그 사고를 내고 되돌렸다 — from_region/from_sigun 없는 항목은 받지 않는다.
_REGION_CORR = {}
for _c in _CORR.get('region', []):
    if 'from_region' not in _c or 'from_sigun' not in _c:
        raise SystemExit(f"[중단] region 교정에 from_region/from_sigun 누락: {_c.get('uni')} {_c.get('dept')}")
    _REGION_CORR[(_c['uni'], _c['dept'], _c['from_region'], _c['from_sigun'])] = (_c['region'], _c['sigun'])
_region_fixed = set()

# 원천 학과명 오타 — 전부 **같은 대학 안의 다수 표기와 대조**해 판정했다(외부 근거 불필요).
# 사용자 제보('예제능')를 계기로 전 학과명 3,303종을 유사도 스캔해 찾은 것들이다.
#   둥물→동물(강원춘천 1행, 같은 대학 1행이 정상) · 컴단기술→첨단기술(경북대 1행 vs 정상 11행)
#   소포츠→스포츠(명지·백석 각 1행) · 식품영앙→식품영양(전남대 6행 vs 정상 1행)
#   사람아너스→사림아너스(창원대 1행 vs 정상 2행) · 경영빅데이터과→학과(계명대 1행 vs 정상 6행)
#   HK자율전공학 I→학부 I(한경대 1행, 같은 대학의 다른 행은 '학부')
# ⚠️ 부분 문자열 치환이므로 정상 학과명에 섞이지 않는 어절인지 확인하고 넣을 것.
_DEPT_TYPO = [
    ('스프츠', '스포츠'), ('소포츠', '스포츠'), ('둥물생명', '동물생명'), ('컴단기술', '첨단기술'),
    ('식품영앙', '식품영양'), ('사람아너스', '사림아너스'), ('경영빅데이터과', '경영빅데이터학과'),
    ('HK자율전공학 I', 'HK자율전공학부 I'),
]

cat_counter = {}
audit = {}
for r in raw:
    uni = s(r[2]); gye = s(r[3]); dept = s(r[4]); jhtype = s(r[5]); jhname = s(r[6]); jagyeok = s(r[7])
    # 원천 오타 정규화(최종판 Final에도 남아 있음, 사용자 제보로 발견).
    # ⚠️ 계열은 앞 2글자만 저장하므로 '예제능'이 '예제'라는 유령 계열이 되고,
    #    categorize()의 `gye.startswith('예체')` 분기를 놓쳐 세명대 실내디자인학과
    #    특성화고교인재전형이 **어느 계열에도 안 잡히는** 실피해가 있었다(같은 학과 일반전형은 정상).
    gye = {'예제능': '예체능'}.get(gye, gye)
    for _bad, _good in _DEPT_TYPO: dept = dept.replace(_bad, _good)
    # 학과명 정규화: '(외)' 표기 제거. 정원 외 채용조건형 계약학과는 별도 배지로 노출한다.
    dept = dept.replace('(외)', '').strip()
    _dk = (uni, dept, jhtype, jhname)
    if _dk in _ROW_DROP and (None in _ROW_DROP[_dk] or num(r[8]) in _ROW_DROP[_dk]):
        _dropped.append((_dk, num(r[8]))); continue
    if _dk in _ROW_DEDUPE:
        if _dk in _dedupe_seen: _dropped.append((_dk, 'dedupe')); continue
        _dedupe_seen.add(_dk)
    if _dk in _ROW_RENAME:
        for _e, _to in _ROW_RENAME[_dk]:
            if _e is None or _e == num(r[8]):
                _renamed.add((_dk, _e)); jhname = _to; break
    enroll = apply_enroll_correction(uni, dept, jhtype, jhname, num(r[8])); prev = recompute_prev(_rawkey(r), r[8], s(r[9])); change = s(r[10]); choejeo = apply_least_correction(uni, dept, jhname, s(r[11]))
    if (uni, dept, jhtype, jhname) in _enroll_fixed and (uni, dept, jhtype, jhname) in _ENROLL_PREV:
        prev = _ENROLL_PREV[(uni, dept, jhtype, jhname)]   # 실제 증감 반영 — 엑셀이 방치한 전년대비 마크 교정
    comp = [num(r[18]), num(r[19]), num(r[20])]
    _ck = (uni, dept, jhtype, jhname)
    if _ck in _COMP_CORR:
        _cold, _cnew = _COMP_CORR[_ck]
        if comp[0] is not None and abs(comp[0] - _cold) < 1e-9:
            comp[0] = _cnew; _comp_fixed.add(_ck)
    grade = [vgrade(num(r[22])), vgrade(num(r[27])), vgrade(num(r[31]))]
    _gk = (uni, dept, jhtype, jhname)
    if _gk in _GRADE_CORR:
        _old, _new = _GRADE_CORR[_gk]
        if (grade[0] is None and _old is None) or (grade[0] is not None and _old is not None and abs(grade[0] - _old) < 1e-9):
            grade[0] = _new; _grade_fixed.add(_gk)
    conv = [num(r[23]), num(r[28]), num(r[32])]
    chung = [s(r[24]), s(r[29]), s(r[33])]
    method = s(r[12]); note = s(r[25]); date = s(r[34])
    _dtk = (uni, jhname, date)
    if _dtk in _DATE_CORR:
        date = _DATE_CORR[_dtk]; _date_fixed.add(_dtk)
    gr = s(r[15]); subj = s(r[16]); career = s(r[17])
    # 입결 '기준'은 연도별로 따로 있다(col21=2026, col26=2025, col30=2024). 대학이 해마다 기준을
    # 바꾸기도 해서(예: 2025 평균 → 2026 70%컷) 기준이 다른 두 해의 등급을 비교하면 의미가 없다.
    # 실제로 이 비교 때문에 가짜 입결 추세 신호가 983건 발생했다 → std25도 실어 보내 app.js에서 막는다.
    std26 = s(r[21])
    if (uni, std26) in _STD_CORR:
        std26 = _STD_CORR[(uni, std26)]; _std_fixed.add((uni, s(r[21])))
    stdK = std_kind(std26)
    std25 = s(r[26])
    # ⚠️ 2025 기준 원문도 같이 교정한다. 안 하면 std26만 바뀌어 app.js가 '기준이 달라졌다'로
    #    오판하고 추세 표시를 차단한다(실제로 6교 704행이 이 회귀로 막혔다).
    #    원문이 같은 문자열이면 같은 발표 형식이라는 뜻이다 — 중부대 2025 자료로 확인했다.
    if (uni, std25) in _STD_CORR:
        std25 = _STD_CORR[(uni, std25)]

    if is_changed_track(uni, s(r[4]), jhname, prev):
        delta_kind, delta_n = 'changed', 0
    else:
        delta_kind, delta_n = parse_delta(prev)
    _dkk = (uni, dept, jhtype, jhname)
    if _dkk in _DKIND_CORR and delta_kind == _DKIND_CORR[_dkk][0]:
        delta_kind = _DKIND_CORR[_dkk][1]; delta_n = 0; _dkind_fixed.add(_dkk)
        # ⚠️ prev(전년대비 원문)도 함께 맞춘다. app.js의 표·카드는 dkind로 그리지만
        #    **인쇄물(printFav)과 비교함은 r.prev를 직접 찍는다** — 여기만 '신설'이 남으면
        #    화면에는 '–'인데 PDF에는 '신설'로 나와 서로 어긋난다.
        #    'changed'는 app.js가 '전형변경'으로 대체 출력하므로 건드리지 않는다.
        if delta_kind == 'none':
            prev = '-'
    ch_kind, ch_detail = parse_choejeo_change(change)
    has_choejeo = 0 if (norm(choejeo) in ('', '없음', '미적용', 'X', '-')) else 1

    # 신설 전형의 상속된 과거 실적 제거.
    # 2027 신설 전형에 2025·2026 실적이 있을 수 없는데 원천 엑셀 25행이 같은 학과 다른 전형의
    # 값을 그대로 물려받았다(아주대 의학과 지역의사선발전형에 ACE전형 경쟁률 27.1→34.2가 붙어
    # '경쟁률 상승=불리' 오판정까지 났다). 전년 실적은 학과가 아니라 학과×전형에 귀속된다.
    # data.js 자체에서 비워야 이 값을 쓰는 모든 소비자(앱·하네스·향후 도구)가 한 번에 안전해진다.
    if delta_kind == 'new' and (any(x is not None for x in comp) or any(x is not None for x in grade)
                                or any(x for x in chung)):
        # ⚠️ 이 제거는 입결교정(_GRADE_CORR)보다 뒤에 온다. 신설 행에 입결교정을 걸면
        #    교정은 '적용됨'으로 집계되고 값은 여기서 지워져 조용히 무효가 된다.
        #    실제로 서강대 일반전형 II(2027 신설)에 그런 항목을 넣었다가 발견했다.
        if _gk in _GRADE_CORR:
            _grade_wiped.append(_gk)
        _new_wiped.append((uni, dept, jhtype, jhname))
        comp = [None, None, None]; grade = [None, None, None]
        conv = [None, None, None]; chung = ['', '', '']
        std26 = ''; stdK = ''; std25 = ''

    tags = sorted(categorize(uni, gye, dept, jhname, jagyeok))
    for t in tags:
        cat_counter[t] = cat_counter.get(t, 0) + 1
        audit.setdefault(t, {}).setdefault((uni, dept), 0)
        audit[t][(uni, dept)] += 1

    _reg, _sig = r[0], r[1]
    _rk = (uni, dept, _reg, _sig)
    if _rk in _REGION_CORR:
        _reg, _sig = _REGION_CORR[_rk]; _region_fixed.add(_rk)
    rows.append([
        intern('region', _reg), intern('sigun', _sig), intern('uni', uni), gye[:2],
        intern('dept', dept), jhtype, intern('jhname', jhname), intern('jagyeok', jagyeok),
        enroll, prev, delta_kind, delta_n,
        intern('change', change), intern('choejeo', choejeo), has_choejeo, ch_kind or '',
        comp[0], comp[1], comp[2],
        grade[0], grade[1], grade[2],
        conv[0], conv[1], conv[2],
        chung[0][:12], chung[1][:12], chung[2][:12],
        intern('method', method), intern('note', note), intern('date', date),
        intern('gradeRatio', gr), intern('subjects', subj), intern('careerSubj', career),
        tags,
        intern('std', std26), stdK, intern('std', std25),
    ])

# ---------------------------------------------------------------- 누락 행 보완 (요강 근거)
# 요강 모집단위표에 있으나 원본 엑셀(V7.15)이 누락한 행(예: 부산대 스포츠과학과 농어촌 1명, 요강 p33).
# 신규 유입 모집단위라 3개년 경쟁률·입결 이력이 없다 → 비교 필드는 공란/None(사실대로). prev '-'(중립).
_ADDED_ROWS = _CORR['add']
# 추가 행은 원천에 없던 행이라 전형 공통정보(전형방법·수능최저·지원자격·고사일)가 비어 있었다.
# 상세 카드에서 '전형방법 –'로 보이는 문제가 있어(감사 30행), 같은 대학·전형의 기존 행에서 상속한다.
# 전형 공통정보는 모집단위와 무관하게 동일한 것이 원칙이므로 안전하다.
# ⚠️ 다수결이 아니라 '유일값일 때만' 상속한다. 모집단위별로 값이 갈리면(예: 계열별 상이) 비워 둔다.
_IDX_METHOD, _IDX_CHOEJEO, _IDX_JAG, _IDX_DATE, _IDX_HAS_CJ = 28, 13, 7, 30, 14
def _inherit(u, jt, jn):
    """같은 (대학, 전형유형, 전형명) 기존 행들의 공통 필드를 상속한다.
    유일값이면 그대로, 값이 갈리면 '80% 이상 다수값'만 채택한다(예: 우석 교과100 25행 vs
    군사학과 체력측정 2행 → 교과100 상속). 그마저 애매하면 비워 둔다 — 틀린 정보보다 공란이 낫다."""
    from collections import Counter
    # 전형명 매칭은 '(외)' 표기를 무시한다. 정원 외를 별도 전형명으로 추가한 경우
    # (예: 경일대 조기취업계약학과전형 / 〃(외)) 전형방법은 정원 내와 동일하다.
    _base = jn.replace('(외)', '').strip()
    _cands = {dicts['jhname'].get(k) for k in (jn, _base) if dicts['jhname'].get(k) is not None}
    got = {}
    for _r in rows:
        if dicts['uni'].get(u) != _r[2] or _r[5] != jt or _r[6] not in _cands:
            continue
        for key, idx in (('method', _IDX_METHOD), ('choejeo', _IDX_CHOEJEO),
                         ('jagyeok', _IDX_JAG), ('date', _IDX_DATE), ('hasCj', _IDX_HAS_CJ)):
            got.setdefault(key, []).append(_r[idx])
    out = {}
    for key, vals in got.items():
        cnt = Counter(vals)
        top, n = cnt.most_common(1)[0]
        if len(cnt) == 1 or n / len(vals) >= 0.8:
            out[key] = top
    return out

for _a in _ADDED_ROWS:
    _u, _d, _jt, _jn, _e = _a['uni'], _a['dept'], _a['jht'], _a['jhn'], _a['e']
    _cats = _a['cats']
    _inh = _inherit(_u, _jt, _jn)
    for _t in _cats:
        cat_counter[_t] = cat_counter.get(_t, 0) + 1
        audit.setdefault(_t, {}).setdefault((_u, _d), 0)
        audit[_t][(_u, _d)] += 1
    rows.append([
        intern('region', _a['region']), intern('sigun', _a['sigun']), intern('uni', _u), _a['gye'],
        intern('dept', _d), _jt, intern('jhname', _jn), _inh.get('jagyeok', intern('jagyeok', '')),
        _e, '-', 'none', 0,
        intern('change', ''), _inh.get('choejeo', intern('choejeo', '')), _inh.get('hasCj', 0), '',
        0, 0, 0,
        None, None, None,
        0, 0, 0,
        '', '', '',
        _inh.get('method', intern('method', '')), intern('note', ''), _inh.get('date', intern('date', '')),
        intern('gradeRatio', ''), intern('subjects', ''), intern('careerSubj', ''),
        _cats,
        intern('std', ''), std_kind(''), intern('std', ''),
    ])

# 모집인원 교정 리포트 — 적용 누락(엑셀 값 변동) 즉시 감지
_miss = [k for k in _ENROLL_CORRECTIONS if k not in _enroll_fixed]
_drop_hit = [x for x in _dropped if x[1] != 'dedupe']
_dedupe_hit = [x for x in _dropped if x[1] == 'dedupe']
if _grade_wiped:
    raise SystemExit(f"[입결교정] 신설 행에 건 입결교정 {len(_grade_wiped)}건이 신설 실적 제거로 무효화됨 — "
                     f"data_corrections.json에서 빼거나 해당 행의 신설 판정을 검토할 것: {_grade_wiped}")
print(f"[구분교정] dkind {len(_dkind_fixed)}/{len(_DKIND_CORR)}건")
if len(_date_fixed) != len(_DATE_CORR):
    _miss = sorted(set(_DATE_CORR) - _date_fixed)
    raise SystemExit(f"[중단] 일자교정 미적용 {len(_miss)}건 — 엑셀이 갱신됐다면 data_corrections.json 'date'에서 제거할 것: {_miss}")
print(f"[일자교정] date {len(_date_fixed)}/{len(_DATE_CORR)}건")
if len(_std_fixed) != len(_STD_CORR):
    _miss_std = sorted(set(_STD_CORR) - _std_fixed)
    raise SystemExit(f"[중단] 입결기준교정 미적용 {len(_miss_std)}건 — 엑셀이 갱신됐다면 data_corrections.json 'std'에서 제거할 것: {_miss_std}")
print(f"[기준교정] std {len(_std_fixed)}/{len(_STD_CORR)}건")
if len(_comp_fixed) != len(_COMP_CORR):
    raise SystemExit(f"[중단] 경쟁률교정 미적용 {sorted(set(_COMP_CORR) - _comp_fixed)} — 엑셀 갱신 시 data_corrections.json 'comp'에서 제거할 것")
print(f"[경쟁률교정] c26 {len(_comp_fixed)}/{len(_COMP_CORR)}건")
if len(_region_fixed) != len(_REGION_CORR):
    raise SystemExit(f"[중단] 지역교정 미적용: {sorted(set(_REGION_CORR) - _region_fixed)}")
print(f"[지역교정] region {len(_region_fixed)}/{len(_REGION_CORR)}건")
print(f"[입결교정] 2026 70%컷 {len(_grade_fixed)}/{len(_GRADE_CORR)}건")
print(f"[신설] 상속된 과거 실적 제거 {len(_new_wiped)}행")
print(f"[enroll교정] 값 {len(_enroll_fixed)}/{len(_ENROLL_CORRECTIONS)} · 행제거 {len(_drop_hit)}/{len(_ROW_DROP)} · 중복제거 {len(_dedupe_hit)}/{len(_ROW_DEDUPE)} · 행추가 {len(_ADDED_ROWS)} · 전형명 {len(_renamed)}/{sum(len(v) for v in _ROW_RENAME.values())}"
      + (f" · ⚠️미적용 {_miss}" if _miss else ""))
if _miss or len(_drop_hit) != len(_ROW_DROP) or len(_dedupe_hit) < len(_ROW_DEDUPE):
    raise SystemExit(f"교정 불일치 — 엑셀 값이 바뀌었을 수 있음. 미적용 값={_miss}, 제거={_drop_hit}, 중복제거={_dedupe_hit}")

SCHEMA = ['region','sigun','uni','gye','dept','jhtype','jhname','jagyeok','enroll','prev','dkind','dn',
          'change','choejeo','hasChoejeo','chKind','c26','c25','c24','g26','g25','g24','v26','v25','v24',
          'chung26','chung25','chung24','method','note','date','gradeRatio','subjects','careerSubj',
          'cats','std26','stdK26','std25']

# (key, label, desc, color, sub, parent)
CATS = [
    ('medical','메디컬','의·치·한·수·약 전체','#e11d48',False,''),
    ('med_med','의예','의예·의학','#dc2626',True,'medical'),
    ('med_dent','치의예','치의예·치의학','#ec4899',True,'medical'),
    ('med_oriental','한의예','한의예·한의학','#9f1239',True,'medical'),
    ('med_vet','수의예','수의예·수의학','#fb923c',True,'medical'),
    ('med_pharm','약학','약학·한약학','#f43f5e',True,'medical'),
    ('nursing_health','간호·보건','간호 및 보건의료','#f5719b',False,''),
    ('engineering','공학','공학계열 전체','#2563eb',False,''),
    ('eng_cs','컴퓨터·SW·AI','컴퓨터·소프트웨어·인공지능','#3b82f6',True,'engineering'),
    ('eng_ee','전기·전자·반도체','전기·전자·통신·반도체','#1d4ed8',True,'engineering'),
    ('eng_mech','기계·자동차·항공','기계·자동차·항공·로봇','#0ea5e9',True,'engineering'),
    ('eng_chem','화공·소재·바이오','화공·신소재·에너지·바이오','#2563eb',True,'engineering'),
    ('eng_civil','건설·건축·환경','토목·건축·도시·환경','#0284c7',True,'engineering'),
    ('eng_etc','산업·기타공학','산업공학 등 그 외 공학','#60a5fa',True,'engineering'),
    ('natural','자연','자연계열 전체','#0891b2',False,''),
    ('nat_math','수학·통계','수학·통계·수리과학','#0e7490',True,'natural'),
    ('nat_phys','물리·화학','물리·화학','#0891b2',True,'natural'),
    ('nat_bio','생명·생물','생명과학·생물·바이오','#14b8a6',True,'natural'),
    ('nat_earth','지구·천문·해양','지구·천문·대기·해양','#0284c7',True,'natural'),
    ('nat_agri','농림·식품·동물','농림·식품영양·동물·수산','#22d3ee',True,'natural'),
    ('business','상경','경영·경제·상경 전체','#d97706',False,''),
    ('biz_mgmt','경영','경영·경영정보','#d97706',True,'business'),
    ('biz_econ','경제·무역·금융','경제·무역·금융·회계·세무','#ea8204',True,'business'),
    ('biz_tour','관광·호텔·외식','관광·호텔·외식경영','#f59e0b',True,'business'),
    ('biz_etc','부동산·소비자·기타','부동산·소비자·물류·보험계리','#fbbf24',True,'business'),
    ('language','어문','어학·문학 전체','#7c3aed',False,''),
    ('lang_kor','국어·한국어','국어국문·한국어·문예창작','#7c3aed',True,'language'),
    ('lang_eng','영어','영어영문·영미','#8b5cf6',True,'language'),
    ('lang_asia','중국어·일본어','중어중문·일어일문·동아시아','#a78bfa',True,'language'),
    ('lang_etc','유럽·기타외국어','불·독·노·서·아랍·베트남 등','#6d28d9',True,'language'),
    ('humanities_core','문사철(어문 제외)','사학·철학·종교 및 어문 외 문학','#9333ea',False,''),
    ('non_business_humanities','비상경','인문 전체(상경 제외)','#a855f7',False,''),
    ('social_science','사회과학','정치·행정·언론·사회','#c026d3',False,''),
    ('statistics','통계','통계·데이터','#0d9488',False,''),
    ('semiconductor','반도체','반도체학과 전체','#1d4ed8',False,''),
    ('semiconductor_contract','반도체 계약','채용조건형 반도체','#1e40af',False,''),
    ('contract_other','계약학과','그 외 계약학과','#0369a1',False,''),
    ('military','군 계약','군사·국방 계약학과','#475569',False,''),
    ('art_college','미술','미술·조형·공예 + 디자인(예체능 계열)','#db2777',False,''),
    ('music_college','음악','음악·성악·기악·작곡·국악·실용음악','#7c3aed',False,''),
    ('pe_college','체육','체육·스포츠·무용·태권도·경호','#059669',False,''),
    ('teaching','사범','사범계열','#16a34a',False,''),
    ('primary_ed','교대','교육대·초등교육','#15803d',False,''),
    ('ist','IST','KAIST·DGIST·UNIST·GIST','#db2777',False,''),
    ('free_major','자유전공','자율·무전공','#ea580c',False,''),
    ('integrated','통합모집','전 모집단위·단일계열 등 묶음 선발','#64748b',False,''),
]

payload = {
    'meta': {
        'title': '2027학년도 수시지원 대시보드',
        'subtitle': '2026 대비 변화 · 입결 영향 · 3개년 추이',
        'source': '2027학년도 수시지원의 모든 것 Final (제작: 훈장 김민철)',
        'years': {'cur': 2027, 'result': [2026, 2025, 2024]},
        'nRows': len(rows), 'nUni': len(order['uni']),
    },
    'schema': SCHEMA,
    'dicts': {k: order[k] for k in order},
    'cats': [{'key': k, 'label': l, 'desc': d, 'color': c, 'sub': sub, 'parent': par, 'count': cat_counter.get(k, 0)} for k, l, d, c, sub, par in CATS],
    'rows': rows,
}

with open(os.path.join(OUT_DIR, 'data.js'), 'w', encoding='utf-8') as f:
    f.write('window.IPSI = ')
    json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
    f.write(';')

# audit export for category review
audit_out = {}
for cat, dd in audit.items():
    items = sorted(({'uni': u, 'dept': d, 'n': n} for (u, d), n in dd.items()), key=lambda x: -x['n'])
    audit_out[cat] = {'count': cat_counter.get(cat, 0), 'distinct': len(items), 'items': items}
with open(os.path.join(OUT_DIR, 'audit_categories.json'), 'w', encoding='utf-8') as f:
    json.dump(audit_out, f, ensure_ascii=False, indent=1)

sz = os.path.getsize(os.path.join(OUT_DIR, 'data.js'))
print(f'rows={len(rows)}  uni={len(order["uni"])}  dept={len(order["dept"])}  data.js={sz/1e6:.2f}MB')
print(f'수능최저 교정 적용: {_least_fixed[0]}건 (예상 4: 세명대 3 + 계명대 1)')
print(f'전년대비 재계산 교정: {len(_prev_recomputed)}건 (2026 실측 스냅샷 대조 · 스킵 {len(_RECOMPUTE_SKIP)} · 오버라이드 {len(_E26_OVERRIDES)})')
print(f'전형 변경(개편·개명) 표기: {_changed_count[0]}건 (2026에 정규화 후에도 없는 대학|학과|전형명, 예상 약 3,000)')
for _k, _old, _new, _e26, _e27 in _prev_recomputed:
    _u, _d, _, _j, _ = _k.split('|')
    print(f'    {_u} {_d} {_j}: {_old} → {_new}  (2026={_e26}, 2027={_e27})')
print('category counts:')
for k, l, d, c, sub, par in CATS:
    print(f'  {cat_counter.get(k,0):6d}  {("  └ " if sub else "")}{k:24s} {l}')
