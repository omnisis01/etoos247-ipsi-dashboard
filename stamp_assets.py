# index.html이 참조하는 정적 파일에 내용 해시(?v=)를 붙여 브라우저 캐시를 무효화하는 스크립트
# 왜 필요한가: index.html이 styles.css·app.js를 버전 없이 참조하면, 배포해도 브라우저가
# 옛 파일을 계속 쓴다. 실제로 QA 중 서버는 새 파일을 주는데 화면은 옛 CSS로 렌더됐다.
# 사용법: python3 stamp_assets.py   (배포 전 반드시 1회 — DATA_UPDATE.md 런북에 포함)
import hashlib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = ['styles.css', 'data.js', 'insights.js', 'apply_dates.js', 'app.js']


def h8(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        raise SystemExit(f'FAIL: {name} 없음')
    return hashlib.sha1(open(p, 'rb').read()).hexdigest()[:8]


def main():
    idx = os.path.join(HERE, 'index.html')
    t = open(idx, encoding='utf-8').read()
    orig, changed = t, []
    for a in ASSETS:
        v = h8(a)
        # href="styles.css" 또는 href="styles.css?v=xxxx" 를 모두 잡는다
        pat = re.compile(r'((?:href|src)=")' + re.escape(a) + r'(?:\?v=[0-9a-f]+)?(")')
        new, n = pat.subn(lambda m: f'{m.group(1)}{a}?v={v}{m.group(2)}', t)
        if n == 0:
            raise SystemExit(f'FAIL: index.html 에서 {a} 참조를 찾지 못함')
        if new != t:
            changed.append(f'{a}?v={v}')
        t = new
    if t != orig:
        open(idx, 'w', encoding='utf-8').write(t)
        print('[캐시버스팅] 갱신 ' + ' · '.join(changed))
    else:
        print('[캐시버스팅] 변경 없음 (해시 동일)')


main()
