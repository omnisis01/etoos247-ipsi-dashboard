# 인사이트 모집인원을 마스터 엑셀 기준으로 정정하는 1회성 패치 스크립트.
# 유래(두 종류의 오류):
#  (A) 지역의사 계열: 권역별로 쪼개진 행 하나를 전형 총원으로 오기 → 합계로 정정. 수시 기준임을 note에 명시.
#  (B) 넥스트플레이 스냅샷 드리프트: 5월 기사의 2027 인원이 V6.29(6/29 수정본)와 다름 → 엑셀 2027합/증감으로 정정.
# 사용법: python3 fix_ins_numbers.py [--dry]
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_ins import load_insights, write_insights
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '입결 및 인사이트', 'TongTongTong_2027학년도 수시지원의 모든 것 V6.29_부산 약학 최저  등수정.xlsx')

# (대학, 인사이트 라벨, 엑셀 전형명, 계열('의예'|None), 전형유형|None, note 접미)
FIX = [
    ('전북대학교', '의예 지역의사선발(교과)', '지역의사선발전형', '의예', '학생부교과', '신설 · 6개 권역 합(수시 기준) · 최저 3합6'),
    ('경북대학교', '의예 지역의사선발(종합)', '지역의사선발전형', '의예', '학생부종합', '신설 · 7개 권역 합(수시 기준) · 최저 수+국,영,탐(2) 3합5'),
    ('제주대학교', '의예 지역의사제(교과)', '지역의사제전형', '의예', '학생부교과', '신설 · 3개 권역 합(수시 기준, 정시 8명 별도) · 최저 수(기미)+국,영,과(2) 3합6'),
    ('원광대학교', '의예 지역의사선발 종합', '지역의사선발전형', '의예', '학생부종합', '신설 · 6개 권역 합(수시 기준) · 최저 3합6'),
    ('단국대학교(천안)', '의예 지역의료인재 종합', '지역의료인재전형', '의예', '학생부종합', '신설 · 6개 권역 합(수시 기준) · 최저 3합5'),
    ('동국대학교(WISE)', '의예 지역의사제 종합', '지역의사제전형', '의예', '학생부종합', '신설 · 5개 권역 합(수시 기준)'),
    ('명지대학교', '학교장추천(교과)', '학교장추천전형', None, '학생부교과', None),
    ('명지대학교', '교과면접', '교과면접전형', None, '학생부교과', None),
    ('명지대학교', '명지인재 면접형(종합)', '명지인재면접전형', None, '학생부종합', None),
    ('명지대학교', '명지인재 서류형(종합)', '명지인재서류전형', None, '학생부종합', None),
    ('인하대학교', '지역균형(교과)', '지역균형전형', None, '학생부교과', None),
    ('중앙대학교', '지역균형선발(교과)', '지역균형전형', None, '학생부교과', None),
    ('숭실대학교', 'SW우수자', 'SW우수자전형', None, None, None),
    ('한양대학교', '학생부종합 추천형', '추천형전형', None, '학생부종합', None),
    ('국민대학교', '교과우수자(학교장추천)', '교과우수자(학교장추천)전형', None, '학생부교과', None),
    ('국민대학교', '국민프런티어(종합)', '국민프런티어전형', None, '학생부종합', None),
    ('국민대학교', '논술(약술형)', '논술전형', None, '논술', None),
]

def s(v): return '' if v is None else str(v).strip()
def num(v):
    try: return int(float(str(v)))
    except: return 0
def is_uiye(d): return bool(re.fullmatch(r'(의예과|의학과|의학과\(의예과\))(\(.+\))?', d))

def main():
    dry = '--dry' in sys.argv
    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
    rows = [{'uni': s(r[2]), 'dept': s(r[4]), 'jht': s(r[5]), 'jhn': s(r[6]), 'e': num(r[8]), 'prev': s(r[9])}
            for r in wb['전체'].iter_rows(min_row=4, values_only=True)]
    ins = load_insights()
    done = 0
    for uni, label, jhn, gye, jht, note_suffix in FIX:
        sel = [x for x in rows if x['uni'] == uni and x['jhn'] == jhn]
        if gye == '의예': sel = [x for x in sel if is_uiye(x['dept'])]
        if jht: sel = [x for x in sel if x['jht'] == jht]
        if not sel: print(f'  ! 엑셀 매칭 실패: {uni} {label}'); continue
        e2027 = sum(x['e'] for x in sel)
        delta = 0
        for x in sel:
            m = re.match(r'^([▲▼])(\d+)$', x['prev'])
            if m: delta += int(m.group(2)) * (1 if m.group(1) == '▲' else -1)
            elif x['prev'] == '신설': delta += x['e']
        e2026 = e2027 - delta
        tgt = None
        for sec in ins['unis'][uni].get('sections', []):
            for row in sec.get('rows', []) or []:
                if row.get('label') == label: tgt = row
        if tgt is None: print(f'  ! 인사이트 행 없음: {uni} {label}'); continue
        old = f"{tgt.get('from')}→{tgt.get('to')} [{tgt.get('note')}]"
        tgt['from'] = '없음' if e2026 == 0 else f'{e2026:,}명'
        tgt['to'] = f'{e2027:,}명'
        tgt['dir'] = 'up' if delta > 0 else ('down' if delta < 0 else 'same')
        tgt['note'] = note_suffix if note_suffix else (f'▲{delta}' if delta > 0 else (f'▼{-delta}' if delta < 0 else '동일(-)'))
        print(f'  {uni} | {label}\n      {old}  →  {tgt["from"]}→{tgt["to"]} [{tgt["note"]}]')
        done += 1
    if dry: print(f'\n(dry-run) {done}건 대상'); return
    write_insights(ins)
    print(f'\nOK  {done}건 정정 완료')

if __name__ == '__main__':
    main()
