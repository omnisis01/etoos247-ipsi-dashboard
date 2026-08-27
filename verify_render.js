// 최소 DOM 스텁으로 app.js를 실제 실행해, 화면에 출력된 HTML을 수집·검증하는 하네스
// 사용법: node verify_render.js [--dump <파일>]
//
// 왜 이게 필요한가 — verify_frontend.py(정적 분석)는 렌더 코드를 통째로 지워도 통과시킨다.
// 변이 테스트에서 미탐 7/10건이 나왔다(bullets·DOM 앵커 삭제조차 못 잡음). 텍스트 매칭은
// 조건 게이트(`if (false)`)·동명 필드(cats.label vs row.label)·다중 참조를 구분하지 못한다.
// 그래서 app.js를 진짜로 돌려 "무엇이 화면에 나갔는가"를 본다. 실행 결과는 반박할 수 없다.
//
// 한계: 스텁이라 레이아웃·CSS·실제 픽셀은 검증하지 않는다. '값이 DOM 문자열에 들어갔는가'까지다.

const fs = require('fs');
const path = require('path');
const HERE = __dirname;

/* ---------------------------------------------------------------- DOM 스텁 */
const RENDERED = [];          // 화면에 나간 HTML 조각 전량
const HANDLERS = new Map();   // 요소별 이벤트 핸들러 — 액션 시뮬레이션에 쓴다
const PROBES = [];            // querySelectorAll 로 만들어진 더미 — 여기 걸린 핸들러로 상세 화면을 연다

class ClassList {
  constructor(el) { this.el = el; this._s = new Set(); }
  add(...c) { c.forEach(x => x && this._s.add(x)); }
  remove(...c) { c.forEach(x => this._s.delete(x)); }
  toggle(c, f) { if (f === undefined) f = !this._s.has(c); f ? this._s.add(c) : this._s.delete(c); return f; }
  contains(c) { return this._s.has(c); }
  get value() { return [...this._s].join(' '); }
}

// 조회로 만들어진 더미 요소의 dataset — app.js가 읽는 키에 그럴듯한 값을 돌려준다.
// 이게 있어야 tr.dataset.i 같은 걸 읽는 클릭 핸들러가 정상 동작해 모달을 열 수 있다.
function fakeDataset() {
  return new Proxy({}, {
    get(t, k) {
      if (k in t) return t[k];
      if (typeof k !== 'string') return undefined;
      // ⚠️ 항상 0번 행으로 모달을 열면, 그 행이 비워둔 필드는 전부 '미도달'로 오판된다
      //    (실측: date·gradeRatio·v26·chung26). 검사할 필드가 채워진 행을 지정받는다.
      if (['i', 'open', 'rm', 'add', 'fav', 'idx'].includes(k)) return globalThis.__PROBE_ROW || '0';
      if (k === 'uni') return (globalThis.window.IPSI_INSIGHTS
        && globalThis.window.IPSI_INSIGHTS.order[0]) || '';
      return '';
    },
    set(t, k, v) { t[k] = v; return true; },
  });
}

class El {
  constructor(tag = 'div') {
    this.tagName = (tag || 'div').toUpperCase();
    this.children = []; this.parentNode = null;
    this.attrs = {}; this.dataset = {}; this.style = {};
    this.classList = new ClassList(this);
    this._html = ''; this._text = '';
    this.id = '';
  }
  set innerHTML(v) {
    this._html = String(v == null ? '' : v);
    if (this._html.trim()) RENDERED.push({ id: this.id, kind: 'innerHTML', html: this._html });
  }
  get innerHTML() { return this._html; }
  set textContent(v) {
    this._text = String(v == null ? '' : v);
    if (this._text.trim()) RENDERED.push({ id: this.id, kind: 'textContent', html: this._text });
  }
  get textContent() { return this._text || stripTags(this._html); }
  set className(v) { this.classList._s = new Set(String(v || '').split(/\s+/).filter(Boolean)); }
  get className() { return this.classList.value; }
  setAttribute(k, v) {
    this.attrs[k] = String(v);
    if (k === 'id') this.id = String(v);
    // title 속성도 사용자에게 보이는 정보다 — 수집한다
    if (k === 'title' && String(v).trim()) RENDERED.push({ id: this.id, kind: 'attr:title', html: String(v) });
  }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  hasAttribute(k) { return k in this.attrs; }
  get parentElement() { return this.parentNode || new El('div'); }
  get firstChild() { return this.children[0] || null; }
  get nextSibling() { return null; }
  appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
  insertBefore(c) { return this.appendChild(c); }
  removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); return c; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  insertAdjacentHTML(_pos, html) { if (String(html).trim()) RENDERED.push({ id: this.id, kind: 'insertAdjacent', html: String(html) }); }
  cloneNode() { return new El(this.tagName); }
  // 조회 결과에 app.js가 클릭 핸들러를 건다. 빈 배열을 주면 그 핸들러가 영영 안 걸려
  // 모달·상세 화면을 열 수 없고, 거기서만 보이는 필드가 전부 '미도달'로 오판된다.
  // 그래서 더미를 돌려주고, 걸린 핸들러를 PROBES 에 모아 나중에 호출한다.
  querySelector() { const e = new El('div'); e.dataset = fakeDataset(); return e; }
  querySelectorAll(sel) {
    const e = new El('div');
    e.dataset = fakeDataset();
    e._sel = sel;
    PROBES.push(e);
    return [e];
  }
  closest() { return null; }
  matches() { return false; }
  focus() {} blur() {} scrollIntoView() { }
  getBoundingClientRect() { return { top: 0, left: 0, width: 800, height: 600, bottom: 600, right: 800 }; }
  addEventListener(t, fn) { HANDLERS.set(`${this.id}:${t}`, fn); }
  removeEventListener() {}
  set onclick(fn) { this._onclick = fn; if (this.id) HANDLERS.set(`${this.id}:click`, fn); }
  get onclick() { return this._onclick; }
  set onkeydown(fn) { this._onkeydown = fn; }
  get onkeydown() { return this._onkeydown; }
  set oninput(fn) { this._oninput = fn; }
  get oninput() { return this._oninput; }
  set onchange(fn) { this._onchange = fn; }
  get onchange() { return this._onchange; }
}

function stripTags(h) { return String(h).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim(); }

// index.html에 정의된 id를 모두 미리 만들어 둔다 — app.js의 $('#x')가 null을 만나면 죽는다
const HTML = fs.readFileSync(path.join(HERE, 'index.html'), 'utf8');
const HTML_IDS = [...HTML.matchAll(/id="([^"]+)"/g)].map(m => m[1]);
const REGISTRY = new Map();
const REQUESTED = new Set();   // app.js가 실제로 찾은 id — 앵커 추적용
function ensure(id) {
  if (!REGISTRY.has(id)) { const e = new El('div'); e.id = id; REGISTRY.set(id, e); }
  return REGISTRY.get(id);
}
HTML_IDS.forEach(ensure);

const documentStub = {
  body: new El('body'),
  documentElement: new El('html'),
  activeElement: null,
  createElement: t => new El(t),
  // id는 요청되는 대로 만들어 준다(동적 생성 요소 포함). 어떤 id가 요청됐는지는
  // REGISTRY/REQUESTED 로 남아 나중에 추적할 수 있다. 앵커 존재 검증은 이 하네스의
  // 목적이 아니다 — 여기서는 '무엇이 렌더됐는가'만 본다.
  getElementById: id => { REQUESTED.add(id); return ensure(id); },
  querySelector: sel => {
    const m = /^#([\w-]+)$/.exec(sel);
    if (m) { REQUESTED.add(m[1]); return ensure(m[1]); }
    return new El('div');
  },
  querySelectorAll: () => [],
  addEventListener: () => {}, removeEventListener: () => {},
  execCommand: () => true,
  createTextNode: t => ({ textContent: t }),
};
documentStub.documentElement.dataset = {};

const store = {};
const localStorageStub = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};

globalThis.window = {
  addEventListener: () => {}, removeEventListener: () => {},
  matchMedia: () => ({ matches: false, addEventListener: () => {}, addListener: () => {} }),
  scrollTo: () => {}, scrollY: 0, innerHeight: 900, innerWidth: 1400,
  print: () => {}, open: () => ({ document: { write: () => {}, close: () => {} }, focus: () => {} }),
  location: { search: '', pathname: '/', origin: 'http://localhost', href: 'http://localhost/' },
  localStorage: localStorageStub,
  getComputedStyle: () => ({ getPropertyValue: () => '' }),
};
globalThis.document = documentStub;
globalThis.localStorage = localStorageStub;
globalThis.location = globalThis.window.location;
globalThis.navigator = { userAgent: 'node', clipboard: { writeText: () => Promise.resolve() } };
globalThis.gtag = () => {};
globalThis.requestAnimationFrame = fn => fn();
globalThis.getComputedStyle = globalThis.window.getComputedStyle;
globalThis.alert = () => {};
globalThis.matchMedia = globalThis.window.matchMedia;
globalThis.scrollTo = () => {};
globalThis.history = { replaceState: () => {}, pushState: () => {} };
globalThis.URL = URL; globalThis.URLSearchParams = URLSearchParams;

/* ---------------------------------------------------------------- 실행 */
require('./data.js'); require('./insights.js');
try { require('./apply_dates.js'); } catch (e) { /* 선택적 */ }

// --- 마커 주입 (PROBE=<필드명>) ---------------------------------------------
// 필드 하나의 값을 전부 고유 마커로 바꾼 뒤 렌더해, 그 마커가 화면 출력물에 나타나는지 본다.
// 값이 나타나면 그 필드는 확실히 화면에 도달한다 — 동명 필드·간접 경유·조건 게이트와 무관하게
// 실행 결과가 증명한다. 정적 분석이 원리적으로 못 하던 판정이다.
const PROBE = process.env.PROBE || '';
const MARK = '◈PROBE◈';
globalThis.__PROBE_ROW = process.env.PROBE_ROW || '0';   // 모달을 열 행 — 검사할 필드가 채워진 행
if (PROBE) {
  const D = globalThis.window.IPSI;
  const di = D.schema.indexOf(PROBE);
  if (D.dicts[PROBE]) {                       // 사전형 문자열 필드
    D.dicts[PROBE] = D.dicts[PROBE].map(v => (v ? MARK : v));
  } else if (PROBE === 'std26' || PROBE === 'std25') {
    D.dicts.std = D.dicts.std.map(v => (v ? MARK : v));
  } else if (di >= 0) {                        // rows 직접 보유 필드
    // ⚠️ 숫자 필드에 문자열 마커를 넣으면 fmtInt/toFixed 가 걸러내거나 죽는다(실측: c25·g26·g25 부팅실패).
    //    유효 범위 안의 고유 숫자를 넣어 화면에 그대로 찍히게 한다.
    const NUMERIC = { enroll: 7777, dn: 77, c26: 77.7, c25: 77.7, c24: 77.7,
                      g26: 7.77, g25: 7.77, g24: 7.77, v26: 777.7, v25: 777.7, v24: 777.7,
                      // 추합은 '명'과 '배'가 혼재해 app.js가 소수점 유무로 판정한다.
                      // 문자열 마커를 넣으면 파싱에 실패해 화면에서 사라진다 → 숫자로 넣는다.
                      chung26: 777, chung25: 777, chung24: 777 };
    const val = PROBE in NUMERIC ? NUMERIC[PROBE] : MARK;
    for (const r of D.rows) if (r[di] != null && r[di] !== '') r[di] = val;
    if (PROBE in NUMERIC) globalThis.__PROBE_NUM = String(NUMERIC[PROBE]);
  } else if (PROBE.startsWith('ins.')) {       // insights 필드
    const f = PROBE.slice(4);
    for (const u of Object.values(globalThis.window.IPSI_INSIGHTS.unis)) {
      // 배열 필드(tags 등)도 마커로 채운다 — 문자열만 처리하면 주입 자체가 안 돼
      // '미도달'로 오판된다(실측: ins.tags).
      if (f in u) u[f] = Array.isArray(u[f]) ? [MARK] : (typeof u[f] === 'string' ? MARK : u[f]);
      if (f === 'caption' || f === 'bullets' || f === 'icon' || f === 'title') {
        for (const s of (u.sections || [])) if (f in s) s[f] = Array.isArray(s[f]) ? [MARK] : MARK;
      }
      if (f === 'text' || f === 'type') for (const v of (u.verdict || [])) if (f in v) v[f] = f === 'type' ? v[f] : MARK;
      if (['label', 'from', 'to', 'note', 'dir'].includes(f)) {
        for (const s of (u.sections || [])) for (const r of (s.rows || [])) if (f in r && f !== 'dir') r[f] = MARK;
      }
    }
  }
}

let bootError = null;
try { require('./app.js'); } catch (e) { bootError = e; }

const initialCount = RENDERED.length;

/* ---------------------------------------------------------------- 결과 */
const ALL = RENDERED.map(r => r.html).join('\n');
const TEXT = stripTags(ALL);

if (process.argv.includes('--dump')) {
  const out = process.argv[process.argv.indexOf('--dump') + 1] || 'render_dump.html';
  fs.writeFileSync(out, ALL);
  console.log(`덤프 ${out} (${(ALL.length / 1024).toFixed(0)}KB)`);
}

module.exports = { ALL, TEXT, RENDERED, bootError, initialCount, El, ensure, HANDLERS, REGISTRY, REQUESTED, HTML_IDS, PROBES };

if (require.main === module) {
  console.log('부팅:', bootError ? '실패 — ' + bootError.message : '성공');
  if (bootError) { console.log(bootError.stack.split('\n').slice(0, 6).join('\n')); process.exit(2); }
  console.log('렌더 조각:', RENDERED.length, '· 총', (ALL.length / 1024).toFixed(0), 'KB');
  const byId = {};
  for (const r of RENDERED) byId[r.id || '(익명)'] = (byId[r.id || '(익명)'] || 0) + 1;
  console.log('렌더된 컨테이너:', Object.keys(byId).length, '개');
  console.log(' ', Object.entries(byId).sort((a, b) => b[1] - a[1]).slice(0, 14)
    .map(([k, v]) => `${k}(${v})`).join(' '));
}
