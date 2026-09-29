"""Original vector title cards for the JDH video. Source screenshots stay untouched."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
VIS = OUT / 'visuals'
VIS.mkdir(exist_ok=True)
FONT = ROOT / 'assets/fonts/IBMPlexSans-Bold.ttf'
BG = '#101c1a'
CREAM = '#f0f0df'
GREEN = '#c8f56a'
MUTED = '#94aca3'

def font(size, weight=700):
    f = ImageFont.truetype(str(FONT), size)
    f.set_variation_by_axes([weight, 100])
    return f

def text(d, xy, value, size, color=CREAM, weight=700):
    d.text(xy, value, font=font(size, weight), fill=color, anchor='lt')

def card(number, label):
    im = Image.new('RGB', (1080,1920), BG)
    d=ImageDraw.Draw(im)
    for x in range(80,1080,100):
        d.line((x,430,x,1340), fill='#192b26', width=1)
    for y in range(440,1350,100):
        d.line((80,y,1000,y),fill='#192b26',width=1)
    d.line((84,172,995,172),fill='#375247',width=2)
    text(d,(84,128),'HEARTWOODFALL',29,GREEN)
    text(d,(790,128),'DEVLOG III',27,MUTED)
    text(d,(84,245),label.upper(),30,MUTED)
    d.line((84,1350,995,1350),fill='#375247',width=2)
    text(d,(84,1276),f'{number:02d} / 11',28,MUTED)
    text(d,(770,1276),'JERRY PM',28,MUTED)
    return im,d

def save(im,name):
    path=VIS/name
    im.save(path)
    return str(path)

im,d=card(2,'The question')
text(d,(80,420),'NEW ENGINE.',102)
text(d,(80,540),'START OVER?',99,GREEN)
for x,label in [(86,'THREE.JS'),(603,'GODOT')]:
    d.rounded_rectangle((x,820,x+395,1055),radius=24,fill='#20352e',outline='#486254',width=2)
    text(d,(x+44,905),label,52)
d.line((500,938,572,938),fill=GREEN,width=8)
d.polygon([(578,938),(554,921),(554,955)], fill=GREEN)
save(im,'02-question.png')

im,d=card(3,'The answer')
text(d,(84,410),'THE CODE?',100)
text(d,(84,525),'REBUILD.',112,GREEN)
text(d,(84,835),'THE WHOLE IDEA?',65)
text(d,(84,930),'KEEP WHAT WORKS.',62)
save(im,'03-answer.png')

im,d=card(4,'Where it started')
text(d,(84,400),'FIRST BUILD',78)
text(d,(84,510),'THREE.JS',135,GREEN)
for row,label in enumerate(['A game world','A visual direction','A starting point']):
    y=820+row*105
    d.ellipse((91,y+12,113,y+34),fill=GREEN)
    text(d,(145,y),label,43)
save(im,'04-origin.png')

im,d=card(8,'What may carry over')
d.rounded_rectangle((90,395,975,735),radius=30,fill='#243b30',outline='#486254',width=2)
text(d,(150,445),'.GLB',158,GREEN)
text(d,(151,640),'3D MODEL ASSETS',38)
text(d,(84,835),'POTENTIAL REUSE',64)
text(d,(84,950),'Same assets.',58)
text(d,(84,1022),'New foundation.',58)
text(d,(84,1170),'Import still needs to be tested.',31,MUTED)
save(im,'08-assets.png')

im,d=card(9,'The takeaway')
text(d,(84,410),'REBUILD THE',85)
text(d,(84,510),'FOUNDATION.',93,GREEN)
for row in range(3):
    y=805+row*105
    for col in range(3):
        x=94+col*293+(38 if row%2 else 0)
        d.rounded_rectangle((x,y,x+255,y+74),radius=9,fill=['#2d493b','#456951','#78a16d'][row])
save(im,'09-foundation.png')

im,d=card(10,'Keep the useful work')
text(d,(84,410),'KEEP THE',98)
text(d,(84,530),'GOOD IDEAS.',103,GREEN)
for row,label in enumerate(['Characters','Environments','Interface & visual direction']):
    y=845+row*107
    d.line((95,y+22,111,y+39,139,y),fill=GREEN,width=7)
    text(d,(176,y),label,44)
save(im,'10-keep.png')

im,d=card(11,'The next build')
text(d,(84,410),'SUBSCRIBE',104)
text(d,(84,535),'FOR MORE',93,GREEN)
text(d,(84,642),'CONTENT.',93,GREEN)
text(d,(84,845),'HEARTWOODFALL',65)
text(d,(84,941),'Building in Godot.',46)
d.rounded_rectangle((84,1085,850,1190),radius=12,fill=GREEN)
text(d,(120,1112),'Subscribe for more content',38,BG)
save(im,'11-subscribe.png')

scenes = [
    ('Hook', "I'm moving my game from Three.js to Godot.", 'source/image-011.png','fill','zoom_in', 'THREE.JS  >  GODOT'),
    ('The question', 'Does that mean starting over?', 'visuals/02-question.png','fill','zoom_in',None),
    ('The answer', 'For the code, yes. For the whole project? No.', 'visuals/03-answer.png','fill','zoom_out',None),
    ('The original', 'Heartwoodfall started as a Three.js project.', 'visuals/04-origin.png','fill','pan_right',None),
    ('Claude', 'Claude helped me fix the character movement.', 'source/image-002.png','fit','zoom_in','FIXING CHARACTER MOVEMENT'),
    ('Godot rebuild', "Now I'm rebuilding in Godot.", 'source/image-011.png','fit','zoom_in','REBUILDING IN GODOT'),
    ('Use as reference', 'The original still guides the characters, environments, and interface.', 'source/image-011.png','fill','pan_right','SAME VISUAL DIRECTION'),
    ('Reusable assets', 'Some assets may carry over, including my three-D models.', 'visuals/08-assets.png','fill','zoom_in',None),
    ('Foundation', 'A new engine means rebuilding the foundation,', 'visuals/09-foundation.png','fill','zoom_out',None),
    ('Keep the work', 'not throwing away every useful idea.', 'visuals/10-keep.png','fill','zoom_in',None),
    ('Subscribe', 'Subscribe for more content.', 'visuals/11-subscribe.png','fill','zoom_out',None),
]
plan=[]
from backend.captions import layout
from backend.models import CaptionStyle
style=CaptionStyle(preset='bar',size=44,position=78)
for n,(name,narration,file,fit,motion,callout) in enumerate(scenes,1):
    caption = narration.replace('three-D','3D')
    checked = layout(caption,style)
    assert not checked['errors'], (name,checked)
    plan.append(dict(id=f'heartwood-{n:02}', name=name,narration=narration,caption=checked['text'],file=file,fit=fit,motion=motion,callout=callout))
(OUT/'scene-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
(OUT/'narration.txt').write_text('\n\n'.join(row['narration'] for row in plan)+'\n')
print({'scenes':len(plan),'words':len(' '.join(row['narration'] for row in plan).split()),'caption_layouts':'all fit two lines'})
