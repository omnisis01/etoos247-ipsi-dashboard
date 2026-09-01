# 대학별 수시 원서접수 기간을 진학어플라이 공통 원서검색에서 수집해 apply_dates.js를 만든다.
# 왜: 대학마다 접수 마감이 다르다(SKY는 9/9, 마감 시각도 17~23시 제각각). 공통 기간(9/7~9/11)만
#     안내하면 SKY 지망생이 이틀 늦게 내러 갔다가 접수 자체를 못 하는 사고가 난다.
# 출처: apply.jinhakapply.com 공통 원서검색 — 진학(coop=1)·유웨이(coop=2) 대행 대학을 한 소스로 집계.
# 사용: python3 fetch_apply_dates.py   (접수 주간 전 재실행 — 세부 일정이 확정되며 갱신된다)
import json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = 'https://apply.jinhakapply.com/Common/SiteSearch'
API = 'https://apply.jinhakapply.com/WebCommon/Ajax/GetUnivList.aspx/ServiceList'
UA = 'Mozilla/5.0'

# 진학어플라이 표기 → 대시보드 표기. 정규화로 못 잡는 것만 등재한다.
ALIAS = {
    '건국대학교(서울)': '건국대학교',
    '연세대학교(서울)': '연세대학교',
    '고려대학교(서울)': '고려대학교',
    '동국대학교(서울)': '동국대학교',
    '한양대학교(서울)': '한양대학교',
    '경상국립대학교': '경상대학교',
    '한경국립대학교': '한경대학교',
    '국립목포대학교': '목포대학교',
    '국립부경대학교': '부경대학교',
    '국립공주대학교': '공주대학교',
    '국립순천대학교': '순천대학교',
    '국립창원대학교': '창원대학교',
    '국립강릉원주대학교': '강릉원주대학교',
    '국립군산대학교': '군산대학교',
    '국립금오공과대학교': '금오공과대학교',
    '국립한국교통대학교': '한국교통대학교',
    '국립한국해양대학교': '한국해양대학교',
    '국립한밭대학교': '한밭대학교',
    '국립목포해양대학교': '목포해양대학교',
    '국립경국대학교': '경국대학교',
    '포항공과대학교': 'POSTECH',
}

# 한 원서 창구가 여러 캠퍼스를 함께 받는 대학 — 진학 단일 항목을 대시보드 캠퍼스 행 전체에 편다.
# (원서 시스템이 하나라 접수 기간이 같다. 고려대(세종)처럼 창구가 분리된 곳은 진학 목록에 따로 있다.)
CAMPUS_EXPAND = {
    '강원대학교': ['강원대학교(춘천)', '강원대학교(강릉)', '강원대학교(원주)', '강원대학교(삼척)', '강원대학교(도계)'],
    '단국대학교': ['단국대학교', '단국대학교(천안)'],
    '상명대학교': ['상명대학교', '상명대학교(천안)'],
    '홍익대학교': ['홍익대학교', '홍익대학교(세종)'],
}


def norm(s):
    return re.sub(r'[\s()·]', '', s or '')


def fetch():
    req = urllib.request.Request(PAGE, headers={'User-Agent': UA})
    html = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
    m = re.search(r"__APPLY_TOKEN\s*=\s*['\"]([^'\"]+)", html)
    if not m:
        raise SystemExit('FAIL: __APPLY_TOKEN을 페이지에서 찾지 못함 — 사이트 구조 변경 여부 확인')
    req = urllib.request.Request(API, data=b'{}', headers={
        'User-Agent': UA, 'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest', 'X-PM-TOKEN': m.group(1),
        'Origin': 'https://apply.jinhakapply.com', 'Referer': PAGE})
    d = json.loads(json.loads(urllib.request.urlopen(req, timeout=60).read().decode())['d'])
    arr = d.get('Univdata', d) if isinstance(d, dict) else d
    return [x for x in arr if x.get('CategoryName') == '수시']


# 진학·유웨이 어느 쪽으로도 접수하지 않는 대학(과기원 등 자체 접수) — 수집으로 안 잡히므로
# 여기서 보충한다.
#
# ⚠️ 출처 서열을 지킬 것 — 대학 공식(요강·입학처 공지) > 접수처 표기 > 제3자 정리본.
#    이 사전은 원래 파노라마(제3자 정리본) 기준으로 채워졌고, 그 탓에 KAIST 10:00·UNIST 19:00
#    두 건이 틀린 채로 서비스됐다. 2026-09-01 대학 공식 자료로 전수 재검증해 값과 근거를 아래처럼 고쳤다.
# ⚠️ MANUAL 은 스크랩에 안 잡힌 대학만 보충한다(아래 `u not in out`). 스크랩에 잡히는 대학의
#    MANUAL 값은 쓰이지 않으므로, 그런 항목은 스크랩 결과와 값을 맞춰 두어야 한다.
#    (안 맞춰 두면 어느 해 스크랩에서 한 번 빠질 때 조용히 옛 값으로 되돌아간다.)
MANUAL = {
    # 입학처 공지 '2027학년도 학사과정 수시모집 원서접수 안내' — "2026.9.1.(화) 09:00 ~ 9.9.(수) 18:00".
    # 유웨이 KAIST 2027 수시 페이지 파라미터도 STARTDATE=20260901090000 으로 일치.
    # (요강 PDF 전형개요는 시작 시각 미표기라 공지와 모순되지 않는다.)
    # https://admission.kaist.ac.kr/undergraduate/notice/sub03#2269
    'KAIST':    {'from': '2026-09-01T09:00', 'to': '2026-09-09T18:00', 'via': '대학 자체'},
    # 공식 모집요강 p.49 — "2026. 9. 3.(목) 9:00 ~ 9. 10.(목) 18:00까지".
    # https://www.dgist.ac.kr/thumbnail/mtcltnData/MD_20260429133944989Qt90.pdf
    'DGIST':    {'from': '2026-09-03T09:00', 'to': '2026-09-10T18:00', 'via': '대학 자체'},
    # 공식 모집요강 Ⅷ장 — "수시모집: 2026.9.3.(목) 09:00~9.10.(목) 18:00까지(8일간)".
    # 전형일정 총괄표 등 7곳 이상에서 09:00 이고 문서 전체에 '19:00' 은 0회다.
    # (9.11.(금) 18:00 은 자기소개서·첨부서류 업로드 마감이지 원서접수 마감이 아니다.)
    # https://adm-u.unist.ac.kr/admission/guide/admissions-process.do?mode=download&articleNo=105830&attachNo=575153
    'UNIST':    {'from': '2026-09-03T09:00', 'to': '2026-09-10T18:00', 'via': '대학 자체'},
    # 공식 모집요강 p.32 전형일정 — "2026. 9. 7.(월) ~ 9. 11.(금) 18:00 까지".
    # ⚠️ 마감만 확인됐다. 시작 09:00 은 요강 미표기이며 공식 근거가 없는 미확인값이다.
    # https://www.gist.ac.kr/download/?file_id=sqfortm6tm7o0mkxkgtqpnurromtdu
    'GIST':     {'from': '2026-09-07T09:00', 'to': '2026-09-11T18:00', 'via': '대학 자체'},
    # 공식 모집요강 Ⅳ장 — "수시모집 2026. 09. 07.(월) 10:00 - 09. 11.(금) 18:00".
    # (요강은 접수처를 '유웨이어플라이 일반접수'로 적지만 스크랩에는 안 잡혀 여기서 보충한다.)
    # https://admission.kentech.ac.kr/detail.do?board_seq=7653
    'KENTECH':  {'from': '2026-09-07T10:00', 'to': '2026-09-11T18:00', 'via': '대학 자체'},
    # 아래 2교는 스크랩에 잡히므로 이 값이 실제로 쓰이지는 않는다. 스크랩이 한 번 놓칠 때를
    # 대비한 보험이므로 출력값과 반드시 같게 유지할 것.
    # 공주교대: 요강 p.1 — "2026. 9. 8.(화) 10:00 ∼ 9. 11.(금) 16:00", 접수처 유웨이어플라이.
    # https://www.gjue.ac.kr/ipsi/72/pdfViewer/CAT183
    '공주교육대학교': {'from': '2026-09-08T10:00', 'to': '2026-09-11T16:00', 'via': '유웨이어플라이'},
    # 계명대: 요강 p.14 — "2026. 9. 7.(월) ~ 9. 11.(금) 18:00까지". 시작 시각은 요강 미표기라
    # 접수처(유웨이어플라이) 표기 09:00 을 따른다. 종전 10:00 은 근거 없는 값이었다.
    # https://www.gokmu.ac.kr/guide/paper.htm?ctg_cd=susi
    '계명대학교': {'from': '2026-09-07T09:00', 'to': '2026-09-11T18:00', 'via': '유웨이어플라이'},
}


def main():
    susi = fetch()
    if len(susi) < 200:
        raise SystemExit(f'FAIL: 수시 항목이 {len(susi)}건뿐 — 수집 실패로 보고 기존 파일을 보존한다')

    dash = json.loads(open(os.path.join(HERE, 'data.js'), encoding='utf-8')
                      .read()[len('window.IPSI = '):-1])
    dash_unis = dash['dicts']['uni']
    by_norm = {norm(u): u for u in dash_unis}

    out, unmatched = {}, []
    for x in sorted(susi, key=lambda v: v.get('ShortName', '')):
        name = (x.get('ShortName') or '').strip()
        rec = {'from': x['WriteFromTime'][:16], 'to': x['WriteToTime'][:16],
               'via': '진학어플라이' if x.get('Cooperator') == 1 else '유웨이어플라이'}
        if name in CAMPUS_EXPAND:
            targets = [t for t in CAMPUS_EXPAND[name] if t in dash_unis]
        else:
            t1 = ALIAS.get(name) or by_norm.get(norm(name)) or by_norm.get(norm(re.sub(r'\(.*?\)', '', name)))
            targets = [t1] if t1 else []
        if not targets:
            unmatched.append(name); continue
        target = None
        # 같은 대시보드 대학에 항목이 둘이면 더 이른 마감을 쓴다 —
        # 학생이 마감을 놓치는 쪽의 비용이 훨씬 크다.
        for target in targets:
            if target in out and out[target]['to'] <= rec['to']:
                continue
            out[target] = rec

    # 자체 접수 대학 보충 — 수집에 이미 잡혔다면(대행 전환) 수집값을 우선한다.
    manual_used = [u for u, rec in MANUAL.items() if u in dash_unis and u not in out]
    for u in manual_used:
        out[u] = MANUAL[u]

    covered = len(out); total = len(dash_unis)
    miss_dash = sorted(set(dash_unis) - set(out))
    body = ('/* 대학별 수시 원서접수 기간 — 진학어플라이 공통 원서검색 집계(진학+유웨이).\n'
            '   생성: fetch_apply_dates.py — 접수 주간 전 재실행할 것. 수기 편집 금지. */\n'
            'window.IPSI_APPLY = ')
    with open(os.path.join(HERE, 'apply_dates.js'), 'w', encoding='utf-8') as f:
        f.write(body + json.dumps(out, ensure_ascii=False, indent=1) + ';\n')
    print(f'[원서접수] 수집 {len(susi)}건 → 대시보드 {covered}/{total}교 매핑'
          + (f' (자체 접수 보충 {len(manual_used)}교: ' + ', '.join(manual_used) + ')' if manual_used else ''))
    if unmatched:
        print(f'  진학측 미매핑 {len(unmatched)}건(대시보드에 없는 대학이면 정상): '
              + ', '.join(unmatched[:12]) + ('…' if len(unmatched) > 12 else ''))
    if miss_dash:
        print(f'  대시보드측 미커버 {len(miss_dash)}교: ' + ', '.join(miss_dash[:12])
              + ('…' if len(miss_dash) > 12 else ''))


# import 만 해도 apply_dates.js 가 통째로 재생성되던 것을 막는다.
# (다른 스크립트가 fetch() 만 가져다 쓰려다 실제로 재생성을 일으킨 적이 있다 — 2026-09-01.)
if __name__ == '__main__':
    main()
