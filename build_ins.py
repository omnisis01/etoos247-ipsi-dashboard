# 에이전트가 생성한 인사이트 JSON을 insights.js에 주입하는 스크립트 (order 확장 + unis 추가)
# 사용법: python3 build_ins.py <새_대학들.json>
import json, re, sys, os

INS = os.path.join(os.path.dirname(__file__), 'insights.js')

def main():
    src = sys.argv[1]
    new_unis = json.load(open(src, encoding='utf-8'))
    txt = open(INS, encoding='utf-8').read()

    # order 배열 파싱
    m = re.search(r'order:\s*(\[[^\]]*\])', txt)
    order = json.loads(m.group(1))
    added = [u for u in new_unis if u not in order]
    skipped = [u for u in new_unis if u in order]
    if skipped:
        print(f'SKIP(이미 존재): {skipped}')
    if not added:
        print('추가할 대학 없음'); return
    new_order = order + added
    txt = txt[:m.start(1)] + json.dumps(new_order, ensure_ascii=False) + txt[m.end(1):]

    # unis 닫는 '  },\n};' 직전에 한 줄 JSON으로 삽입
    tail = re.search(r'\n(  \},\n\};)\s*$', txt)
    if not tail:
        print('ERROR: insights.js 꼬리 구조(  },\\n};)를 찾지 못함'); sys.exit(1)
    lines = ''.join(
        f'    {json.dumps(u, ensure_ascii=False)}: {json.dumps(new_unis[u], ensure_ascii=False)},\n'
        for u in added)
    txt = txt[:tail.start(1)] + lines + txt[tail.start(1):]

    open(INS, 'w', encoding='utf-8').write(txt)
    print(f'OK  추가 {len(added)}교: {added}  (order {len(order)} → {len(new_order)})')

if __name__ == '__main__':
    main()
