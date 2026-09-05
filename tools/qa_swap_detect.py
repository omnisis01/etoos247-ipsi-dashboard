# -*- coding: utf-8 -*-
# 상호교환 검출 — 같은 대학·같은 전형 블록에서 두 학과의 (등급,환산)이 서로 뒤바뀐 쌍을 찾는다. 읽기 전용.
#
# ⚠️ **검출은 판정이 아니다.** 잡힌 쌍을 보고 "어디가가 옳다"고 결론내지 마라 —
#   어디가 쪽 배열이 뒤바뀌어도 그림은 똑같다(청주대 국어/수학교육과 실측). data_corrections.json
#   의 _note_ipgyeol 참조: 이 논리로 넣었던 명지대 4·협성대 3·전주대 2건은 전부 철회됐다.
#   방향을 가르려면 **모집인원 스냅샷·경쟁률 산술 같은 제3근거**가 있어야 한다.
# ⚠️ 소수 인원 전형에서는 '3개년 추이가 매끄럽다'도 근거가 못 된다 —
#   모집 1명·등록 1명이면 그 해 값은 학생 한 명의 성적이라 연속성을 기대할 수 없다.
#   (2026-09-04 협성대 실내/산업디자인 재검토에서 실제로 이 함정에 걸렸다가 되돌렸다.)
#
# 훅에 넣지 않았다 — 접수 주간 동결 중이고, 판정 규칙 없이 경보만 울리면 해롭다. 9/12 이후 검토.
# 조건: ①같은 블록 ②A값이 B에·B값이 A에(상호) ③양쪽 경쟁률이 학과별로 일치.
import json, io, os, collections
H="/Users/omnibook/Downloads/ipsi_dashboard/2026 vs 2027/dashboard"
d=json.loads(io.open(os.path.join(H,'data.js'),encoding='utf-8').read()[len('window.IPSI = '):-1])
S,D=d['schema'],d['dicts']
A=json.load(io.open(os.path.join(H,'tools/adiga/adiga_raw.json'),encoding='utf-8'))
def v(r,k):
    x=r[S.index(k)]
    return D[k][x] if (k in D and isinstance(x,int)) else x
ad=collections.defaultdict(dict)          # (대학, 전형원문) -> 학과 -> (g,v,comp)
for k,cats in A.items():
    uni=k.split('[')[0]
    for cat,blocks in cats.items():
        for b in blocks:
            for row in b['rows']:
                if len(row)<11 or row[0]!='수시': continue
                try: g=float(row[9]); vv=float(row[7]); c=float(row[5])
                except: continue
                ad[(uni,b['jh'])][row[1]]=(g,vv,c)
mine=collections.defaultdict(dict)        # (대학, 우리전형) -> 학과 -> (g,v,comp)
for r in d['rows']:
    g,vv=v(r,'g26'),v(r,'v26')
    if g is None or vv is None: continue
    mine[(v(r,'uni'),v(r,'jhname'))][v(r,'dept')]=(g,vv,v(r,'c26'))
def blockmatch(jh_ours, jh_ad):
    a=jh_ours.replace('(외)','').replace('전형','').strip()
    return a and a in jh_ad
found=[]
for (uni,jh),mrows in mine.items():
    for (u2,jh2),arows in ad.items():
        if u2!=uni or not blockmatch(jh,jh2): continue
        common=[x for x in mrows if x in arows]
        if len(common)<2: continue
        for i,a1 in enumerate(common):
            for a2 in common[i+1:]:
                m1,m2=mrows[a1],mrows[a2]; d1,d2=arows[a1],arows[a2]
                swapped=(abs(m1[0]-d2[0])<0.005 and abs(m1[1]-d2[1])<0.05 and
                         abs(m2[0]-d1[0])<0.005 and abs(m2[1]-d1[1])<0.05 and
                         abs(m1[0]-m2[0])>0.005)
                if not swapped: continue
                cok=(m1[2] is not None and m2[2] is not None and
                     abs(m1[2]-d1[2])<0.02 and abs(m2[2]-d2[2])<0.02)
                found.append((uni,jh,a1,a2,m1,m2,d1,d2,cok))
        break
print('상호교환 검출 %d쌍 (경쟁률로 정렬 확인된 것 %d쌍)'%(len(found),sum(1 for f in found if f[8])))
for uni,jh,a1,a2,m1,m2,d1,d2,cok in found:
    print('\n%s [%s] %s'%(uni,jh,'✅경쟁률 정렬 확인' if cok else '⚠경쟁률 불일치'))
    print('   %-16s 우리 g=%-5s v=%-7s c=%-6s | 어디가 g=%-5s v=%-7s c=%-6s'%(a1[:16],m1[0],m1[1],m1[2],d1[0],d1[1],d1[2]))
    print('   %-16s 우리 g=%-5s v=%-7s c=%-6s | 어디가 g=%-5s v=%-7s c=%-6s'%(a2[:16],m2[0],m2[1],m2[2],d2[0],d2[1],d2[2]))
