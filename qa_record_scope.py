# -*- coding: utf-8 -*-
# 졸업생 학생부 반영범위(record_scope.js) 점검 — 대학명 정합성·근거 필수·확인일자 신선도.
#
# 왜 필요한가: 이 파일은 **요강을 손으로 읽어 옮긴 값**이라 자동 검증 대상이 없다. 그래서 최소한
#   ① 대학명이 data.js 와 어긋나면(개명·표기 변경) 화면에 안 뜨는 것을 잡고,
#   ② 근거 URL·원문 인용이 빠진 항목을 막고,
#   ③ 요강이 갱신되는 시기에 값이 낡았음을 알린다.
# ⚠️ 값 자체의 진위는 검증할 수 없다 — 근거 URL 을 남기는 이유가 그것이다.
#    의심되면 source 를 열어 원문을 다시 본다. 추측으로 채우지 마라(빈칸이 낫다).
import json, os, re, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'record_scope.js')
STALE_DAYS = 120          # 요강은 학년도 단위라 링크보다 길게 잡는다


def main():
    if not os.path.exists(SRC):
        print(f'SKIP  아직 없음: {os.path.basename(SRC)}'); return 0
    raw = open(SRC, encoding='utf-8').read()
    i = raw.index('{')
    data = json.loads(raw[i:raw.rindex('}') + 1])
    d = json.loads(open(os.path.join(HERE, 'data.js'), encoding='utf-8').read()[len('window.IPSI = '):-1])
    ui = d['schema'].index('uni')
    dict_uni = d['dicts']['uni']
    live = {dict_uni[r[ui]] if isinstance(r[ui], int) else r[ui] for r in d['rows']}

    unis = data.get('universities', {})
    checked = data.get('checkedOn', '')
    fails, confirmed, unknown = [], 0, 0
    print(f'수록 {len(unis)}교 · 확인일 {checked or "(없음)"}')

    bad = [u for u in unis if u not in live]
    if bad:
        fails.append(f'data.js 에 없는 대학명 {len(bad)}건')
        for u in bad:
            print(f'  ✗ {u} — data.js 에 없다. 화면에 절대 표시되지 않는다.')
    else:
        print(f'  ✓ 대학명 {len(unis)}개 전부 data.js 와 일치')

    for u, e in unis.items():
        if not e.get('graduate'):
            unknown += 1; continue
        confirmed += 1
        if not e.get('source'):
            fails.append(f'{u}: 근거 URL 없음')
            print(f'  ✗ {u} — 값은 있는데 source 가 없다. 근거 없는 값은 넣지 마라.')
        if not e.get('quote'):
            print(f'  ⚠ {u} — 원문 인용(quote)이 없다. 나중에 재확인이 어려워진다.')
    print(f'  · 확인됨 {confirmed}교 · 미확인 {unknown}교')

    if checked:
        age = (datetime.date.today() - datetime.date.fromisoformat(checked)).days
        print(f'  {"✓" if age <= STALE_DAYS else "✗"} 확인일 {checked} ({age}일 전)')
        if age > STALE_DAYS:
            fails.append(f'확인일이 {age}일 지났다 — 요강 재확인 후 checkedOn 갱신')
    else:
        fails.append('checkedOn 이 없다')

    print('\n' + ('FAIL  ' + ' · '.join(fails) if fails else 'OK  반영범위 자료 이상 없음'))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
