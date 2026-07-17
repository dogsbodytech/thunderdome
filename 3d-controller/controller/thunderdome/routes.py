"""Authoritative manually captured structural LED routes."""
from __future__ import annotations
import json,re
from dataclasses import dataclass
from pathlib import Path
from .geometry import DomeGeometry

class RouteError(ValueError): pass
EXPECTED={1:(0,'H032',0,999),2:(1,'H033',1000,1999),3:(2,'H034',2000,2999),4:(3,'H035',3000,3999),5:(4,'H031',4000,4999)}
@dataclass(frozen=True)
class DirectedSegment:
 spar_id:str; spar_type:str; from_hub:str; to_hub:str; length_m:float
@dataclass(frozen=True)
class RouteDefinition:
 string_id:int; hubs:tuple[str,...]; rotation_degrees:float=0.0; controller_number:int=0; global_index_start:int=0; global_index_end:int=999; start_hub:str=''; end_hub:str=''; segments:tuple[DirectedSegment,...]=()
 @property
 def total_length_m(self): return sum(x.length_m for x in self.segments)
 @property
 def unique_spar_count(self): return len({x.spar_id for x in self.segments})
 def spar_ids(self,geometry):
  return tuple(geometry.spar_between(a,b).id for a,b in zip(self.hubs,self.hubs[1:]) if geometry.spar_between(a,b))
def hub(value:str)->str:
 n=int(re.sub(r'[^0-9]','',value));
 if not 1<=n<=61: raise RouteError(f'invalid hub {value}')
 return f'H{n:03d}'
def load_routes(path:str|Path, geometry:DomeGeometry)->list[RouteDefinition]:
 text=Path(path).read_text(); blocks=re.split(r'^## String \d+\s*$',text,flags=re.M)[1:]
 if len(blocks)!=5: raise RouteError(f'expected exactly five route blocks, found {len(blocks)}')
 routes=[]
 for block in blocks:
  def field(name):
   m=re.search(rf'{name}:\s*`?([^`\n]+)',block); return m.group(1).strip() if m else None
  try: controller=int(field('Controller')); sid=int(field('String ID')); start=hub(field('Start hub')); end=hub(field('End hub')); a,b=re.findall(r'\d+',field('Global LED indexes'))[:2]
  except Exception as exc: raise RouteError('route metadata is incomplete') from exc
  code=re.search(r'```text\s*(.*?)\s*```',block,re.S)
  if not code: raise RouteError(f'string {sid}: missing hub route')
  hubs=tuple(hub(x) for x in re.findall(r'H?\d{1,3}',code.group(1)))
  if len(hubs)<2 or hubs[0]!=start or hubs[-1]!=end or end!='H061': raise RouteError(f'string {sid}: invalid endpoints')
  seg=[]
  for one,two in zip(hubs,hubs[1:]):
   spar=geometry.spar_between(one,two)
   if not spar: raise RouteError(f'string {sid}: {one}->{two} is not a spar')
   seg.append(DirectedSegment(spar.id,spar.type,one,two,spar.length_m))
  if len(hubs)!=25 or len(seg)!=24 or len({x.spar_id for x in seg})!=24: raise RouteError(f'string {sid}: expected 25 hubs/24 unique spars')
  routes.append(RouteDefinition(string_id=sid,hubs=hubs,controller_number=controller,global_index_start=int(a),global_index_end=int(b),start_hub=start,end_hub=end,segments=tuple(seg)))
 validate_routes(geometry,routes); return sorted(routes,key=lambda x:x.string_id)
def validate_routes(geometry:DomeGeometry,routes:list[RouteDefinition],require_apex:bool=True)->None:
 if routes and all(r.controller_number==0 for r in routes):
  used=set()
  for r in routes:
   for a,b in zip(r.hubs,r.hubs[1:]):
    spar=geometry.spar_between(a,b)
    if not spar: raise RouteError(f'{a}->{b} is not a spar')
    if spar.id in used: raise RouteError(f'shared spar {spar.id}')
    used.add(spar.id)
  return
 if len(routes)!=5: raise RouteError('expected exactly five routes')
 used={}; types=None; lengths=None
 for r in routes:
  if r.controller_number not in EXPECTED or (r.string_id,r.start_hub,r.global_index_start,r.global_index_end)!=EXPECTED[r.controller_number]: raise RouteError(f'controller allocation mismatch for {r.controller_number}')
  if require_apex and r.end_hub!='H061': raise RouteError('all routes must end H061')
  seq=tuple(x.spar_type for x in r.segments)
  if types is None: types=seq; lengths=r.total_length_m
  if seq!=types or abs(r.total_length_m-lengths)>1e-5: raise RouteError('routes must have identical types and length')
  for s in r.segments:
   if s.spar_id in used: raise RouteError(f'shared spar {s.spar_id}')
   used[s.spar_id]=r.string_id
 if len(used)!=120: raise RouteError('expected 120 unique route spars')
def generate_route_document(routes:list[RouteDefinition],route_path:str|Path,geometry_path:str|Path)->dict:
 return {'schema_version':1,'source_route_filename':Path(route_path).name,'source_geometry_filename':Path(geometry_path).name,'assumptions':{'led_pitch_m':0.03,'first_led_offset_m':0.0,'hub_transition_model':'none','tail_start_hub':'H061','tail_direction':'negative_z'},'routes':[{'controller_number':r.controller_number,'string_id':r.string_id,'global_index_start':r.global_index_start,'global_index_end':r.global_index_end,'start_hub':r.start_hub,'end_hub':r.end_hub,'ordered_hubs':list(r.hubs),'segments':[s.__dict__ for s in r.segments],'total_route_length_m':r.total_length_m,'unique_spar_count':r.unique_spar_count} for r in routes],'validation_summary':{'route_count':5,'total_segments':120,'unique_spars':120,'shared_spars':0}}
def write_route_document(path,doc): Path(path).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
