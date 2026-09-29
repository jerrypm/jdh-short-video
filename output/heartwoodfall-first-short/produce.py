"""Create this user's Heartwoodfall short through JDH Studio's local API only."""
import json
import math
import os
from pathlib import Path
import sys
import time
import httpx

OUT=Path(__file__).resolve().parent
STATE=OUT/'production-state.json'
BASE=os.environ.get('JDH_STUDIO_URL', 'http://127.0.0.1:54159')
PLAN=json.loads((OUT/'scene-plan.json').read_text())

def checkpoint(value):
    STATE.write_text(json.dumps(value,indent=2)+'\n')

def main(mode):
    state=json.loads(STATE.read_text()) if STATE.exists() else {}
    with httpx.Client(base_url=BASE,trust_env=False,timeout=180) as client:
        client.headers['X-JDH-CSRF']=client.get('/api/session').json()['csrf']
        def call(method,path,**kwargs):
            r=client.request(method,'/api'+path,**kwargs)
            if r.status_code != 200:
                raise RuntimeError(f'{method} {path}: {r.status_code}: {r.text[:1000]}')
            return r.json()
        def load(): return call('GET',f"/projects/{state['project_id']}")
        def save(p): return call('PUT',f"/projects/{p['id']}",json=p)
        def wait(job):
            started=time.monotonic()
            last=None
            while True:
                current=call('GET',f"/jobs/{job['id']}")
                marker=(current['status'],current['message'])
                if marker != last:
                    print(json.dumps({'job':job['id'],'status':current['status'],'message':current['message'],'progress':current['progress']}),flush=True)
                    last=marker
                if current['status']=='completed': return current
                if current['status'] in {'failed','cancelled'}: raise RuntimeError(current)
                if time.monotonic()-started>900: raise RuntimeError('Job timeout; project retained for continuation')
                time.sleep(.75)
        if not state:
            p=call('POST','/projects',json={'name':'01 - Heartwoodfall: Three.js to Godot','language':'en','target':45,'script':'\n\n'.join(s['narration'] for s in PLAN),'reference':'Jerry PM - Heartwoodfall part III: Combine Two Tools (Medium PDF supplied by author)'})
            state={'project_id':p['id'],'visuals':{},'voice':'am_michael','speed':0.96,'tts_jobs':{}}
            checkpoint(state)
            print('Created project '+p['id'],flush=True)
        if mode=='prepare':
            for row in PLAN:
                relative=row['file']
                if relative in state['visuals']: continue
                with (OUT/relative).open('rb') as f:
                    value=call('POST',f"/projects/{state['project_id']}/media",files={'file':(Path(relative).name,f,'image/png')})
                state['visuals'][relative]=value['asset']['id']; checkpoint(state)
            p=load()
            if not p['scenes']:
                p['scenes']=[{'id':row['id'],'name':row['name'],'narration':row['narration'],'caption':row['caption'],'duration':60,'media_id':state['visuals'][row['file']], 'fit':row['fit'], 'motion':{'version':1,'visual':{'preset':row['motion'],'amount':0.035,'focus_x':0.5,'focus_y':0.45},'caption':{'preset':'fade','end_frame':5},'callout':{'text':row['callout'],'x':144,'y':280,'width':792,'size':42,'target_x':540,'target_y':830,'entrance':{'preset':'slide_up','end_frame':10}} if row['callout'] else None}} for row in PLAN]
                p['caption_style']={'preset':'bar','size':44,'position':78,'enabled':True}
                p['narration_volume']=0.92
                p['music_volume']=0
                p['reference_notes']='Based on the author-supplied Medium PDF, pp. 2, 5–7. First-person wording reflects Jerry PM’s article. Asset reuse remains a possibility, not a completed migration. Visuals: original PDF images (cover p.1 and Godot editor p.6) plus original typography cards. Script edited by the assistant; voice generated with local Kokoro am_michael, not Gemini Nano or a voice clone. Native motion/captions/render by JDH Shorts Studio. No live gameplay footage is claimed.'
                p['upload']={'title':'Moving My Game from Three.js to Godot | Heartwoodfall Devlog', 'description':"I'm rebuilding Heartwoodfall in Godot while keeping the original Three.js project as a reference. Claude helped with character movement; the old design still guides the next build. Some 3D assets may be reusable, but that still needs to be tested.\n\nBased on my Medium article: Heartwoodfall part III: Combine Two Tools.\nMore devlogs: https://medium.com/@21zerixpm\n\nArticle screenshots and animated typography; not live gameplay footage. English narration made with local Kokoro. Edited and rendered locally in JDH Shorts Studio.\n\n#Godot #GameDev #Devlog #Threejs #Claude"}
                p=save(p)
            for row in PLAN:
                p=load(); s=next(s for s in p['scenes'] if s['id']==row['id'])
                if s['audio_id']: continue
                job=call('POST',f"/projects/{p['id']}/tts",json={'scene_id':s['id'],'voice':state['voice'],'speed':state['speed']})
                state['tts_jobs'][s['id']]=job['id']; checkpoint(state)
                value=wait(job)
                response=client.get(f"/api/jobs/{job['id']}/files/narration.wav"); response.raise_for_status()
                (OUT/'audio').mkdir(exist_ok=True)
                (OUT/'audio'/f"{s['id']}.wav").write_bytes(response.content)
                p=load()
                call('POST',f"/projects/{p['id']}/tts/{job['id']}/apply",json={'revision':p['revision']})
                print(json.dumps({'scene':s['name'],'audio_seconds':round(value['result']['frames']/30,2)}),flush=True)
            p=load()
            for s in p['scenes']:
                a=next(a for a in p['assets'] if a['id']==s['audio_id'])
                s['duration']=max(a['frames']+7,60,math.ceil(len(s['caption'].replace('\n',' '))*30/19))
                if s['id']=='heartwood-11': s['duration']+=15
            p=save(p)
            state['frames']=sum(s['duration'] for s in p['scenes']); checkpoint(state)
            (OUT/'project-snapshot.json').write_text(json.dumps(p,indent=2)+'\n')
            print(json.dumps({'project_id':p['id'],'seconds':state['frames']/30,'revision':p['revision'],'preflight':call('GET',f"/projects/{p['id']}/preflight")}),flush=True)
        elif mode in {'draft','final'}:
            p=load()
            checked=wait(call('POST',f"/quality/{p['id']}/checks",json={'revision':p['revision'],'preset':mode}))
            (OUT/f'quality-{mode}-before.json').write_text(json.dumps(checked['result'],indent=2)+'\n')
            print(json.dumps({'quality_findings':checked['result']['findings']}),flush=True)
            job=call('POST',f"/projects/{p['id']}/render",json={'preset':mode,'check_id':checked['id']})
            state[mode+'_job']=job['id'];checkpoint(state)
            result=wait(job)
            downloads=OUT/('draft' if mode=='draft' else 'final')
            downloads.mkdir(exist_ok=True)
            for name in result['files']:
                r=client.get(f"/api/jobs/{job['id']}/files/{name}");r.raise_for_status()
                (downloads/name).write_bytes(r.content)
            (OUT/f'{mode}-verification.json').write_text(json.dumps(result['result'],indent=2)+'\n')
            print(json.dumps({'downloaded_to':str(downloads),'verification':result['result']}),flush=True)

if __name__=='__main__': main(sys.argv[1])
