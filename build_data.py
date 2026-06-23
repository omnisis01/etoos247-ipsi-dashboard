# -*- coding: utf-8 -*-
"""Build compact, dictionary-encoded data.js for the 수시 dashboard from the master xlsx."""
import openpyxl, re, json, os, html

SRC = os.path.join(os.path.dirname(__file__), '..', '2027학년도 수시지원의 모든 것 V6.12.xlsx')
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
def parse_choejeo_change(change_text):
    """returns (kind, detail) where kind in 신설/폐지/완화/강화/변경/None.
    수능최저 'N합M': M↑ = 완화(easier), M↓ = 강화(harder)."""
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
    if '→' in z:
        L, R = z.split('→', 1)
        Lh = re.search(r'(\d)합(\d+)', L); Rh = re.search(r'(\d)합(\d+)', R)
        if '없음' in R and not Rh and ('합' in L or '등급' in L or Lh): return ('폐지', cseg)
        if '없음' in L and (Rh or '합' in R): return ('신설', cseg)
        if Lh and Rh:
            oc, ov = int(Lh.group(1)), int(Lh.group(2))
            nc, nv = int(Rh.group(1)), int(Rh.group(2))
            if nv > ov: return ('완화', cseg)
            if nv < ov: return ('강화', cseg)
            if nc > oc: return ('강화', cseg)
            if nc < oc: return ('완화', cseg)
            return ('변경', cseg)
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
SEMI_CONTRACT_WHITELIST = [  # famous 채용조건형 계약학과 (uni-substring, exact dept)
    ('고려대학교', '반도체공학과'), ('서강대학교', '시스템반도체공학과(외)'),
    ('성균관대학교', '반도체시스템공학과'), ('연세대학교', '시스템반도체공학과'),
    ('한양대학교', '반도체공학과(외)'), ('한국과학기술원', '반도체시스템공학과'),
    ('KAIST', '반도체시스템공학과'), ('포항공과대학교', '반도체공학과'), ('POSTECH', '반도체공학과'),
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

    # --- 문사철 (literature/history/philosophy), anti-greedy ---
    HUM = ['국어국문', '국문학', '한문학', '문예창작', '문학과', '사학과', '한국사', '국사학', '동양사', '서양사',
           '역사학', '역사문화', '미술사', '고고', '철학', '윤리학', '종교', '신학과', '신학부', '기독교', '불교',
           '선교', '목회', '인문학부', '인문콘텐츠', '문화재', '역사학과', '사학전공']
    if any(k in d for k in HUM) and not any(x in d for x in ['교육', '군사', '수사', '천문', '통신', '과학수사']):
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

    # --- free / undeclared major (무전공·광역) ---
    FREE = ['자유전공', '자율전공', '무전공', '전공자유', '전공자율', '자율학부', '자율설계', '자율융합', '자율미래',
            '계열자유', '광역', '학부대학', '열린전공', '전공개방', '첨단융합학부', '계열모집', '자유공학', '광역모집']
    if any(k in d for k in FREE):
        tags.add('free_major')

    return tags

# ---------------------------------------------------------------- impact signal
def impact(delta_kind, delta_n, ch_kind, comp):
    """comp = [c26,c25,c24]; returns (score, reasons[list of (sign,text)])."""
    reasons = []
    # 모집인원
    if delta_kind == 'up':
        reasons.append(('good', f'모집인원 {delta_n}명 증원 → 합격선 하락(유리) 가능'))
    elif delta_kind == 'down':
        reasons.append(('bad', f'모집인원 {abs(delta_n)}명 감원 → 합격선 상승(불리) 가능'))
    elif delta_kind == 'new':
        reasons.append(('new', '신설 모집단위 → 입결 미형성, 첫해 낮게 형성되는 경향(틈새 가능)'))
    elif delta_kind == 'closed':
        reasons.append(('bad', '모집 폐지'))
    elif delta_kind == 'split':
        reasons.append(('new', '모집단위 분리 → 인원·경쟁 재편, 변동성 큼'))
    elif delta_kind == 'merge':
        reasons.append(('new', '모집단위 통합 → 인원·경쟁 재편, 변동성 큼'))
    # 최저
    if ch_kind == '완화':
        reasons.append(('bad', '수능최저 완화 → 지원자·경쟁률 상승, 합격선 상승(불리) 가능'))
    elif ch_kind == '강화':
        reasons.append(('good', '수능최저 강화 → 지원자 감소, 내신 합격선 하락(유리) 가능'))
    elif ch_kind == '신설':
        reasons.append(('good', '수능최저 신설 → 지원 위축, 내신 합격선 하락(유리) 가능'))
    elif ch_kind == '폐지':
        reasons.append(('bad', '수능최저 폐지 → 지원자 증가, 합격선 상승(불리) 가능'))
    # 경쟁률 추세
    c = [x for x in comp if x is not None]
    if len(comp) == 3 and comp[0] is not None and comp[2] is not None:
        if comp[0] >= comp[2] * 1.25:
            reasons.append(('bad', f'경쟁률 상승추세 ({comp[2]:.1f}→{comp[0]:.1f})'))
        elif comp[0] <= comp[2] * 0.8:
            reasons.append(('good', f'경쟁률 하락추세 ({comp[2]:.1f}→{comp[0]:.1f})'))
    score = sum(1 for s_, _ in reasons if s_ == 'good') - sum(1 for s_, _ in reasons if s_ == 'bad')
    return score, reasons

# trend direction for 입결 grades (lower grade = harder). 3yr [26,25,24]
def trend(vals):
    v = [x for x in vals]
    if v[0] is not None and v[2] is not None:
        d = v[0] - v[2]
        if d <= -0.3: return 'up'      # grade number decreased -> 입결 상승(어려워짐)
        if d >= 0.3: return 'down'     # grade number increased -> 입결 하락(쉬워짐)
        return 'flat'
    return 'na'

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
cat_counter = {}
audit = {}
for r in raw:
    uni = s(r[2]); gye = s(r[3]); dept = s(r[4]); jhtype = s(r[5]); jhname = s(r[6]); jagyeok = s(r[7])
    enroll = num(r[8]); prev = s(r[9]); change = s(r[10]); choejeo = s(r[11])
    comp = [num(r[18]), num(r[19]), num(r[20])]
    grade = [vgrade(num(r[22])), vgrade(num(r[27])), vgrade(num(r[31]))]
    conv = [num(r[23]), num(r[28]), num(r[32])]
    chung = [s(r[24]), s(r[29]), s(r[33])]
    method = s(r[12]); note = s(r[25]); date = s(r[34])
    gr = s(r[15]); subj = s(r[16]); career = s(r[17])

    delta_kind, delta_n = parse_delta(prev)
    ch_kind, ch_detail = parse_choejeo_change(change)
    has_choejeo = 0 if (norm(choejeo) in ('', '없음', '미적용', 'X', '-')) else 1
    score, reasons = impact(delta_kind, delta_n, ch_kind, comp)
    gtrend = trend(grade)
    ctrend = ('up' if (comp[0] and comp[2] and comp[0] > comp[2]*1.1) else 'down' if (comp[0] and comp[2] and comp[0] < comp[2]*0.9) else 'flat' if (comp[0] and comp[2]) else 'na')

    tags = sorted(categorize(uni, gye, dept, jhname, jagyeok))
    for t in tags:
        cat_counter[t] = cat_counter.get(t, 0) + 1
        audit.setdefault(t, {}).setdefault((uni, dept), 0)
        audit[t][(uni, dept)] += 1

    rows.append([
        intern('region', r[0]), intern('sigun', r[1]), intern('uni', uni), gye[:2],
        intern('dept', dept), jhtype, intern('jhname', jhname), intern('jagyeok', jagyeok),
        enroll, prev, delta_kind, delta_n,
        intern('change', change), intern('choejeo', choejeo), has_choejeo, ch_kind or '',
        comp[0], comp[1], comp[2],
        grade[0], grade[1], grade[2],
        conv[0], conv[1], conv[2],
        chung[0][:12], chung[1][:12], chung[2][:12],
        intern('method', method), intern('note', note), intern('date', date),
        intern('gradeRatio', gr), intern('subjects', subj), intern('careerSubj', career),
        tags, score, [rs for rs in reasons], gtrend, ctrend,
    ])

SCHEMA = ['region','sigun','uni','gye','dept','jhtype','jhname','jagyeok','enroll','prev','dkind','dn',
          'change','choejeo','hasChoejeo','chKind','c26','c25','c24','g26','g25','g24','v26','v25','v24',
          'chung26','chung25','chung24','method','note','date','gradeRatio','subjects','careerSubj',
          'cats','score','reasons','gtrend','ctrend']

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
    ('humanities_core','문사철','문학·사학·철학','#9333ea',False,''),
    ('non_business_humanities','비상경','인문 전체(상경 제외)','#a855f7',False,''),
    ('social_science','사회과학','정치·행정·언론·사회','#c026d3',False,''),
    ('statistics','통계','통계·데이터','#0d9488',False,''),
    ('semiconductor','반도체','반도체학과 전체','#1d4ed8',False,''),
    ('semiconductor_contract','반도체 계약','채용조건형 반도체','#1e40af',False,''),
    ('contract_other','계약학과','그 외 계약학과','#0369a1',False,''),
    ('military','군 계약','군사·국방 계약학과','#475569',False,''),
    ('teaching','사범','사범계열','#16a34a',False,''),
    ('primary_ed','교대','교육대·초등교육','#15803d',False,''),
    ('ist','IST','KAIST·DGIST·UNIST·GIST','#db2777',False,''),
    ('free_major','자유전공','자율·무전공','#ea580c',False,''),
]

payload = {
    'meta': {
        'title': '2027학년도 수시지원 대시보드',
        'subtitle': '2026 대비 변화 · 입결 영향 · 3개년 추이',
        'source': '2027학년도 수시지원의 모든 것 V6.12 (제작: 훈장 김민철)',
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
print('category counts:')
for k, l, d, c, sub, par in CATS:
    print(f'  {cat_counter.get(k,0):6d}  {("  └ " if sub else "")}{k:24s} {l}')
