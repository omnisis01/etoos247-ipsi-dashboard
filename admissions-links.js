// 대학별로 확인한 공식 입학처·모집요강 링크와 미확인 대학의 검색 경로를 제공합니다.
window.IPSI_ADMISSIONS = {
  checkedOn: '2026-09-07',
  universities: {
    '서울대학교': {
      admissions: 'https://admission.snu.ac.kr/index.html',
      guide: 'https://admission.snu.ac.kr/undergraduate/early/guide',
      source: 'https://admission.snu.ac.kr/index.html'
    },
    '고려대학교': {
      admissions: 'https://oku.korea.ac.kr/oku/index.do',
      guide: 'https://oku.korea.ac.kr/oku/cms/FR_CON/index.do?MENU_ID=680',
      source: 'https://oku.korea.ac.kr/oku/index.do'
    },
    '연세대학교': {
      admissions: 'https://admission.yonsei.ac.kr/seoul/admission/html/main/main.asp',
      guide: 'https://admission.yonsei.ac.kr/seoul/admission/html/rolling/guide.asp',
      source: 'https://admission.yonsei.ac.kr/seoul/admission/html/etc/sitemap.asp'
    },
    '한양대학교': {
      admissions: 'https://go.hanyang.ac.kr/main.do?m_type=SUSI',
      guide: 'https://go.hanyang.ac.kr/web/mojib/mojib.do?m_type=SUSI',
      source: 'https://go.hanyang.ac.kr/main.do?m_type=SUSI'
    },
    '경국대학교': {
      admissions: 'https://ipsi.gknu.ac.kr/',
      guide: 'https://ipsi.gknu.ac.kr/admission/sub.htm?nav_code=and1536915398',
      source: 'https://www.gknu.ac.kr/main/intro.do'
    }
  }
};

window.officialLinksHTML = function (r) {
  const uni = typeof r === 'string' ? r : r?.uni;
  if (!uni) return '';
  const escape = value => String(value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  const entry = window.IPSI_ADMISSIONS.universities[uni];
  const anchor = (url, label) => `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer" aria-label="${escape(uni)} ${escape(label)} · 새 창">${escape(label)} <span aria-hidden="true">↗</span></a>`;
  if (!entry) {
    const query = encodeURIComponent(`${uni} 2027 수시 공식 입학처 모집요강`);
    return `<div class="official-links"><b>지원 전 공식 확인</b><div class="official-link-actions">${anchor(`https://www.google.com/search?q=${query}`, '입학처 찾기 (검색 결과)')}</div>
      <small>공식 링크를 아직 확인하지 못했습니다. 검색 결과에서 대학 공식 홈페이지와 캠퍼스를 확인하세요. 새 창으로 열립니다.</small></div>`;
  }
  return `<div class="official-links"><b>지원 전 공식 확인</b><div class="official-link-actions">${anchor(entry.admissions, '공식 입학처')}${entry.guide ? anchor(entry.guide, '수시 모집요강') : ''}</div>
    <small>링크 확인 ${escape(window.IPSI_ADMISSIONS.checkedOn)} · 새 창으로 열립니다. 지원 자격·최저·고사일·접수 마감은 최신 공식 공지를 확인하세요.</small></div>`;
};
