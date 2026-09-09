/* 졸업생(N수생) 학생부 교과 반영 학기 범위 — 대학 공식 2027 수시모집요강 원문에서 수집.
   ⚠️ 원천 엑셀에 없는 항목이라 손으로 요강을 읽어 넣는다. 근거 URL·원문 인용을 반드시 남긴다.
   ⚠️ **추측 금지.** 확인 못 한 대학은 아예 넣지 않는다 — 빈칸이 오답보다 낫다.
        학생이 자기 내신 등급을 잘못 계산하게 되는 정보다.
   ⚠️ 목포대는 입학처가 요강을 '학사구조개편으로 미확정·참고용'이라 고지해 **일부러 뺐다.**
   conf(근거 강도) — stated  : 요강이 졸업생/재학생을 명시적으로 구분함
                     inferred: 구분 조항이 없어 단일 규정이 졸업생에도 적용된다고 본 것
                     na      : 그 대학 교과전형에 졸업생이 지원할 수 없음(또는 교과전형 자체가 없음)
   ⚠️ JSON 호환 문법을 유지할 것 — qa_record_scope.py 가 파이썬으로 파싱한다.
   점검: python3 qa_record_scope.py */
window.IPSI_RECORD_SCOPE = {
 "checkedOn": "2026-09-09",
 "universities": {
  "서울대학교": {
   "conf": "na",
   "graduate": "",
   "note": "학생부교과전형 자체가 없습니다(학생부종합만 선발).",
   "quote": "요강 전문에 '학생부교과' 0건",
   "source": "https://admission.snu.ac.kr/webdata/admission/files/2027susi.pdf"
  },
  "연세대학교": {
   "conf": "na",
   "graduate": "",
   "note": "학생부교과(추천형)은 졸업예정자만 지원할 수 있습니다.",
   "quote": "국내 고등학교 3학년 재학생으로 2027년 2월 졸업 예정",
   "source": "https://admission.yonsei.ac.kr/seoul/upload/guide/20260529204109T8NZNJ.PDF"
  },
  "고려대학교": {
   "conf": "na",
   "graduate": "",
   "note": "학생부교과(학교추천)은 졸업예정자만 지원할 수 있습니다.",
   "quote": "국내 고등학교 졸업예정자 중 학생부에 5학기 교과 성적이 기재",
   "source": "https://oku.korea.ac.kr/oku/index.do"
  },
  "서강대학교": {
   "conf": "inferred",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "note": "재학생·졸업생을 나누는 조항이 없습니다.",
   "quote": "전 학년 통합 반영, 가중치 없음(3학년 1학기까지 반영함)",
   "source": "https://admission.sogang.ac.kr/upload/GUIDES/20260609163807KP38K2.pdf"
  },
  "성균관대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "quote": "3학년 2학기 교과성적은 반영하지 않음",
   "source": "https://admission.skku.edu/upload/guide/20260813104526BBPE44.pdf"
  },
  "한양대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 2학기까지",
   "quote": "반영학기 : 졸업예정자는 3학년 1학기, 졸업자는 3학년 2학기까지 반영",
   "source": "https://go.hanyang.ac.kr/web/mojib/mojib.do?m_type=SUSI"
  },
  "중앙대학교": {
   "conf": "inferred",
   "current": "3학년 1학기까지",
   "graduate": "3학년 2학기까지",
   "note": "요강은 '최종 이수학기'라고만 적습니다 — 졸업생은 3학년 2학기가 됩니다.",
   "quote": "원서접수 당시 이수한 최종 학년의 최종 이수학기까지 반영",
   "source": "https://admission.cau.ac.kr/"
  },
  "경희대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "전 학년(3학년 2학기 포함)",
   "quote": "졸업자 : 전학년 / 졸업예정자 : 3학년 1학기",
   "source": "https://iphak.khu.ac.kr/"
  },
  "한국외국어대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "quote": "3학년 1학기까지 (졸업자와 졸업예정자 동일)",
   "source": "https://adms.hufs.ac.kr/cms/FrCon/index.do?MENU_ID=650"
  },
  "서울시립대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 2학기까지",
   "quote": "졸업예정자의 경우 3학년 1학기까지만 반영하며, 졸업생의 경우 3학년 1·2학기를 모두 반영",
   "source": "https://enter.uos.ac.kr/"
  },
  "이화여자대학교": {
   "conf": "inferred",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "note": "구분 조항이 없고 요강에 '3학년 2학기'가 한 번도 나오지 않습니다.",
   "quote": "3학년 1학기까지(학년별/학기별 가중치 없음)",
   "source": "https://admission.ewha.ac.kr/upload/GUIDES/20260907134642BHLTER.pdf"
  },
  "건국대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 2학기까지",
   "quote": "반영학기: (졸업예정자) 3학년 1학기까지, (졸업자) 3학년 2학기까지",
   "source": "https://enter.konkuk.ac.kr/"
  },
  "동국대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "전 학년(3학년 2학기 포함)",
   "quote": "졸업예정자는 3학년 1학기까지, 졸업자는 전(全)학년을 대상으로 반영",
   "source": "https://ipsi.dongguk.edu/upload/file/20260601115911UVEHWG.PDF"
  },
  "홍익대학교": {
   "conf": "inferred",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "note": "구분 조항이 없고 요강에 '3학년 2학기'가 한 번도 나오지 않습니다.",
   "quote": "반영학기 1학년 1학기 ~ 3학년 1학기",
   "source": "https://www.hongik.ac.kr/kr/admission/recruitment.do"
  },
  "숙명여자대학교": {
   "conf": "stated",
   "current": "전 학기",
   "graduate": "3학년 2학기까지",
   "quote": "국내 고교 재학 기간 중 이수한 전(全)학기의 지정 교과목을 반영",
   "source": "https://admission.sookmyung.ac.kr/upload/info/20260907095635ZSM2KM.PDF"
  },
  "원광대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "note": "⚠️ 출결(비교과)만 졸업생 3학년 2학기까지 반영합니다 — 교과는 3학년 1학기까지입니다.",
   "quote": "3학년 2학기를 제외한 전 학년 반영 교과(군) 해당",
   "source": "https://ipsi.wku.ac.kr/"
  },
  "가톨릭대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "note": "요강이 '졸업(예정)자' 하나로만 규정합니다.",
   "quote": "졸업(예정)자: 3학년 1학기까지 성적 반영",
   "source": "https://ipsi.catholic.ac.kr/"
  },
  "대전대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 2학기까지",
   "quote": "재학생은 3학년 1학기까지의 성적, 졸업생은 3학년 2학기까지의 성적을 반영합니다",
   "source": "https://ipsi.dju.ac.kr/upload/GUIDES/20260904140222001.pdf"
  },
  "단국대학교(천안)": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 2학기까지",
   "quote": "재학생 : 3학년 1학기까지 / 졸업생 : 3학년 2학기까지",
   "source": "https://ipsi.dankook.ac.kr/cheonan/main.html"
  },
  "건양대학교": {
   "conf": "inferred",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "note": "재학생·졸업생을 나누는 조항이 없습니다.",
   "quote": "전 학년 공통반영 100% (3학년 1학기까지)",
   "source": "https://ipsi.konyang.ac.kr/"
  },
  "상지대학교": {
   "conf": "inferred",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "note": "구분 조항이 없고 요강에 '3학년 2학기'가 한 번도 나오지 않습니다.",
   "quote": "반영 학기 : 1학년 1학기 ~ 3학년 1학기(5개 학기)",
   "source": "https://www.sangji.ac.kr/thumbnail/pdf/CMS_202608200201260141.pdf"
  },
  "세명대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "quote": "3학년 1학기까지 반영 (졸업자 동일 적용)",
   "source": "https://ipsi.semyung.ac.kr/"
  },
  "순천대학교": {
   "conf": "inferred",
   "current": "3학년 1학기까지",
   "graduate": "3학년 2학기까지",
   "note": "요강은 졸업예정자만 3학년 1학기로 제한하고, 기본 반영비율은 1~3학년 100%입니다.",
   "quote": "2027. 2월 졸업예정자는 3학년 1학기까지 반영",
   "source": "https://www.scnu.ac.kr/upload/html/themes/iphak/download/2027susi_0617.pdf"
  },
  "부산대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 2학기까지",
   "note": "학생부교과의 학업역량평가(20%)는 졸업생도 3학년 1학기까지만 봅니다.",
   "quote": "졸업예정자는 3학년 1학기까지, 졸업자는 3학년 2학기까지",
   "source": "https://go.pusan.ac.kr/_common/new_download_file.asp?menu=boardfile&file_no=4404"
  },
  "경성대학교": {
   "conf": "stated",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "note": "⚠️ 학생부종합전형은 졸업생만 3학년 2학기까지 반영합니다 — 교과전형과 다릅니다.",
   "quote": "학생부교과전형 실기전형 … 재학생/졸업생 … 5학기(1학년 1학기 ~ 3학년 1학기)",
   "source": "https://kscms.ks.ac.kr/ipsi/CMS/Contents/Contents.do?mCode=MN025"
  },
  "동의대학교": {
   "conf": "inferred",
   "current": "3학년 1학기까지",
   "graduate": "3학년 1학기까지",
   "note": "졸업생 별도 행이나 예외 문구가 요강에 없습니다.",
   "quote": "반영학기 | 1학년 1학기 ~ 3학년 1학기",
   "source": "https://ipsi.deu.ac.kr/submenu.do?menuord=1"
  }
 }
};
