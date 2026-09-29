import json
from pathlib import Path
import httpx
out=Path(__file__).resolve().parent
state=json.loads((out/'production-state.json').read_text())
pid=state['project_id']
with httpx.Client(base_url='http://127.0.0.1:54159', trust_env=False, timeout=90) as c:
    c.headers['X-JDH-CSRF']=c.get('/api/session').json()['csrf']
    def call(method,path,**kwargs):
        r=c.request(method,'/api'+path,**kwargs);r.raise_for_status();return r.json()
    p=call('GET',f'/projects/{pid}')
    assert p['revision']==25, 'Stop if user edited the project during production'
    normalized={}
    for s in p['scenes']:
        existing=[a for a in p['assets'] if a['name']==f"{s['name']} - Kokoro leveled.wav"]
        if existing:
            assert len(existing)==1
            value={'asset':existing[0]}
        else:
            with (out/'audio-leveled'/f"{s['id']}.wav").open('rb') as f:
                value=call('POST',f'/projects/{pid}/media',files={'file':(f"{s['name']} - Kokoro leveled.wav",f,'audio/wav')})
        normalized[s['id']]=value['asset']['id']
        assert value['asset']['frames'] in {s['duration'],s['duration']+1}, 'ffprobe decimal rounding must be <= one frame'
    p=call('GET',f'/projects/{pid}')
    for s in p['scenes']:
        s['audio_id']=normalized[s['id']]
        s['audio_in']=0
        s['audio_text']=s['narration']
    p['narration_volume']=1.0
    p['reference_notes']+=' Narration loudness adjusted locally with FFmpeg loudnorm (-16 LUFS target, -1.5 dBTP ceiling), split at exact scene sample boundaries; original Kokoro takes retained in Media.'
    saved=call('PUT',f'/projects/{pid}',json=p)
    (out/'project-snapshot.json').write_text(json.dumps(saved,indent=2)+'\n')
    state['leveled_audio']=normalized
    (out/'production-state.json').write_text(json.dumps(state,indent=2)+'\n')
    print({'saved_revision':saved['revision'],'scenes':len(saved['scenes']),'seconds':sum(s['duration'] for s in saved['scenes'])/30,'preflight':call('GET',f'/projects/{pid}/preflight')})
