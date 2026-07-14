# -*- coding: utf-8 -*-
# cores.py — 主題核の抽出(文書10仕様の完全実装) 2026-07-14
# 使い方: 厳選19曲の.midがあるフォルダに置いて  pip install mido && python3 cores.py
# 出力: cores/core_XX_*.mid(耳検品用19本) + core_cards.json + report.txt
import os, json, statistics as stt
from collections import Counter
try:
    import mido
    from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo
except ImportError:
    raise SystemExit("pip install mido を先に実行してくれ")

FOLDER='.'
ELITE=[('mononoke',['mononoke']),('summer',['summer']),('dragonboy',['dragon']),
 ('sixthstation',['sixth']),('howl',['merry']),('family',['shigure']),
 ('thread',['thread']),('prometheus',['prometheus']),('wipeout',['wipe']),
 ('lightdarkness',['light','darkness']),('liberation',['liberation']),('ballade',['ballade']),
 ('angel',['angel']),('andalone',['alone']),('thankyou',['thank']),
 ('kaze',['kaze']),('fantasia',['fantasia']),('presence3',['presence']),('hoshi',['星の消滅'])]
CONSTN={0,3,5,7,10}; MEI={4,9,11}; YAMI={1,8}

def load(fn):
    m=MidiFile(fn); t=0.0; act={}; N=[]
    for msg in m:
        t+=msg.time
        if msg.type=='note_on' and msg.velocity>0: act.setdefault(msg.note,[]).append((t,msg.velocity))
        elif msg.type=='note_off' or (msg.type=='note_on' and msg.velocity==0):
            if act.get(msg.note): t0,v=act[msg.note].pop(0); N.append((t0,msg.note,v,t-t0))
    N.sort(); return N

def melody(N):
    mel=[]
    for t0,m2,v,d in N:
        if m2<60: continue
        if mel and t0-mel[-1][0]<=0.04:
            if m2>mel[-1][1]: mel[-1]=(t0,m2,d)
        else: mel.append((t0,m2,d))
    return mel

def circ(a,b): return min((a-b)%12,(b-a)%12)

def align(ref,occ):
    n,m=len(ref),len(occ)
    D=[[0.0]*(m+1) for _ in range(n+1)]
    for i in range(1,n+1): D[i][0]=i*1.5
    for j in range(1,m+1): D[0][j]=j*1.5
    for i in range(1,n+1):
        for j in range(1,m+1):
            cd=circ(ref[i-1][0],occ[j-1][0])/2+(0.5 if ref[i-1][1]!=occ[j-1][1] else 0)
            D[i][j]=min(D[i-1][j-1]+cd,D[i-1][j]+1.5,D[i][j-1]+1.5)
    i,j=n,m; mp={}
    while i>0 and j>0:
        cd=circ(ref[i-1][0],occ[j-1][0])/2+(0.5 if ref[i-1][1]!=occ[j-1][1] else 0)
        if abs(D[i][j]-(D[i-1][j-1]+cd))<1e-9: mp[i-1]=j-1; i-=1; j-=1
        elif abs(D[i][j]-(D[i-1][j]+1.5))<1e-9: i-=1
        else: j-=1
    return mp

def write_core_midi(path,kernel,supdeg,bpm=80):
    mf=MidiFile(ticks_per_beat=480); tr=MidiTrack(); mf.tracks.append(tr)
    tr.append(MetaMessage('set_tempo',tempo=bpm2tempo(bpm),time=0))
    DUR={'s':240,'e':480,'l':960}
    ev=[]; t=0
    for rep in range(2):
        stlen=sum(DUR[dc] for _,dc in kernel)
        ev.append((t,t+stlen,36+supdeg,42))
        tt=t
        for deg,dc in kernel:
            ev.append((tt,tt+int(DUR[dc]*0.95),60+deg,66)); tt+=DUR[dc]
        t+=stlen+960
    msgs=[]
    for on,off,n2,v in ev: msgs+=[(on,1,n2,v),(off,0,n2,0)]
    msgs.sort(key=lambda x:(x[0],x[1]))
    last=0
    for tk,kind,n2,v in msgs:
        tr.append(Message('note_on' if kind else 'note_off',note=n2,velocity=v,time=tk-last)); last=tk
    mf.save(path)

files=[f for f in os.listdir(FOLDER) if f.lower().endswith('.mid')]
os.makedirs('cores',exist_ok=True)
cards=[]; lines=[]
for num,(tag,keys) in enumerate(ELITE,1):
    fn=next((f for f in files if all(k in f.lower() or k in f for k in keys)),None)
    if not fn: lines.append(f"[{tag}] ファイル未発見(keys={keys})"); continue
    try:
        N=load(os.path.join(FOLDER,fn))
        pcd=Counter()
        for t0,m2,v,d in N: pcd[m2%12]+=d
        root=pcd.most_common(1)[0][0]
        mel=melody(N)
        if len(mel)<40: lines.append(f"[{tag}] 旋律薄"); continue
        med=stt.median(q[2] for q in mel)
        DEG=[(q[1]-root)%12 for q in mel]
        DC=['l' if q[2]>med*1.4 else ('s' if q[2]<med*0.7 else 'e') for q in mel]
        # STEP1: 最頻6音窓(移置不変)
        iv=[None if mel[i][0]-mel[i-1][0]>1.8 else mel[i][1]-mel[i-1][1] for i in range(1,len(mel))]
        wins={}
        for i in range(len(iv)-5):
            w=iv[i:i+6]
            if None in w or all(x==0 for x in w): continue
            wins.setdefault(tuple(w),[]).append(i)
        if not wins: lines.append(f"[{tag}] 窓なし"); continue
        tw,occI=max(wins.items(),key=lambda kv:len(kv[1]))
        occ2=[occI[0]]
        for i in occI[1:]:
            if mel[i][0]-mel[occ2[-1]][0]>4: occ2.append(i)
        # 句境界まで拡張(上限16音)
        def expand(i):
            a=b=i
            while a>0 and mel[a][0]-(mel[a-1][0]+min(mel[a-1][2],1.5))<=0.5 and b-a<15: a-=1
            while b<len(mel)-1 and mel[b+1][0]-(mel[b][0]+min(mel[b][2],1.5))<=0.5 and b-a<15: b+=1
            return a,b+1
        occs=[]
        for i in occ2:
            a,b=expand(i)
            occs.append([(DEG[k],DC[k]) for k in range(a,b)])
        occs.sort(key=len,reverse=True)
        ref=occs[0]
        # STEP2: 整列→不変量
        posDeg=[Counter() for _ in ref]; posDC=[Counter() for _ in ref]
        for p,(dg,dc) in enumerate(ref): posDeg[p][dg]+=1; posDC[p][dc]+=1
        for occ in occs[1:]:
            mp=align(ref,occ)
            for p,q in mp.items(): posDeg[p][occ[q][0]]+=1; posDC[p][occ[q][1]]+=1
        nOcc=len(occs)
        inv=[posDeg[p].most_common(1)[0][1]/nOcc>=0.7 for p in range(len(ref))]
        # 最長不変連続区間(≥4·なければ0.5へ緩和)
        def bestrun(flags):
            bi,bl,ci,cl=0,0,0,0
            for k,f in enumerate(flags):
                if f: cl+=1
                else:
                    if cl>bl: bi,bl=ci,cl
                    ci,cl=k+1,0
            if cl>bl: bi,bl=ci,cl
            return bi,bl
        bi,bl=bestrun(inv)
        relax=False
        if bl<4:
            inv=[posDeg[p].most_common(1)[0][1]/nOcc>=0.5 for p in range(len(ref))]
            bi,bl=bestrun(inv); relax=True
        if bl<4: lines.append(f"[{tag}] 核不成立(最長不変{bl})"); continue
        kernel=[(posDeg[p].most_common(1)[0][0],posDC[p].most_common(1)[0][0]) for p in range(bi,bi+bl)]
        yohaku=[{ 'pos':p-bi,'deg':dict(posDeg[p]),'dc':dict(posDC[p])} for p in range(bi,bi+bl) if posDeg[p].most_common(1)[0][1]/nOcc<0.9]
        # STEP3: 保持音+実績サポート低音
        hpos=max(range(len(kernel)),key=lambda k:{'s':0,'e':1,'l':2}[kernel[k][1]])
        lows=[(t0,m2,d) for t0,m2,v,d in N if m2<52]
        supC=Counter()
        for i in occ2:
            a,b=expand(i)
            k=a+bi+hpos
            if k>=len(mel): continue
            t0=mel[k][0]
            bs=[lm for lt,lm,ld in lows if lt<=t0<lt+ld]
            if bs: supC[(min(bs)-root)%12]+=1
        # 心座標v2·色族·振り子
        dur=max(t0+d for t0,m2,v,d in N); tot=sum(d for _,_,d in mel)
        cs=lambda c:sum(d for _,m2,d in mel if (m2-root)%12==c)/tot
        S2=[]
        for t0,m2,d in lows:
            pc=(m2-root)%12
            if S2 and S2[-1]==pc: continue
            S2.append(pc)
        warm=sum(1 for x in S2 if x in(3,10))/max(1,len(S2)); dark=sum(1 for x in S2 if x in(1,8))/max(1,len(S2))
        v2=cs(4)*3+warm-dark
        ugoki=len(mel)/dur/6+len(S2)/dur*60/30
        ten=(stt.mean(q[1] for q in mel)-66)/12
        mei=sum(cs(c) for c in MEI); yami=sum(cs(c) for c in YAMI)
        fam='明' if mei>yami*1.5 else ('闇' if yami>mei*1.5 else '混淆')
        best=None
        for L in(2,3,4,5):
            w=Counter(tuple(S2[i:i+L]) for i in range(len(S2)-L))
            if not w: continue
            pat,c=w.most_common(1)[0]
            cov=c*L/len(S2)
            if best is None or cov>best[1]: best=(pat,cov)
        vocab=len(set(k[0] for k in kernel))
        loom=sum(1 for k in range(len(kernel)-2) if kernel[k][0]==0 and kernel[k+2][0]==0 and kernel[k+1][0]!=0)/max(1,len(kernel)-2)
        card={'num':num,'tag':tag,'file':fn,'出現':nOcc,'緩和':relax,
          '骨':[k[0] for k in kernel],'息':[k[1] for k in kernel],
          '保持音':{'座席':hpos,'度数':kernel[hpos][0],'実績低音':dict(supC.most_common(4))},
          '織機率':round(loom,2),'語彙':vocab,'心座標v2':{'光翳':round(v2,2),'静動':round(ugoki,2),'天地':round(ten,2)},
          '色族':fam,'固有振り子':list(best[0]) if best else [],'変容余白':yohaku}
        cards.append(card)
        sup=supC.most_common(1)[0][0] if supC else 0
        write_core_midi(f"cores/core_{num:02d}_{tag}.mid",kernel,sup)
        lines.append(f"[{num:02d} {tag}] 核ST{[k[0] for k in kernel]} 息{''.join(k[1] for k in kernel)} 出現{nOcc} 語彙{vocab} 保持音ST{kernel[hpos][0]}@{hpos} 低音{dict(supC.most_common(2))} {fam} v2={v2:+.2f}"+(" (緩和)" if relax else ""))
    except Exception as e:
        lines.append(f"[{tag}] ERROR: {e}")
# STEP6: 検証
fant=[c for c in cards if c['tag']=='fantasia']
if fant:
    ok=set(fant[0]['骨'])<={0,5,7,3,10}
    lines.append(f"[検証] Fantasia核が憲法内({sorted(set(fant[0]['骨']))}): {'PASS' if ok else 'FAIL — 既知の正解[0,5,7]系と照合せよ'}")
lines.append(f"[検証] 核カード{len(cards)}/19枚·MIDI{len([f for f in os.listdir('cores') if f.endswith('.mid')])}本")
json.dump(cards,open('core_cards.json','w'),ensure_ascii=False,indent=1)
open('report.txt','w').write('\n'.join(lines))
print('\n'.join(lines))
print('\n完了: core_cards.json + report.txt + cores/*.mid')
