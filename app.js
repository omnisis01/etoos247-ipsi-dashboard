/* ============================================================
   2027 수시지원 대시보드 — app logic (vanilla JS, no deps)
   ============================================================ */
(function () {
'use strict';
const D = window.IPSI;
if (!D) { document.body.innerHTML = '<p style="padding:40px">data.js 로드 실패</p>'; return; }

/* ---------- decode dictionary-encoded rows into objects ---------- */
const dc = D.dicts;
const ROWS = D.rows.map((r, i) => ({
  _i: i,
  region: dc.region[r[0]] || '', sigun: dc.sigun[r[1]] || '', uni: dc.uni[r[2]] || '', gye: r[3] || '',
  dept: dc.dept[r[4]] || '', jhtype: r[5] || '', jhname: dc.jhname[r[6]] || '', jagyeok: dc.jagyeok[r[7]] || '',
  enroll: r[8], prev: r[9] || '', dkind: r[10] || 'none', dn: r[11],
  change: dc.change[r[12]] || '', choejeo: dc.choejeo[r[13]] || '', hasChoejeo: r[14], chKind: r[15] || '',
  c: [r[16], r[17], r[18]], g: [r[19], r[20], r[21]], v: [r[22], r[23], r[24]],
  chung: [r[25], r[26], r[27]],
  method: dc.method[r[28]] || '', note: dc.note[r[29]] || '', date: dc.date[r[30]] || '',
  gradeRatio: dc.gradeRatio[r[31]] || '', subjects: dc.subjects[r[32]] || '', careerSubj: dc.careerSubj[r[33]] || '',
  cats: r[34] || [], score: r[35] || 0, reasons: r[36] || [], gtrend: r[37] || 'na', ctrend: r[38] || 'na',
}));

const CAT_ICON = {
  all: '🎓', medical: '🩺', nursing_health: '🏥', engineering: '⚙️', natural: '🔬', business: '💼',
  language: '🗣️', humanities_core: '📜', non_business_humanities: '🏛️', social_science: '🌐',
  statistics: '📈', semiconductor: '💾', semiconductor_contract: '🔗', contract_other: '🤝',
  military: '🎖️', teaching: '🍎', primary_ed: '✏️', ist: '🧪', free_major: '🧭',
};
const CATS = D.cats;
const CAT_BY = {}; CATS.forEach(c => CAT_BY[c.key] = c);
const JHTYPES = ['학생부교과', '학생부종합', '논술', '실기/실적', '특기자'];
const REGIONS = [...new Set(ROWS.map(r => r.region).filter(Boolean))].sort();

/* ---------- state ---------- */
const S = {
  cat: 'all', search: '', jhtypes: new Set(), region: '', minLeast: '',
  changes: new Set(), gradeMax: 9.0, sort: 'impact', sortDir: -1,
  page: 1, perPage: 60, hlFilter: 'all', chartMetric: 'grade',
  compare: new Set(load('cmp', [])),
  fav: migrateFav(load('fav', null)),
};
const FAV_HOPE_MAX = 6, FAV_REACH_MAX = 3;
function migrateFav(v) {
  if (Array.isArray(v)) return { hope: v.slice(0, 6), reach: v.slice(6, 9) };       // 구버전(단일 배열) 호환
  if (v && Array.isArray(v.hope) && Array.isArray(v.reach)) return { hope: v.hope.slice(0, 6), reach: v.reach.slice(0, 3) };
  return { hope: [], reach: [] };
}
function load(k, def) { try { return JSON.parse(localStorage.getItem('ipsi_' + k)) ?? def; } catch (e) { return def; } }
function save(k, v) { try { localStorage.setItem('ipsi_' + k, JSON.stringify(v)); } catch (e) {} }

/* ---------- helpers ---------- */
const $ = s => document.querySelector(s);
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
const fmt = (v, d = 2) => (v == null || isNaN(v)) ? '–' : Number(v).toFixed(d);
const fmtInt = v => (v == null || isNaN(v)) ? '–' : Math.round(v).toLocaleString();
function avg(arr) { const a = arr.filter(x => x != null && !isNaN(x)); return a.length ? a.reduce((s, x) => s + x, 0) / a.length : null; }
function track(name, params) { try { if (typeof gtag === 'function') gtag('event', name, params || {}); } catch (e) {} }

function numOr(s) { if (s == null) return null; const m = String(s).match(/-?\d+\.?\d*/); return m ? parseFloat(m[0]) : null; }

/* ---- 2026 vs 2025 year-over-year per metric ---- */
function yoyGrade(r) { // 입결 등급: 숫자↑ = 입결 하락(쉬워짐) = 유리
  const a = r.g[1], b = r.g[0]; if (a == null || b == null) return null;
  const d = b - a; return { y25: a, y26: b, d, dir: d >= 0.1 ? 'easier' : d <= -0.1 ? 'harder' : 'flat' };
}
function yoyComp(r) { // 경쟁률: 하락 = 유리
  const a = r.c[1], b = r.c[0]; if (a == null || b == null) return null;
  const ratio = a ? b / a : 1, d = b - a;
  return { y25: a, y26: b, d, dir: ratio <= 0.9 ? 'down' : ratio >= 1.1 ? 'up' : 'flat' };
}
function yoyChung(r) { // 추합(충원): 증가 = 실질 문턱↓ = 유리
  const a = numOr(r.chung[1]), b = numOr(r.chung[0]); if (a == null || b == null) return null;
  const d = b - a; return { y25: a, y26: b, d, dir: d > 0 ? 'up' : d < 0 ? 'down' : 'flat' };
}

/* ---- 올해(2027) 입시 유불리 예상: 2026 vs 2025 결과 추이 + 2027 구조 변화 ---- */
function verdict(r) {
  const sig = []; let score = 0;
  // 2027 구조 변화 (모집인원)
  if (r.dkind === 'up') { sig.push({ dir: 'good', t: `모집인원 ${r.dn}명 증원`, m: '인원' }); score += 2; }
  else if (r.dkind === 'down') { sig.push({ dir: 'bad', t: `모집인원 ${Math.abs(r.dn)}명 감원`, m: '인원' }); score -= 2; }
  else if (r.dkind === 'new') sig.push({ dir: 'warn', t: '신설 — 첫해 입결 미형성(기회·변동)', m: '신설' });
  else if (r.dkind === 'closed') { sig.push({ dir: 'bad', t: '모집 폐지', m: '폐지' }); score -= 2; }
  else if (r.dkind === 'split') sig.push({ dir: 'warn', t: '모집단위 분리(인원·경쟁 재편)', m: '변동' });
  else if (r.dkind === 'merge') sig.push({ dir: 'warn', t: '모집단위 통합(인원·경쟁 재편)', m: '변동' });
  // 2027 구조 변화 (수능최저)
  if (r.chKind === '강화' || r.chKind === '신설') { sig.push({ dir: 'good', t: `수능최저 ${r.chKind} → 지원 위축`, m: '최저' }); score += 2; }
  else if (r.chKind === '완화' || r.chKind === '폐지') { sig.push({ dir: 'bad', t: `수능최저 ${r.chKind} → 지원 증가`, m: '최저' }); score -= 2; }
  // 2026 vs 2025 결과 추이 (핵심)
  const g = yoyGrade(r), c = yoyComp(r), ch = yoyChung(r);
  if (g) { if (g.dir === 'easier') { sig.push({ dir: 'good', t: `입결 하락세 ${g.y25.toFixed(2)}→${g.y26.toFixed(2)}등급`, m: '입결' }); score += 2; } else if (g.dir === 'harder') { sig.push({ dir: 'bad', t: `입결 상승세 ${g.y25.toFixed(2)}→${g.y26.toFixed(2)}등급`, m: '입결' }); score -= 2; } }
  if (c) { if (c.dir === 'down') { sig.push({ dir: 'good', t: `경쟁률 하락 ${c.y25.toFixed(1)}→${c.y26.toFixed(1)}:1`, m: '경쟁' }); score += 2; } else if (c.dir === 'up') { sig.push({ dir: 'bad', t: `경쟁률 상승 ${c.y25.toFixed(1)}→${c.y26.toFixed(1)}:1`, m: '경쟁' }); score -= 2; } }
  if (ch) { if (ch.dir === 'up') { sig.push({ dir: 'good', t: `추합 증가 ${ch.y25}→${ch.y26}명`, m: '충원' }); score += 1; } else if (ch.dir === 'down') { sig.push({ dir: 'bad', t: `추합 감소 ${ch.y25}→${ch.y26}명`, m: '충원' }); score -= 1; } }
  let cls, label;
  if (score >= 2) { cls = 'good'; label = '유리'; }
  else if (score <= -2) { cls = 'bad'; label = '불리'; }
  else if (score > 0) { cls = 'good'; label = '유리'; }
  else if (score < 0) { cls = 'bad'; label = '불리'; }
  else if (r.dkind === 'new') { cls = 'new'; label = '신설'; }
  else if (sig.length) { cls = 'neu'; label = '중립'; }
  else { cls = 'neu'; label = '변화 없음'; }
  return { cls, label, score, sig, g, c, ch };
}
const _vc = new Map();
function V(r) { let v = _vc.get(r._i); if (!v) { v = verdict(r); _vc.set(r._i, v); } return v; }
function impactSummary(r) { const v = V(r); return { cls: v.cls, label: v.label }; }
const deltaInfo = row => {
  switch (row.dkind) {
    case 'up': return { cls: 'up', txt: '▲' + (row.dn ?? '') };
    case 'down': return { cls: 'down', txt: '▼' + Math.abs(row.dn ?? '') };
    case 'new': return { cls: 'new', txt: '신설' };
    case 'closed': return { cls: 'down', txt: '폐지' };
    case 'split': return { cls: 'new', txt: '분리' };
    case 'merge': return { cls: 'new', txt: '통합' };
    default: return { cls: 'neu', txt: '–' };
  }
};

/* ---------- SVG sparkline (chronological 2024→2026) ---------- */
function sparkline(valsNewestFirst, opt = {}) {
  const vals = [valsNewestFirst[2], valsNewestFirst[1], valsNewestFirst[0]]; // chrono
  const pts = vals.map((v, i) => ({ v, i })).filter(p => p.v != null && !isNaN(p.v));
  const w = opt.w || 60, h = opt.h || 22, pad = 3;
  if (pts.length < 2) return `<svg class="spark" width="${w}" height="${h}"></svg>`;
  const xs = pts.map(p => p.i), ys = pts.map(p => p.v);
  const minX = 0, maxX = 2; let minY = Math.min(...ys), maxY = Math.max(...ys);
  if (minY === maxY) { minY -= 1; maxY += 1; }
  const sx = i => pad + (i - minX) / (maxX - minX) * (w - pad * 2);
  const inv = opt.invert; // grade: lower is better -> invert so better is up
  const sy = v => { const t = (v - minY) / (maxY - minY); return pad + (inv ? t : 1 - t) * (h - pad * 2); };
  const path = pts.map((p, k) => (k ? 'L' : 'M') + sx(p.i).toFixed(1) + ' ' + sy(p.v).toFixed(1)).join(' ');
  const last = pts[pts.length - 1];
  const col = opt.color || 'var(--primary)';
  let dots = pts.map(p => `<circle cx="${sx(p.i).toFixed(1)}" cy="${sy(p.v).toFixed(1)}" r="1.5" fill="${col}"/>`).join('');
  return `<svg class="spark" width="${w}" height="${h}"><path d="${path}" fill="none" stroke="${col}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>${dots}<circle cx="${sx(last.i).toFixed(1)}" cy="${sy(last.v).toFixed(1)}" r="2.6" fill="${col}"/></svg>`;
}

/* ---------- filtering ---------- */
function passChange(row) {
  if (!S.changes.size) return true;
  for (const c of S.changes) {
    if (c === 'new' && row.dkind === 'new') return true;
    if (c === 'up' && row.dkind === 'up') return true;
    if (c === 'down' && row.dkind === 'down') return true;
    if (c === 'ease' && row.chKind === '완화') return true;
    if (c === 'tighten' && (row.chKind === '강화' || row.chKind === '신설')) return true;
  }
  return false;
}
let FILTERED = [];
function applyFilters() {
  const q = S.search.trim().toLowerCase();
  FILTERED = ROWS.filter(r => {
    if (S.cat !== 'all' && !r.cats.includes(S.cat)) return false;
    if (S.jhtypes.size && !S.jhtypes.has(r.jhtype)) return false;
    if (S.region && r.region !== S.region) return false;
    if (S.minLeast === 'yes' && !r.hasChoejeo) return false;
    if (S.minLeast === 'no' && r.hasChoejeo) return false;
    if (!passChange(r)) return false;
    if (S.gradeMax < 9 && !(r.g[0] != null && r.g[0] <= S.gradeMax)) return false;
    if (q) {
      const hay = (r.uni + ' ' + r.dept + ' ' + r.jhname + ' ' + r.region + ' ' + r.jhtype).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  sortFiltered();
}
function sortFiltered() {
  const dir = S.sortDir;
  const key = S.sort;
  const val = r => {
    switch (key) {
      case 'impact': return V(r).score;
      case 'grade': return r.g[0] == null ? 999 : r.g[0];
      case 'comp': return r.c[0] == null ? -1 : r.c[0];
      case 'enroll': return r.enroll == null ? -1 : r.enroll;
      case 'uni': return r.uni;
      case 'delta': return (r.dn == null ? 0 : r.dn);
      default: return r.score;
    }
  };
  FILTERED.sort((a, b) => {
    let x = val(a), y = val(b);
    if (typeof x === 'string') return x.localeCompare(y, 'ko') * dir;
    if (x === y) { // tiebreak by grade asc
      const ga = a.g[0] == null ? 999 : a.g[0], gb = b.g[0] == null ? 999 : b.g[0];
      return ga - gb;
    }
    return (x - y) * dir;
  });
}

/* ============================================================
   RENDER
   ============================================================ */
function renderAll() { applyFilters(); S.page = 1; renderCatHeader(); renderKPIs(); renderHighlights(); renderCharts(); renderTable(); }
function renderSoft() { applyFilters(); renderCatHeader(); renderKPIs(); renderHighlights(); renderCharts(); renderTable(); }

/* ----- category list ----- */
function renderCatList() {
  const box = $('#catList'); box.innerHTML = '';
  const allBtn = el('button', 'cat-item all' + (S.cat === 'all' ? ' active' : ''));
  allBtn.innerHTML = `<span class="cat-dot"></span><span>전체 보기</span><span class="cat-n">${ROWS.length.toLocaleString()}</span>`;
  allBtn.onclick = () => { S.cat = 'all'; renderCatList(); renderAll(); };
  box.appendChild(allBtn);
  CATS.forEach(c => {
    const b = el('button', 'cat-item' + (S.cat === c.key ? ' active' : ''));
    b.innerHTML = `<span class="cat-dot" style="background:${c.color}"></span><span>${esc(c.label)}</span><span class="cat-n">${c.count.toLocaleString()}</span>`;
    b.title = c.desc;
    b.onclick = () => { S.cat = c.key; track('select_category', { category: c.key, label: c.label }); renderCatList(); renderAll(); closeSidebar(); };
    box.appendChild(b);
  });
}

/* ----- filters ----- */
function renderFilters() {
  const box = $('#filters'); box.innerHTML = '';
  // 전형유형
  const g1 = el('div', 'f-group');
  g1.innerHTML = '<div class="f-title">전형유형</div>';
  const r1 = el('div', 'chip-row');
  JHTYPES.forEach(t => {
    const c = el('button', 'chip' + (S.jhtypes.has(t) ? ' on' : ''), esc(t));
    c.onclick = () => { S.jhtypes.has(t) ? S.jhtypes.delete(t) : S.jhtypes.add(t); renderFilters(); renderSoft(); };
    r1.appendChild(c);
  });
  g1.appendChild(r1); box.appendChild(g1);

  // 변화 유형
  const g2 = el('div', 'f-group');
  g2.innerHTML = '<div class="f-title">2026 대비 변화</div>';
  const r2 = el('div', 'chip-row');
  [['new', '신설', 'new'], ['up', '증원', 'good'], ['down', '감원', 'bad'], ['ease', '최저 완화', 'bad'], ['tighten', '최저 강화·신설', 'good']].forEach(([k, lab, cls]) => {
    const c = el('button', 'chip' + (S.changes.has(k) ? ' on ' + cls : ''), esc(lab));
    c.onclick = () => { S.changes.has(k) ? S.changes.delete(k) : S.changes.add(k); renderFilters(); renderSoft(); };
    r2.appendChild(c);
  });
  g2.appendChild(r2); box.appendChild(g2);

  // 수능최저
  const g3 = el('div', 'f-group');
  g3.innerHTML = '<div class="f-title">수능최저</div>';
  const r3 = el('div', 'chip-row');
  [['', '전체'], ['yes', '있음'], ['no', '없음']].forEach(([k, lab]) => {
    const c = el('button', 'chip' + (S.minLeast === k ? ' on' : ''), lab);
    c.onclick = () => { S.minLeast = k; renderFilters(); renderSoft(); };
    r3.appendChild(c);
  });
  g3.appendChild(r3); box.appendChild(g3);

  // 지역
  const g4 = el('div', 'f-group');
  g4.innerHTML = '<div class="f-title">지역(광역)</div>';
  const sel = el('select', 'f-select');
  sel.innerHTML = '<option value="">전국 전체</option>' + REGIONS.map(r => `<option ${S.region === r ? 'selected' : ''}>${esc(r)}</option>`).join('');
  sel.onchange = () => { S.region = sel.value; renderSoft(); };
  g4.appendChild(sel); box.appendChild(g4);

  // 입결 상한
  const g5 = el('div', 'f-group');
  g5.innerHTML = `<div class="f-title">입결 등급 상한 <span class="range-val" id="gradeVal">${S.gradeMax >= 9 ? '전체' : '≤ ' + S.gradeMax.toFixed(1)}</span></div>`;
  const rng = el('input'); rng.type = 'range'; rng.min = '1'; rng.max = '9'; rng.step = '0.5'; rng.value = S.gradeMax;
  rng.oninput = () => { S.gradeMax = parseFloat(rng.value); $('#gradeVal').textContent = S.gradeMax >= 9 ? '전체' : '≤ ' + S.gradeMax.toFixed(1); };
  rng.onchange = () => renderSoft();
  g5.appendChild(rng); box.appendChild(g5);
}

/* ----- category header ----- */
function renderCatHeader() {
  const c = S.cat === 'all' ? { label: '전체 전형', desc: '전국 모든 대학·계열 수시 전형', color: 'var(--primary)', key: 'all' } : CAT_BY[S.cat];
  $('#catHeader').innerHTML =
    `<div class="ch-icon" style="background:${c.color}">${CAT_ICON[c.key] || '🎓'}</div>
     <div><h2>${esc(c.label)}</h2><p>${esc(c.desc)} · 검색결과 <b>${FILTERED.length.toLocaleString()}</b>개 전형</p></div>`;
}

/* ----- KPIs ----- */
function renderKPIs() {
  const f = FILTERED;
  const nNew = f.filter(r => r.dkind === 'new').length;
  const nUp = f.filter(r => r.dkind === 'up').length;
  const nDown = f.filter(r => r.dkind === 'down').length;
  const nTighten = f.filter(r => r.chKind === '강화' || r.chKind === '신설').length;
  const nEase = f.filter(r => r.chKind === '완화' || r.chKind === '폐지').length;
  const avgG = avg(f.map(r => r.g[0]));
  const avgC = avg(f.map(r => r.c[0]));
  const nUni = new Set(f.map(r => r.uni)).size;
  let nGood = 0, nBad = 0;
  f.forEach(r => { const v = V(r); if (v.label === '유리') nGood++; else if (v.label === '불리') nBad++; });
  const cards = [
    { cls: 'primary', label: '📑 전형 수', val: f.length.toLocaleString(), sub: `${nUni}개 대학` },
    { cls: 'good', label: '🟢 올해 유리', val: nGood.toLocaleString(), sub: '2026↔2025 + 변화 종합' },
    { cls: 'bad', label: '🔴 올해 불리', val: nBad.toLocaleString(), sub: '2026↔2025 + 변화 종합' },
    { cls: 'new', label: '✨ 신설', val: nNew.toLocaleString(), sub: '첫해 입결 주목' },
    { cls: 'good', label: '▲ 증원', val: nUp.toLocaleString(), sub: '합격선 하락 가능' },
    { cls: 'bad', label: '▼ 감원', val: nDown.toLocaleString(), sub: '합격선 상승 가능' },
    { cls: 'good', label: '🔒 최저 강화·신설', val: nTighten.toLocaleString(), sub: '지원 위축→유리' },
    { cls: 'bad', label: '🔓 최저 완화·폐지', val: nEase.toLocaleString(), sub: '지원 증가→경쟁↑' },
    { cls: '', label: '🎯 평균 입결(2026)', val: avgG == null ? '–' : avgG.toFixed(2), sub: '등급, 낮을수록 우수' },
    { cls: '', label: '🔥 평균 경쟁률(2026)', val: avgC == null ? '–' : avgC.toFixed(1) + ':1', sub: '지원자/모집' },
  ];
  $('#kpis').innerHTML = cards.map(c =>
    `<div class="kpi ${c.cls}"><div class="k-bar"></div><div class="k-label">${c.label}</div><div class="k-val">${c.val}</div><div class="k-sub">${c.sub}</div></div>`
  ).join('');
}

/* ----- YoY evidence strip (2026 vs 2025) ----- */
function yoyHTML(r, big) {
  const g = yoyGrade(r), c = yoyComp(r);
  const parts = [];
  if (g) { const cls = g.dir === 'easier' ? 'good' : g.dir === 'harder' ? 'bad' : 'neu';
    parts.push(`<span class="yoy ${cls}"><i>입결</i>${g.y25.toFixed(2)}<b>→</b>${g.y26.toFixed(2)}</span>`); }
  if (c) { const cls = c.dir === 'down' ? 'good' : c.dir === 'up' ? 'bad' : 'neu';
    parts.push(`<span class="yoy ${cls}"><i>경쟁</i>${c.y25.toFixed(1)}<b>→</b>${c.y26.toFixed(1)}</span>`); }
  if (!parts.length) return big ? '<div class="yoy-row"><span class="muted">2025·2026 입결 데이터 없음</span></div>' : '';
  return `<div class="yoy-row${big ? ' big' : ''}">${parts.join('')}</div>`;
}
/* ----- highlights (유불리 중심) ----- */
function hlRelevance(r) {
  const v = V(r);
  let s = Math.abs(v.score) * 10;
  if (r.dkind === 'new') s += 12;
  if (r.dkind === 'up' || r.dkind === 'down') s += Math.abs(r.dn || 0) * 1.5;
  if (r.c[0] != null) s += Math.min(r.c[0], 30) * 0.15;
  return s;
}
function renderHighlights() {
  const seg = $('#hlFilter');
  if (!seg.dataset.init) {
    seg.dataset.init = '1';
    seg.innerHTML = [['all', '전체'], ['good', '유리'], ['bad', '불리'], ['new', '신설']]
      .map(([k, l]) => `<button data-k="${k}" class="${S.hlFilter === k ? 'on' : ''}">${l}</button>`).join('');
    seg.onclick = e => { const b = e.target.closest('button'); if (!b) return; S.hlFilter = b.dataset.k; [...seg.children].forEach(c => c.classList.toggle('on', c.dataset.k === S.hlFilter)); renderHighlights(); };
  } else {
    [...seg.children].forEach(c => c.classList.toggle('on', c.dataset.k === S.hlFilter));
  }
  let pool = FILTERED.filter(r => {
    const v = V(r);
    if (!v.sig.length) return false;
    if (S.hlFilter === 'good') return v.label === '유리';
    if (S.hlFilter === 'bad') return v.label === '불리';
    if (S.hlFilter === 'new') return r.dkind === 'new';
    return true;
  });
  let top;
  if (S.hlFilter === 'all') {                       // 유리·불리·신설 교차 배치(편향 방지)
    const g = [], b = [], n = [];
    pool.forEach(r => { const c = V(r).cls; (c === 'good' ? g : c === 'bad' ? b : n).push(r); });
    [g, b, n].forEach(a => a.sort((x, y) => hlRelevance(y) - hlRelevance(x)));
    top = []; let gi = 0, bi = 0, ni = 0;
    while (top.length < 12 && (gi < g.length || bi < b.length || ni < n.length)) {
      if (gi < g.length) top.push(g[gi++]);
      if (top.length < 12 && bi < b.length) top.push(b[bi++]);
      if (top.length < 12 && ni < n.length && top.length % 4 === 3) top.push(n[ni++]);
    }
    [...g.slice(gi), ...b.slice(bi), ...n.slice(ni)].sort((x, y) => hlRelevance(y) - hlRelevance(x)).forEach(r => { if (top.length < 12) top.push(r); });
  } else {
    pool.sort((a, b) => hlRelevance(b) - hlRelevance(a));
    top = pool.slice(0, 12);
  }
  $('#hlSub').textContent = `· ${pool.length.toLocaleString()}건 중 주요 ${top.length}건`;
  const box = $('#highlightCards');
  if (!top.length) { box.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><div class="es-ico">🔍</div>이 조건에서 유불리 신호가 감지된 전형이 없습니다.</div>`; return; }
  box.innerHTML = top.map(r => {
    const v = V(r), d = deltaInfo(r);
    const tags = [];
    if (r.dkind === 'new') tags.push('<span class="tag new">신설</span>');
    else if (r.dkind === 'up') tags.push(`<span class="tag up">증원 ${d.txt}</span>`);
    else if (r.dkind === 'down') tags.push(`<span class="tag down">감원 ${d.txt}</span>`);
    else if (r.dkind === 'split') tags.push('<span class="tag new">분리</span>');
    else if (r.dkind === 'merge') tags.push('<span class="tag new">통합</span>');
    if (r.chKind) { const cls = (r.chKind === '강화' || r.chKind === '신설') ? 'up' : 'down'; tags.push(`<span class="tag ${cls}">최저 ${r.chKind}</span>`); }
    const reasons = v.sig.slice(0, 2).map(s => {
      const ico = s.dir === 'good' ? '<span class="dot-good">▲</span>' : s.dir === 'bad' ? '<span class="dot-bad">▼</span>' : '<span class="dot-new">✦</span>';
      return `<div class="imp-line">${ico}<span>${esc(s.t)}</span></div>`;
    }).join('');
    return `<div class="hl-card" data-i="${r._i}">
      <div class="hl-top"><span class="hl-uni">${esc(r.uni)}</span><span class="impact-chip ${v.cls}" style="margin-left:auto">${v.label}</span></div>
      <div class="hl-dept">${esc(r.dept)}</div>
      <div class="hl-jh">${esc(r.jhtype)} · ${esc(r.jhname)} · 모집 ${fmtInt(r.enroll)}명</div>
      ${yoyHTML(r)}
      <div class="hl-tags">${tags.join('')}</div>
      <div class="hl-impact">${reasons || '<span class="muted">상세 보기</span>'}</div>
    </div>`;
  }).join('');
  box.querySelectorAll('.hl-card').forEach(c => c.onclick = () => openModal(+c.dataset.i));
}

/* ----- charts ----- */
function renderCharts() {
  const seg = $('#chartMetric');
  if (!seg.dataset.init) {
    seg.dataset.init = '1';
    seg.innerHTML = [['grade', '평균 입결'], ['comp', '평균 경쟁률'], ['count', '전형 수']]
      .map(([k, l]) => `<button data-k="${k}" class="${S.chartMetric === k ? 'on' : ''}">${l}</button>`).join('');
    seg.onclick = e => { const b = e.target.closest('button'); if (!b) return; S.chartMetric = b.dataset.k; [...seg.children].forEach(c => c.classList.toggle('on', c.dataset.k === S.chartMetric)); renderCharts(); };
  }
  // aggregate by university
  const byU = {};
  FILTERED.forEach(r => { (byU[r.uni] = byU[r.uni] || []).push(r); });
  let arr = Object.entries(byU).map(([uni, rs]) => ({
    uni, n: rs.length, grade: avg(rs.map(r => r.g[0])), comp: avg(rs.map(r => r.c[0])),
  }));
  const metric = S.chartMetric;
  if (metric === 'grade') { arr = arr.filter(a => a.grade != null).sort((a, b) => a.grade - b.grade); }
  else if (metric === 'comp') { arr = arr.filter(a => a.comp != null).sort((a, b) => b.comp - a.comp); }
  else { arr.sort((a, b) => b.n - a.n); }
  arr = arr.slice(0, 22);
  $('#chartTitleA').textContent = metric === 'grade' ? '대학별 평균 입결등급 (낮을수록 상위) · 상위 22' : metric === 'comp' ? '대학별 평균 경쟁률 (높은 순) · 상위 22' : '대학별 전형 수 · 상위 22';
  const catColor = S.cat === 'all' ? 'var(--primary)' : CAT_BY[S.cat].color;
  if (!arr.length) { $('#chartA').innerHTML = '<div class="no-data" style="padding:20px">데이터 없음</div>'; }
  else {
    const getV = a => metric === 'grade' ? a.grade : metric === 'comp' ? a.comp : a.n;
    const maxV = Math.max(...arr.map(getV));
    const minV = metric === 'grade' ? Math.min(...arr.map(getV)) : 0;
    $('#chartA').innerHTML = arr.map(a => {
      const v = getV(a);
      const w = metric === 'grade'
        ? (8 + (1 - (v - minV) / ((maxV - minV) || 1)) * 88) // shorter bar = better grade visually inverted
        : (8 + v / (maxV || 1) * 90);
      const label = metric === 'grade' ? v.toFixed(2) : metric === 'comp' ? v.toFixed(1) + ':1' : v + '개';
      const inside = w >= 26;
      return `<div class="bar-row"><div class="bl" data-uni="${esc(a.uni)}" title="${esc(a.uni)}">${esc(a.uni)}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${w.toFixed(1)}%;background:${catColor}">${inside ? label : ''}</div>${inside ? '' : `<span class="bar-val-out">${label}</span>`}</div>
        <div class="bn">${a.n}개</div></div>`;
    }).join('');
    $('#chartA').querySelectorAll('.bl').forEach(b => b.onclick = () => { $('#search').value = b.dataset.uni; S.search = b.dataset.uni; renderAll(); });
  }
  // trend chart B
  renderTrendChart();
}
function renderTrendChart() {
  const f = FILTERED;
  const yearsLab = ['2024', '2025', '2026'];
  const gradeY = [avg(f.map(r => r.g[2])), avg(f.map(r => r.g[1])), avg(f.map(r => r.g[0]))];
  const compY = [avg(f.map(r => r.c[2])), avg(f.map(r => r.c[1])), avg(f.map(r => r.c[0]))];
  const W = 320, H = 190, padL = 38, padR = 38, padT = 18, padB = 26;
  const x = i => padL + i / 2 * (W - padL - padR);
  function series(vals, lo, hi, color, fmtf, below) {
    const ok = vals.map((v, i) => ({ v, i })).filter(p => p.v != null);
    if (ok.length < 2) return '';
    const y = v => padT + (1 - (v - lo) / ((hi - lo) || 1)) * (H - padT - padB);
    const path = ok.map((p, k) => (k ? 'L' : 'M') + x(p.i) + ' ' + y(p.v).toFixed(1)).join(' ');
    const dots = ok.map(p => `<circle cx="${x(p.i)}" cy="${y(p.v).toFixed(1)}" r="3.4" fill="${color}"/>
      <text x="${x(p.i)}" y="${(y(p.v) + (below ? 16 : -8)).toFixed(1)}" text-anchor="middle" font-size="10" font-weight="800" fill="${color}">${fmtf(p.v)}</text>`).join('');
    return `<path d="${path}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>${dots}`;
  }
  const gOk = gradeY.filter(v => v != null), cOk = compY.filter(v => v != null);
  let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%">`;
  svg += `<line class="axis" x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}"/>`;
  yearsLab.forEach((l, i) => { svg += `<text x="${x(i)}" y="${H - padB + 16}" text-anchor="middle" font-size="10.5" font-weight="700">${l}</text>`; });
  if (gOk.length) { const lo = Math.min(...gOk) - .3, hi = Math.max(...gOk) + .3; svg += series(gradeY, lo, hi, 'var(--primary)', v => v.toFixed(2), true); }
  if (cOk.length) { const lo = Math.min(...cOk) * .8, hi = Math.max(...cOk) * 1.15; svg += series(compY, lo, hi, 'var(--new)', v => v.toFixed(1), false); }
  svg += `</svg>`;
  svg += `<div class="legend"><span><i style="background:var(--primary)"></i>평균 입결등급</span><span><i style="background:var(--new)"></i>평균 경쟁률</span></div>`;
  $('#chartB').innerHTML = svg;
}

/* ----- table ----- */
const COLS = [
  { k: 'uni', label: '대학 / 모집단위', sort: 'uni' },
  { k: 'jh', label: '전형', sort: null },
  { k: 'enroll', label: '모집(전년대비)', sort: 'enroll' },
  { k: 'least', label: '수능최저', sort: null },
  { k: 'grade', label: '입결 2026 (전년비)', sort: 'grade' },
  { k: 'comp', label: '경쟁률 2026 (전년비)', sort: 'comp' },
  { k: 'impact', label: '올해 유불리', sort: 'impact' },
  { k: 'add', label: '담기', sort: null },
];
function yoyBadge(r, kind) {
  if (kind === 'grade') { const g = yoyGrade(r); if (!g || g.dir === 'flat') return ''; const cls = g.dir === 'easier' ? 'good' : 'bad'; const ar = g.dir === 'harder' ? '▲' : '▼';
    return `<span class="ybadge ${cls}" title="입결 ${g.y25.toFixed(2)} → ${g.y26.toFixed(2)}등급 · ${g.dir === 'easier' ? '입결 하락(쉬워짐)·유리' : '입결 상승(어려워짐)·불리'}">${ar}${Math.abs(g.d).toFixed(2)}</span>`; }
  if (kind === 'comp') { const c = yoyComp(r); if (!c || c.dir === 'flat') return ''; const cls = c.dir === 'down' ? 'good' : 'bad'; const ar = c.y26 > c.y25 ? '▲' : '▼';
    return `<span class="ybadge ${cls}" title="2025 ${c.y25.toFixed(1)} → 2026 ${c.y26.toFixed(1)}:1 (${c.dir === 'down' ? '경쟁 완화·유리' : '경쟁 심화·불리'})">${ar}${Math.abs(c.d).toFixed(1)}</span>`; }
  return '';
}
function renderTable() {
  $('#gridHead').innerHTML = '<tr>' + COLS.map(c =>
    `<th data-sort="${c.sort || ''}" class="${c.sort === S.sort ? 'sorted' : ''}">${c.label}${c.sort ? `<span class="sort-ar">${c.sort === S.sort ? (S.sortDir < 0 ? '▼' : '▲') : '▽'}</span>` : ''}</th>`
  ).join('') + '</tr>';
  $('#gridHead').querySelectorAll('th').forEach(th => {
    const sk = th.dataset.sort; if (!sk) return;
    th.onclick = () => { if (S.sort === sk) S.sortDir *= -1; else { S.sort = sk; S.sortDir = (sk === 'grade' || sk === 'uni') ? 1 : -1; } sortFiltered(); S.page = 1; renderTable(); };
  });
  // sort segment quick
  const ss = $('#sortSeg');
  if (!ss.dataset.init) {
    ss.dataset.init = '1';
    ss.innerHTML = [['impact', '유불리순'], ['grade', '입결 낮은순'], ['comp', '경쟁률순'], ['enroll', '모집인원순']]
      .map(([k, l]) => `<button data-k="${k}" class="${S.sort === k ? 'on' : ''}">${l}</button>`).join('');
    ss.onclick = e => { const b = e.target.closest('button'); if (!b) return; S.sort = b.dataset.k; S.sortDir = b.dataset.k === 'grade' ? 1 : -1; [...ss.children].forEach(c => c.classList.toggle('on', c.dataset.k === S.sort)); sortFiltered(); S.page = 1; renderTable(); };
  } else { [...ss.children].forEach(c => c.classList.toggle('on', c.dataset.k === S.sort)); }

  const total = FILTERED.length;
  const pages = Math.max(1, Math.ceil(total / S.perPage));
  if (S.page > pages) S.page = pages;
  const start = (S.page - 1) * S.perPage;
  const slice = FILTERED.slice(start, start + S.perPage);
  $('#tableCount').textContent = `· 총 ${total.toLocaleString()}개`;

  $('#gridBody').innerHTML = slice.map(r => {
    const d = deltaInfo(r);
    const v = V(r);
    const gradeSpark = sparkline(r.g, { invert: true, color: 'var(--primary)' });
    const compSpark = sparkline(r.c, { color: 'var(--new)' });
    const least = r.hasChoejeo
      ? `<span class="jh-pill" style="background:var(--primary-soft);color:var(--primary-ink);border:none" title="${esc(r.choejeo)}">${esc(r.choejeo.slice(0, 16))}${r.choejeo.length > 16 ? '…' : ''}</span>${r.chKind ? `<span class="delta ${(r.chKind === '강화' || r.chKind === '신설') ? 'up' : 'down'}" style="margin-left:4px">${r.chKind}</span>` : ''}`
      : '<span class="no-data">없음</span>';
    const inCmp = S.compare.has(r._i);
    const fb = favBucket(r._i);
    return `<tr data-i="${r._i}">
      <td><div class="td-uni">${esc(r.uni)} <span class="muted">${esc(r.region)}</span></div><div class="td-dept">${esc(r.dept)}</div></td>
      <td><span class="jh-pill">${esc(r.jhtype.replace('학생부', ''))}</span><div class="muted" style="margin-top:3px">${esc(r.jhname.slice(0, 14))}</div></td>
      <td class="enroll-cell">${fmtInt(r.enroll)}<span class="delta ${d.cls}">${d.txt}</span></td>
      <td>${least}</td>
      <td><div class="cell-top"><span class="grade-val">${fmt(r.g[0])}</span>${yoyBadge(r, 'grade')}</div>${gradeSpark}</td>
      <td><div class="cell-top"><span class="grade-val">${r.c[0] == null ? '–' : r.c[0].toFixed(1)}</span>${yoyBadge(r, 'comp')}</div>${compSpark}</td>
      <td><span class="impact-chip ${v.cls}">${v.label}</span></td>
      <td><div class="row-btns"><button class="row-fav ${fb ? 'in ' + fb : ''}" data-fav="${r._i}" title="지원카드에 담기 (지원희망/상향 선택)">${fb ? '★' : '☆'}</button><button class="row-add ${inCmp ? 'in' : ''}" data-add="${r._i}" title="비교함에 담기">${inCmp ? '✓' : '⇄'}</button></div></td>
    </tr>`;
  }).join('');
  $('#gridBody').querySelectorAll('tr').forEach(tr => {
    tr.onclick = e => { if (e.target.closest('[data-add],[data-fav]')) return; openModal(+tr.dataset.i); };
  });
  $('#gridBody').querySelectorAll('[data-add]').forEach(b => b.onclick = e => { e.stopPropagation(); toggleCompare(+b.dataset.add); });
  $('#gridBody').querySelectorAll('[data-fav]').forEach(b => b.onclick = e => { e.stopPropagation(); openFavMenu(+b.dataset.fav, b); });
  renderPager(pages, total);
}
function renderPager(pages, total) {
  const p = $('#pager');
  if (pages <= 1) { p.innerHTML = total ? `<span class="pg-info">총 ${total.toLocaleString()}개</span>` : ''; return; }
  const cur = S.page;
  let btns = [];
  const mk = (n, lab, on, dis) => `<button ${dis ? 'disabled' : ''} class="${on ? 'on' : ''}" data-p="${n}">${lab || n}</button>`;
  btns.push(mk(cur - 1, '‹', false, cur === 1));
  const win = [];
  let s = Math.max(1, cur - 2), e = Math.min(pages, cur + 2);
  if (cur <= 3) e = Math.min(pages, 5);
  if (cur >= pages - 2) s = Math.max(1, pages - 4);
  if (s > 1) { btns.push(mk(1)); if (s > 2) btns.push('<span class="pg-info">…</span>'); }
  for (let i = s; i <= e; i++) btns.push(mk(i, null, i === cur));
  if (e < pages) { if (e < pages - 1) btns.push('<span class="pg-info">…</span>'); btns.push(mk(pages)); }
  btns.push(mk(cur + 1, '›', false, cur === pages));
  btns.push(`<span class="pg-info">${cur} / ${pages}</span>`);
  p.innerHTML = btns.join('');
  p.querySelectorAll('button[data-p]').forEach(b => b.onclick = () => { S.page = +b.dataset.p; renderTable(); window.scrollTo({ top: $('#tableSec').offsetTop - 70, behavior: 'smooth' }); });
}

/* ----- detail modal ----- */
function openModal(i) {
  const r = ROWS[i];
  const d = deltaInfo(r), v = V(r);
  track('view_program', { uni: r.uni, dept: r.dept, verdict: v.label });
  // vals are chronological [2024,2025,2026]; sparkline expects newest-first → reverse
  const trendRow = (lab, vals, f, color) => `<tr><td class="metric">${lab}</td>${vals.map(x => `<td>${x == null ? '–' : f(x)}</td>`).join('')}<td>${sparkline([vals[2], vals[1], vals[0]], { color, invert: color === 'var(--primary)' })}</td></tr>`;
  const reasons = v.sig.length ? v.sig.map(s => {
    const ico = s.dir === 'good' ? '🟢' : s.dir === 'bad' ? '🔴' : '🟠';
    return `<div class="imp-line"><span class="imp-ico">${ico}</span><span><b>[${esc(s.m)}]</b> ${esc(s.t)}</span></div>`;
  }).join('') : '<div class="muted">2026·2025 추이/구조 변화에서 두드러진 신호가 없습니다.</div>';
  // 2026 vs 2025 per-metric comparison
  const yoyCmp = (lab, info, fmtf, goodWhen) => {
    if (!info) return `<tr><td class="metric">${lab}</td><td>–</td><td>–</td><td colspan="2"><span class="muted">데이터 없음</span></td></tr>`;
    const good = goodWhen(info.dir);
    const cls = info.dir === 'flat' ? 'neu' : good ? 'good' : 'bad';
    const word = info.dir === 'flat' ? '변화 미미' : good ? '유리' : '불리';
    // 입결은 난이도 기준 화살표(상승=▲), 그 외는 값 기준
    const ar = lab.includes('입결')
      ? (info.dir === 'harder' ? '▲' : info.dir === 'easier' ? '▼' : '–')
      : (info.y26 > info.y25 ? '▲' : info.y26 < info.y25 ? '▼' : '–');
    const dec = lab.includes('입결') ? 2 : lab.includes('추합') ? 0 : 1;
    return `<tr><td class="metric">${lab}</td><td>${fmtf(info.y25)}</td><td><b>${fmtf(info.y26)}</b></td><td class="ycell ${cls}">${ar} ${Math.abs(info.d).toFixed(dec)}</td><td><span class="impact-chip ${cls}">${word}</span></td></tr>`;
  };
  const cats = r.cats.map(k => CAT_BY[k] ? `<span class="tag" style="background:${CAT_BY[k].color}22;color:${CAT_BY[k].color}">${esc(CAT_BY[k].label)}</span>` : '').join(' ');
  const inCmp = S.compare.has(i);
  const bk = favBucket(i);
  $('#modalCard').innerHTML = `
    <div class="modal-head"><div class="mh-top"><div>
      <div class="mh-uni">${esc(r.uni)} · ${esc(r.region)} ${esc(r.sigun)}</div>
      <h3>${esc(r.dept)}</h3>
      <div style="margin-top:7px;display:flex;gap:6px;flex-wrap:wrap">${cats}</div>
    </div><button class="modal-close" id="modalClose">✕</button></div></div>
    <div class="modal-body">
      <div class="msec"><div class="kv">
        <dt>전형</dt><dd>${esc(r.jhtype)} · ${esc(r.jhname)}</dd>
        <dt>모집인원</dt><dd><b>${fmtInt(r.enroll)}명</b> <span class="delta ${d.cls}">${d.txt}</span> <span class="muted">(2026 대비: ${esc(r.prev || '-')})</span></dd>
        <dt>지원자격</dt><dd>${esc(r.jagyeok) || '–'}</dd>
        <dt>전형방법</dt><dd>${esc(r.method) || '–'}</dd>
        <dt>수능최저</dt><dd>${r.hasChoejeo ? esc(r.choejeo) : '없음'} ${r.chKind ? `<span class="delta ${(r.chKind === '강화' || r.chKind === '신설') ? 'up' : 'down'}">최저 ${r.chKind}</span>` : ''}</dd>
        ${r.gradeRatio ? `<dt>학년별반영</dt><dd>${esc(r.gradeRatio)}</dd>` : ''}
        ${r.subjects ? `<dt>반영과목</dt><dd>${esc(r.subjects)}</dd>` : ''}
        ${r.careerSubj ? `<dt>진로선택</dt><dd>${esc(r.careerSubj)}</dd>` : ''}
        ${r.date ? `<dt>대학별고사</dt><dd>${esc(r.date)}</dd>` : ''}
      </div></div>
      <div class="msec hero-sec"><h4>🎯 올해 입시 유불리 예상 <span class="muted">2026 vs 2025 + 2027 변화 종합 · 자동 추정</span></h4>
        <div class="verdict-head"><span class="verdict-big ${v.cls}">${v.label}</span>
          <span class="muted">${v.cls === 'good' ? '합격선이 낮아질 신호가 우세합니다.' : v.cls === 'bad' ? '합격선이 높아질 신호가 우세합니다.' : v.cls === 'new' ? '신설로 입결이 미형성되어 변동성이 큽니다.' : '뚜렷한 방향성이 약합니다.'}</span></div>
        <table class="trend-table yoy-table"><thead><tr><th>지표</th><th>2025</th><th>2026</th><th>전년비</th><th>해석</th></tr></thead><tbody>
          ${yoyCmp('입결(등급)', v.g, x => x.toFixed(2), dir => dir === 'easier')}
          ${yoyCmp('경쟁률', v.c, x => x.toFixed(1) + ':1', dir => dir === 'down')}
          ${yoyCmp('추합(충원)', v.ch, x => Math.round(x), dir => dir === 'up')}
        </tbody></table>
        <div class="impact-box" style="margin-top:12px">${reasons}</div>
        <div class="muted" style="margin-top:6px">※ 입결 하락세·경쟁률 하락·증원·수능최저 강화는 ‘유리’ 신호로, 그 반대는 ‘불리’ 신호로 추정합니다.</div>
      </div>
      ${r.change ? `<div class="msec"><h4>📝 2026 대비 변경사항(2027)</h4><div class="change-box">${esc(r.change)}</div></div>` : ''}
      <div class="msec"><h4>📈 3개년 입결·경쟁률 추이</h4>
        <table class="trend-table"><thead><tr><th>구분</th><th>2024</th><th>2025</th><th>2026</th><th>추이</th></tr></thead><tbody>
          ${trendRow('입결(등급)', [r.g[2], r.g[1], r.g[0]], v => v.toFixed(2), 'var(--primary)')}
          ${trendRow('입결(환산)', [r.v[2], r.v[1], r.v[0]], v => v.toFixed(1), 'var(--good)')}
          ${trendRow('경쟁률', [r.c[2], r.c[1], r.c[0]], v => v.toFixed(2) + ':1', 'var(--new)')}
          ${trendRow('충원(추합)', [numOr(r.chung[2]), numOr(r.chung[1]), numOr(r.chung[0])], v => Math.round(v), 'var(--neutral)')}
        </tbody></table>
        <div class="muted" style="margin-top:6px">※ 입결 등급은 낮을수록 우수. 환산점수는 대학별 산출식이 달라 학교 간 직접 비교 불가.</div>
      </div>
      ${r.note ? `<div class="msec"><h4>💡 지원 시 유의사항</h4><div class="change-box" style="background:var(--surface-2);color:var(--text-soft);border-color:var(--line)">${esc(r.note)}</div></div>` : ''}
      <div class="msec"><h4>🗂️ 지원카드에 담기 <span class="muted">지원희망 또는 상향을 선택</span></h4>
        <div class="modal-actions">
          <button class="ghost-btn fav-pick ${bk === 'hope' ? 'on' : ''}" id="modalFavHope">${bk === 'hope' ? '✓ 지원희망에 담김' : '🎯 지원희망으로'} <span class="muted">${S.fav.hope.length}/6</span></button>
          <button class="ghost-btn fav-pick reach ${bk === 'reach' ? 'on' : ''}" id="modalFavReach">${bk === 'reach' ? '✓ 상향에 담김' : '🚀 상향·도전으로'} <span class="muted">${S.fav.reach.length}/3</span></button>
        </div>
        <button class="ghost-btn" id="modalAdd" style="width:100%;justify-content:center;margin-top:8px">${inCmp ? '✓ 비교함에서 보기' : '⇄ 비교함에 담기'}</button>
      </div>
    </div>`;
  $('#modal').classList.remove('hidden');
  $('#modalClose').onclick = closeModal;
  $('#modalAdd').onclick = () => { if (S.compare.has(i)) { openCompare(); } else { toggleCompare(i); openModal(i); } };
  $('#modalFavHope').onclick = () => { addFav(i, 'hope'); openModal(i); };
  $('#modalFavReach').onclick = () => { addFav(i, 'reach'); openModal(i); };
}
function closeModal() { $('#modal').classList.add('hidden'); }
$('#modal').onclick = e => { if (e.target.id === 'modal') closeModal(); };

/* ----- compare ----- */
function toggleCompare(i) {
  if (S.compare.has(i)) S.compare.delete(i);
  else { if (S.compare.size >= 6) { alert('최대 6개까지 비교할 수 있습니다.'); return; } S.compare.add(i); }
  save('cmp', [...S.compare]);
  updateCompareBtn(); renderTable();
}
function updateCompareBtn() { $('#compareCount').textContent = S.compare.size; }
function openCompare() {
  const items = [...S.compare].map(i => ROWS[i]);
  const inner = $('#compareInner');
  if (!items.length) {
    inner.innerHTML = `<div class="drawer-head"><h3>비교함</h3><button class="modal-close" id="cmpClose">✕</button></div><div class="empty-state"><div class="es-ico">📊</div>비교할 전형을 표(＋ 버튼)에서 담아보세요.<br>같은 카테고리 내 여러 대학을 나란히 비교할 수 있습니다.</div>`;
  } else {
    const rowM = (lab, fn) => `<tr><td class="rowlab">${lab}</td>${items.map(r => `<td>${fn(r)}</td>`).join('')}</tr>`;
    inner.innerHTML = `<div class="drawer-head"><h3>전형 비교 <span class="muted">${items.length}개</span></h3>
      <div style="display:flex;gap:8px"><button class="ghost-btn" id="cmpClear">전체 비우기</button><button class="modal-close" id="cmpClose">✕</button></div></div>
      <div style="overflow-x:auto;padding:0 4px 30px"><table class="cmp-table"><thead><tr><th>구분</th>${items.map(r =>
        `<th>${esc(r.uni)}<div class="muted">${esc(r.dept.slice(0, 16))}</div><div class="cmp-rm" data-rm="${r._i}">✕ 제거</div></th>`).join('')}</tr></thead><tbody>
        ${rowM('🎯 올해 유불리', r => `<span class="impact-chip ${V(r).cls}">${V(r).label}</span>`)}
        ${rowM('계열/지역', r => esc(r.gye) + ' · ' + esc(r.region))}
        ${rowM('전형', r => esc(r.jhtype) + '<br><span class="muted">' + esc(r.jhname) + '</span>')}
        ${rowM('모집인원(전년대비)', r => `<b>${fmtInt(r.enroll)}</b> <span class="delta ${deltaInfo(r).cls}">${deltaInfo(r).txt}</span>`)}
        ${rowM('수능최저', r => r.hasChoejeo ? esc(r.choejeo) + (r.chKind ? ` <span class="delta ${(r.chKind === '강화' || r.chKind === '신설') ? 'up' : 'down'}">${r.chKind}</span>` : '') : '<span class="muted">없음</span>')}
        ${rowM('입결 2025→2026', r => { const g = yoyGrade(r); return `${fmt(r.g[1])} → <b>${fmt(r.g[0])}</b>` + (g && g.dir !== 'flat' ? ` <span class="ycell ${g.dir === 'easier' ? 'good' : 'bad'}">${g.dir === 'easier' ? '유리' : '불리'}</span>` : ''); })}
        ${rowM('입결 추이', r => sparkline(r.g, { invert: true, color: 'var(--primary)', w: 70 }))}
        ${rowM('경쟁률 2025→2026', r => { const c = yoyComp(r); return (r.c[1] == null ? '–' : r.c[1].toFixed(1)) + ' → <b>' + (r.c[0] == null ? '–' : r.c[0].toFixed(1)) + ':1</b>' + (c && c.dir !== 'flat' ? ` <span class="ycell ${c.dir === 'down' ? 'good' : 'bad'}">${c.dir === 'down' ? '유리' : '불리'}</span>` : ''); })}
        ${rowM('경쟁률 추이', r => sparkline(r.c, { color: 'var(--new)', w: 70 }))}
        ${rowM('충원 2025→2026', r => esc(r.chung[1] || '–') + ' → ' + esc(r.chung[0] || '–'))}
      </tbody></table></div>`;
  }
  $('#compareDrawer').classList.remove('hidden');
  $('#cmpClose').onclick = () => $('#compareDrawer').classList.add('hidden');
  const clr = $('#cmpClear'); if (clr) clr.onclick = () => { S.compare.clear(); save('cmp', []); updateCompareBtn(); renderTable(); openCompare(); };
  inner.querySelectorAll('[data-rm]').forEach(b => b.onclick = () => { S.compare.delete(+b.dataset.rm); save('cmp', [...S.compare]); updateCompareBtn(); renderTable(); openCompare(); });
}
$('#compareDrawer').onclick = e => { if (e.target.id === 'compareDrawer') $('#compareDrawer').classList.add('hidden'); };
$('#compareBtn').onclick = openCompare;

/* ----- favorites (지원카드: 지원희망 6 + 상향·도전 3, 버킷 선택) ----- */
const BUCKET_MAX = { hope: FAV_HOPE_MAX, reach: FAV_REACH_MAX };
const BUCKET_NAME = { hope: '지원희망', reach: '상향·도전' };
function favBucket(i) { return S.fav.hope.includes(i) ? 'hope' : S.fav.reach.includes(i) ? 'reach' : null; }
function isFav(i) { return !!favBucket(i); }
function favCount() { return S.fav.hope.length + S.fav.reach.length; }
function saveFav() { save('fav', S.fav); updateFavBtn(); }
function updateFavBtn() { $('#favCount').textContent = favCount(); }
function addFav(i, bucket) {
  const cur = favBucket(i);
  if (cur === bucket) { removeFav(i); return; }                 // 같은 버킷 다시 누르면 토글 해제
  if (S.fav[bucket].length >= BUCKET_MAX[bucket]) { alert(`${BUCKET_NAME[bucket]}은(는) 최대 ${BUCKET_MAX[bucket]}장까지 담을 수 있습니다.`); return; }
  if (cur) S.fav[cur].splice(S.fav[cur].indexOf(i), 1);         // 다른 버킷이면 이동
  S.fav[bucket].push(i);
  track('add_favorite', { uni: ROWS[i].uni, dept: ROWS[i].dept, bucket });
  saveFav(); renderTable(); if (!$('#favDrawer').classList.contains('hidden')) openFav();
}
function removeFav(i) {
  const b = favBucket(i); if (!b) return;
  S.fav[b].splice(S.fav[b].indexOf(i), 1);
  saveFav(); renderTable(); if (!$('#favDrawer').classList.contains('hidden')) openFav();
}
function switchBucket(i) {
  const cur = favBucket(i); if (!cur) return;
  const other = cur === 'hope' ? 'reach' : 'hope';
  if (S.fav[other].length >= BUCKET_MAX[other]) { alert(`${BUCKET_NAME[other]}은(는) 최대 ${BUCKET_MAX[other]}장입니다.`); return; }
  S.fav[cur].splice(S.fav[cur].indexOf(i), 1); S.fav[other].push(i);
  saveFav(); renderTable(); openFav();
}
function moveFav(bucket, pos, dir) {
  const arr = S.fav[bucket], j = pos + dir; if (j < 0 || j >= arr.length) return;
  [arr[pos], arr[j]] = [arr[j], arr[pos]]; saveFav(); openFav(); renderTable();
}
/* add-time bucket chooser popover */
function closeFavMenu() { const m = document.querySelector('.fav-menu'); if (m) m.remove(); }
function openFavMenu(i, anchor) {
  closeFavMenu();
  const cur = favBucket(i);
  const m = el('div', 'fav-menu');
  m.innerHTML = `<div class="fm-title">지원카드에 담기</div>
    <button data-b="hope" class="${cur === 'hope' ? 'on' : ''}"><span>🎯 지원희망</span><span class="fm-n">${S.fav.hope.length}/6</span></button>
    <button data-b="reach" class="${cur === 'reach' ? 'on reach' : 'reach'}"><span>🚀 상향·도전</span><span class="fm-n">${S.fav.reach.length}/3</span></button>
    ${cur ? `<button data-b="remove" class="fm-rm">✕ 지원카드에서 빼기</button>` : ''}`;
  document.body.appendChild(m);
  const r = anchor.getBoundingClientRect();
  let left = r.right - 184; if (left < 8) left = 8;
  m.style.left = left + 'px';
  m.style.top = (r.bottom + 6 + m.offsetHeight > window.innerHeight ? r.top - 6 - m.offsetHeight : r.bottom + 6) + 'px';
  m.querySelectorAll('button').forEach(b => b.onclick = ev => { ev.stopPropagation(); const bk = b.dataset.b; if (bk === 'remove') removeFav(i); else addFav(i, bk); closeFavMenu(); });
  setTimeout(() => document.addEventListener('click', function h() { closeFavMenu(); document.removeEventListener('click', h); }), 0);
}
function favSlotCard(i, bucket, pos, lastIdx) {
  const label = bucket === 'hope' ? (pos + 1) : '상' + (pos + 1);
  if (i == null) return `<div class="fav-slot empty"><span class="rank-badge ${bucket}">${label}</span><span class="fav-empty-t">비어 있음 — ${bucket === 'hope' ? '표의 ☆에서 지원희망으로 담기' : '상향으로 담기'}</span></div>`;
  const r = ROWS[i], v = V(r), d = deltaInfo(r);
  return `<div class="fav-slot" data-open="${i}"><span class="rank-badge ${bucket}">${label}</span>
    <div class="fav-body">
      <div class="fav-uni">${esc(r.uni)} <span class="muted">${esc(r.region)}</span></div>
      <div class="fav-dept">${esc(r.dept)}</div>
      <div class="fav-meta"><span class="jh-pill">${esc(r.jhtype.replace('학생부', ''))}</span> 모집 ${fmtInt(r.enroll)} <span class="delta ${d.cls}">${d.txt}</span>
        · 입결 <b>${fmt(r.g[0])}</b> · 경쟁 ${r.c[0] == null ? '–' : r.c[0].toFixed(1)}:1 <span class="impact-chip ${v.cls}">${v.label}</span></div>
      ${yoyHTML(r)}
    </div>
    <div class="fav-ctrl"><button data-up="${bucket}:${pos}" ${pos === 0 ? 'disabled' : ''} title="위로">▲</button><button data-dn="${bucket}:${pos}" ${pos === lastIdx ? 'disabled' : ''} title="아래로">▼</button>
      <button class="fav-sw" data-sw="${i}" title="${bucket === 'hope' ? '상향으로 이동' : '지원희망으로 이동'}">⇄</button><button class="fav-rm" data-rm="${i}" title="빼기">✕</button></div>
  </div>`;
}
function openFav() {
  const inner = $('#favInner');
  const mk = (bucket, n) => { const arr = S.fav[bucket], out = []; for (let k = 0; k < n; k++) out.push(favSlotCard(arr[k] ?? null, bucket, k, arr.length - 1)); return out.join(''); };
  inner.innerHTML = `<div class="drawer-head"><div><h3>🗂️ 내 지원카드 <span class="muted">${favCount()}/9</span></h3>
      <div class="muted" style="font-size:11.5px">담을 때 지원희망/상향을 선택하고, ▲▼ 순위변경 · ⇄ 칸 이동 · ✕ 빼기</div></div>
    <div style="display:flex;gap:8px">${favCount() ? '<button class="ghost-btn" id="favClear">전체 비우기</button>' : ''}<button class="modal-close" id="favClose">✕</button></div></div>
    <div class="fav-wrap">
      <div class="fav-group-label hope">🎯 지원희망 (수시 6장) <span class="muted">${S.fav.hope.length}/6</span></div>
      ${mk('hope', FAV_HOPE_MAX)}
      <div class="fav-group-label reach">🚀 상향·도전 (3장) <span class="muted">${S.fav.reach.length}/3</span></div>
      ${mk('reach', FAV_REACH_MAX)}
    </div>`;
  $('#favDrawer').classList.remove('hidden');
  $('#favClose').onclick = () => $('#favDrawer').classList.add('hidden');
  const clr = $('#favClear'); if (clr) clr.onclick = () => { if (confirm('지원카드를 모두 비울까요?')) { S.fav = { hope: [], reach: [] }; saveFav(); renderTable(); openFav(); } };
  inner.querySelectorAll('[data-up]').forEach(b => b.onclick = e => { e.stopPropagation(); const [bk, p] = b.dataset.up.split(':'); moveFav(bk, +p, -1); });
  inner.querySelectorAll('[data-dn]').forEach(b => b.onclick = e => { e.stopPropagation(); const [bk, p] = b.dataset.dn.split(':'); moveFav(bk, +p, 1); });
  inner.querySelectorAll('[data-sw]').forEach(b => b.onclick = e => { e.stopPropagation(); switchBucket(+b.dataset.sw); });
  inner.querySelectorAll('[data-rm]').forEach(b => b.onclick = e => { e.stopPropagation(); removeFav(+b.dataset.rm); });
  inner.querySelectorAll('[data-open]').forEach(c => c.onclick = e => { if (e.target.closest('button')) return; $('#favDrawer').classList.add('hidden'); openModal(+c.dataset.open); });
}
$('#favDrawer').onclick = e => { if (e.target.id === 'favDrawer') $('#favDrawer').classList.add('hidden'); };
$('#favBtn').onclick = openFav;

/* ----- topbar / theme / search / mobile ----- */
let searchT;
$('#search').oninput = e => { S.search = e.target.value; clearTimeout(searchT); searchT = setTimeout(() => renderAll(), 180); };
$('#resetBtn').onclick = () => {
  S.jhtypes.clear(); S.changes.clear(); S.region = ''; S.minLeast = ''; S.gradeMax = 9; S.search = ''; $('#search').value = '';
  renderFilters(); renderAll();
};
function applyTheme(t) { document.documentElement.dataset.theme = t; $('#themeBtn').textContent = t === 'dark' ? '☀️' : '🌙'; save('theme', t); }
$('#themeBtn').onclick = () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeFavMenu(); closeModal(); $('#compareDrawer').classList.add('hidden'); $('#favDrawer').classList.add('hidden'); closeSidebar(); } });

const scrim = el('div', 'scrim'); document.body.appendChild(scrim);
scrim.onclick = closeSidebar;
function openSidebar() { $('#sidebar').classList.add('open'); scrim.classList.add('show'); }
function closeSidebar() { $('#sidebar').classList.remove('open'); scrim.classList.remove('show'); }
$('#menuToggle').onclick = () => $('#sidebar').classList.contains('open') ? closeSidebar() : openSidebar();

/* ----- init ----- */
$('#sourceNote').innerHTML = `자료: ${esc(D.meta.source)}<br>전형 ${D.meta.nRows.toLocaleString()}건 · 대학 ${D.meta.nUni}곳`;
$('#footNote').innerHTML = `<b>이투스247학원</b> · 본 대시보드는 <b>${esc(D.meta.source)}</b> 자료를 가공한 참고용입니다. '올해 유불리 예상'과 '최저 변화'는 공개 데이터 기반 자동 분석 결과로 실제 입시 결과와 다를 수 있으니, 반드시 각 대학 모집요강을 확인하세요.`;
applyTheme(load('theme', 'light'));
updateCompareBtn(); updateFavBtn();
renderCatList(); renderFilters(); renderAll();
})();
