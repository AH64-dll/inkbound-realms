import sys,random,json,time
from pathlib import Path
sys.path.insert(0,str(Path('legacy/ascii_rpg').resolve()))
from src import game
from src.worldgen import generate_world,WALKABLE,grow
from src.dungeon import gen_interior
from src.ingest import load_document
s=time.monotonic(); text=load_document('legacy/ascii_rpg/books/sample.txt'); world=generate_world(text,seed=42)
state=game.new_game(world,42); rng=random.Random(42); moved=0
for _ in range(100):
 if state.in_combat_with:
  if state.player.hp<20: game.combat_flee(state,rng)
  else: game.combat_quick(state,rng)
 else:
  x,y=state.player.x,state.player.y
  legal=[(dx,dy) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)] if 0<=x+dx<world.width and 0<=y+dy<world.height and world.grid[y+dy][x+dx] in WALKABLE]
  if legal: game.move_player(state,*rng.choice(legal),rng); moved+=1
 if world.director_active:
  from src.director import resolve_choice
  resolve_choice(state,world.director_active['choices'][0]['id'],rng)
 if state.player.hp<=0: game.respawn(state)
a,b=generate_world(text,seed=42),generate_world(text,seed=42)
assert a.grid==b.grid
assert gen_interior(42,'test','dungeon')==gen_interior(42,'test','dungeon')
old=a.width; shift=grow(a,'left'); assert a.width==old+32
report={'steps':100,'moves':moved,'hp':state.player.hp,'clock':world.clock,'messages':state.messages[-12:],'terrain_repeat':True,'dungeon_repeat':True,'frontier_width':a.width,'frontier_shift':shift,'elapsed_seconds':round(time.monotonic()-s,3)}
Path('artifacts/audit/playthrough.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
