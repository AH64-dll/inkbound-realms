import os,sys,json,tempfile,shutil,random,time
from pathlib import Path
os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,str(Path('legacy/ascii_rpg').resolve()))
import pygame as pg
from src.ui import App
from src import game
from src.worldgen import WALKABLE, World
from src.saves import read_save
root=Path(tempfile.mkdtemp(prefix='inkbound-audit-'))
(root/'books').mkdir(); shutil.copy('legacy/ascii_rpg/books/sample.txt',root/'books')
app=App(root,seed=42); app.started=True; app.settings['sound']=False
out=Path('artifacts/audit').resolve(); records=[]
rng=random.Random(42)
# Drive the actual application loop and its input dispatcher, capture each surface.
stages=['overworld','characters','books','saves','settings','inventory','data','town','dungeon','combat','after_combat','ascii']
original_flip=pg.display.flip
frame=0

def flip():
 global frame
 name=stages[frame]
 pg.image.save(pg.display.get_surface(),str(out/(name+'.png')))
 records.append({'surface':name,'hp':app.state.player.hp,'position':[app.state.player.x,app.state.player.y],'messages':app.state.messages[-5:]})
 original_flip(); frame+=1
 if frame>=len(stages):
  pg.event.post(pg.event.Event(pg.QUIT)); pg.display.flip=original_flip; return
 name=stages[frame]
 app.tab={'characters':'CHARACTERS','books':'BOOKS','saves':'SAVES','settings':'SETTINGS','inventory':'INVENTORY','data':'DATA'}.get(name,'MAP')
 if name=='town':
  c=app.world.cities[0]; app.state.player.x,app.state.player.y=c.x,c.y
  app._key(pg,pg.K_e)
  for k in [pg.K_UP,pg.K_UP,pg.K_e,pg.K_b,pg.K_ESCAPE]: app._key(pg,k)
 elif name=='dungeon':
  game.ascend(app.state); s=next(s for s in app.world.sites if s.kind=='dungeon')
  app.state.player.x,app.state.player.y=s.x,s.y; app._key(pg,pg.K_e)
 elif name=='combat':
  # Controlled encounter checks the actual combat controls, without spending hours crossing a huge map.
  sx,sy=app.state.player.x,app.state.player.y
  e=game.Enemy('Audit raider',sx+1,sy,28,4,draught=False); app.state.enemies=[e]; app.state.in_combat_with=e
  app._key(pg,pg.K_d); app._key(pg,pg.K_q)
 elif name=='after_combat':
  for _ in range(15):
   if not app.state.in_combat_with: break
   game.combat_attack(app.state,rng)
  game.gain_xp(app.state,100); app.persist()
 elif name=='ascii':
  game.ascend(app.state); app.settings['graphics']='ascii'
  for k in [pg.K_RIGHT,pg.K_DOWN,pg.K_LEFT,pg.K_UP]: app._key(pg,k)
pg.display.flip=flip
start=time.monotonic(); app.run()
wd,roster,active,enemies=read_save(root,'slot1')
report={'source_commit':'fdaa736','seed':42,'book':'sample.txt','temporary_save':str(root),'elapsed_seconds':round(time.monotonic()-start,3),'world':{'width':wd['width'],'height':wd['height'],'cities':len(wd['cities']),'characters':len(wd['characters']),'sites':len(wd['sites']),'quests':len(wd['quests']),'dormant_quests':len(wd['dormant_quests'])},'save_load':World.from_dict(wd).to_dict()==wd,'player_roundtrip':game.Player.from_dict(roster[0]).to_dict()==roster[0],'screens':records}
(out/'report.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
