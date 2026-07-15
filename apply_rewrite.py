# 시사점(verdict/oneLine) 재작성분을 insights.js에 적용하는 1회성 스크립트.
# 유래: 기존 시사점이 원본 전략 PDF의 「시사점」열을 동의어로 옮긴 수준이라,
#       PDF에 없는 우리 데이터(3개년 입결·경쟁률·추합)로 근거·관점을 다시 세운 문구로 교체한다.
# 사용법: python3 apply_rewrite.py <new7.json> <enrich8.json> [--dry]
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_ins import load_insights, write_insights

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry' in sys.argv
    new7 = json.load(open(args[0], encoding='utf-8'))
    enr8 = json.load(open(args[1], encoding='utf-8'))
    ins = load_insights()
    n_one = n_v = n_sec = 0

    # 신규 7교: oneLine + verdict 전체 교체
    for uni, p in new7.items():
        d = ins['unis'].get(uni)
        if not d: print(f'  ! 없음: {uni}'); continue
        if p.get('oneLine'): d['oneLine'] = p['oneLine']; n_one += 1
        if p.get('verdict'): d['verdict'] = p['verdict']; n_v += 1

    # 보강 8교: 메디컬 추가분 verdict만 교체(정확 문자열 매칭) + 메디컬 섹션 caption/bullets 교체
    for uni, p in enr8.items():
        d = ins['unis'].get(uni)
        if not d: print(f'  ! 없음: {uni}'); continue
        olds = p.get('med_verdict_old') or []
        miss = [o for o in olds if o not in [v.get('text') for v in d.get('verdict', [])]]
        if miss:
            print(f'  ! [{uni}] med_verdict_old 원문 불일치 {len(miss)}건 — 건너뜀')
            for m in miss[:2]: print(f'      {m[:60]}')
            continue
        d['verdict'] = [v for v in d['verdict'] if v.get('text') not in olds] + (p.get('med_verdict_new') or [])
        n_v += 1
        for sec in d.get('sections', []):
            t = sec.get('title', '')
            if t.startswith('메디컬(') and t.endswith(') 변화'):
                if p.get('med_caption'): sec['caption'] = p['med_caption']
                if p.get('med_bullets'): sec['bullets'] = p['med_bullets']
                n_sec += 1
    if dry:
        print(f'(dry) oneLine {n_one} · verdict {n_v} · 메디컬섹션 {n_sec}'); return
    write_insights(ins)
    print(f'OK  oneLine {n_one}교 · verdict {n_v}교 · 메디컬 섹션 {n_sec}교 갱신')

if __name__ == '__main__':
    main()
