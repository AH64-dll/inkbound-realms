import os,time,json
from pathlib import Path
os.environ['SDL_AUDIODRIVER']='dummy'
import pygame as pg
from inkbound.realm.models import RealmSpec
from inkbound.realm.package import RealmPackage
from inkbound.runtime.engine import Engine
from inkbound.runtime.ui import App,TABS
out=Path('artifacts/runtime');out.mkdir(parents=True,exist_ok=True)
report=[]
for genre in ['fantasy','horror','science_fiction']:
 e=Engine(RealmPackage(RealmSpec.model_validate_json(Path('fixtures/'+genre+'.json').read_bytes())))
 app=App(e,'/tmp/inkbound-'+genre+'-capture.json');app.sound=False
 start=time.monotonic()
 for tab in TABS:
  app.tab=tab;app.draw();pg.image.save(app.screen,str(out/(genre+'-'+tab.lower()+'.png')))
 app.tab='MAP'; e.enter('location.home');app.draw();pg.image.save(app.screen,str(out/(genre+'-town.png')))
 e.player.x,e.player.y=e.state.npc_positions['npc.guide'];e.talk('npc.guide');app.draw();pg.image.save(app.screen,str(out/(genre+'-dialogue.png')))
 e.close_dialogue();e.leave();app.ascii=True;app.draw();pg.image.save(app.screen,str(out/(genre+'-ascii.png')))
 frames=[]
 for _ in range(30):
  s=time.monotonic();app.draw();frames.append((time.monotonic()-s)*1000)
 report.append({'genre':genre,'mean_draw_ms':round(sum(frames)/len(frames),3),'max_draw_ms':round(max(frames),3),'turn_unchanged_by_30_frames':e.state.turn==0})
 pg.quit()
(out/'render-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
