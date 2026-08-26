#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math,shutil,sys
from pathlib import Path
import numpy as np, soundfile as sf
from fadr_client import FadrClient,FadrError

def click(bpm,duration,path,sr=44100):
    a=np.zeros(max(1,int(duration*sr)),dtype=np.float32); step=60/bpm
    t=np.arange(int(.025*sr))/sr
    for n in range(math.ceil(duration/step)):
        i=int(n*step*sr); tone=.7*np.sin(2*np.pi*(1600 if n%4==0 else 1050)*t)*np.exp(-90*t)
        end=min(len(a),i+len(tone)); a[i:end]+=tone[:end-i]
    sf.write(path,a,sr)

def duration(path):
    i=sf.info(str(path)); return i.frames/i.samplerate

def find_file(files,token):
    for f in files:
        if token in Path(f).stem.lower(): return Path(f)

def rpp_quote(p): return str(Path(p).resolve()).replace('\\','/').replace('"','\\"')
def track(name,file,length): return f'''  <TRACK\n    NAME "{name}"\n    <ITEM\n      POSITION 0\n      LENGTH {length:.6f}\n      <SOURCE WAVE\n        FILE "{rpp_quote(file)}"\n      >\n    >\n  >\n'''
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=Path);ap.add_argument('--title',required=True);ap.add_argument('--artist',default='');ap.add_argument('--out',required=True,type=Path);ap.add_argument('--bpm',type=float);ap.add_argument('--scene',type=int)
    a=ap.parse_args(); source=a.source.expanduser().resolve(); out=a.out.expanduser().resolve()
    if not source.is_file(): ap.error(f'--source does not exist: {source}')
    out.mkdir(parents=True,exist_ok=True); original=out/f'ORIGINAL{source.suffix.lower()}'; shutil.copy2(source,original)
    try: result=FadrClient().process(source,out/'fadr')
    except FadrError as e: print(f'ERROR: {e}',file=sys.stderr); return 2
    task=result['task']; text=json.dumps(task).lower(); bpm=a.bpm
    if not bpm:
        def scan(o):
            if isinstance(o,dict):
                for k,v in o.items():
                    if k.lower() in {'bpm','tempo'} and isinstance(v,(int,float)): return float(v)
                    q=scan(v)
                    if q:return q
            if isinstance(o,list):
                for v in o:
                    q=scan(v)
                    if q:return q
        bpm=scan(task)
    if not bpm or bpm<=0: print('ERROR: No valid BPM returned; pass --bpm.',file=sys.stderr); return 3
    dur=duration(source); click_path=out/'CLICK.wav'; click(bpm,dur,click_path)
    cues=out/'CUES.wav'; sf.write(cues,np.zeros(int(dur*44100),dtype=np.float32),44100)
    files=result['files']; mapping={'VOCALS':find_file(files,'vocal'),'DRUMS':find_file(files,'drum'),'BASS':find_file(files,'bass'),'MELODIES':find_file(files,'melod'),'INSTRUMENTAL':find_file(files,'instrument')}
    ordered=[('ORIGINAL',original),*mapping.items(),('CLICK',click_path),('CUES',cues)]
    content=f'<REAPER_PROJECT 0.1 "7.0" 0\n  TEMPO {bpm:.6f} 4 4\n'+''.join(track(n,p,dur) for n,p in ordered if p)+'>\n'
    rpp=out/f'{a.title}.RPP';rpp.write_text(content,encoding='utf-8')
    meta={'title':a.title,'artist':a.artist,'source':str(source),'bpm':bpm,'scene':a.scene,'rpp':str(rpp),'fadr_task_id':result['task_id'],'files':files};(out/'automation-result.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    if a.scene is not None:(out/'x32-scene-requirements.json').write_text(json.dumps({'song':a.title,'scene':a.scene},indent=2),encoding='utf-8')
    print(json.dumps(meta));return 0
if __name__=='__main__':raise SystemExit(main())
