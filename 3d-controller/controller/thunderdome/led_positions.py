"""Generate and validate nominal physical XYZ LED positions."""
from __future__ import annotations
import json, math
from pathlib import Path
from .geometry import DomeGeometry
from .routes import RouteDefinition
PITCH=0.03; EPS=1e-9
class LedPositionsError(ValueError): pass
def generate_positions(routes:list[RouteDefinition],geometry:DomeGeometry)->dict:
 leds=[]
 for r in routes:
  length=r.total_length_m
  cumulative=0.0
  for i in range(1000):
   d=i*PITCH; base={'global_index':r.global_index_start+i,'string_id':r.string_id,'controller_number':r.controller_number,'string_index':i,'distance_along_string_m':d}
   if d<=length+EPS:
    remaining=d; segment=r.segments[0]
    for seg in r.segments:
     if remaining<=seg.length_m+EPS: segment=seg; break
     remaining-=seg.length_m
    fraction=max(0.0,min(1.0,remaining/segment.length_m))
    # snap to exact hub coordinates; end hubs associate preceding segment
    if abs(remaining)<EPS: fraction=0.0; xyz=geometry.hubs[segment.from_hub].xyz
    elif abs(remaining-segment.length_m)<EPS: fraction=1.0; xyz=geometry.hubs[segment.to_hub].xyz
    else:
     a,b=geometry.hubs[segment.from_hub],geometry.hubs[segment.to_hub]; xyz=tuple(x+fraction*(y-x) for x,y in zip(a.xyz,b.xyz))
    leds.append({**base,'location_type':'spar','spar_id':segment.spar_id,'spar_type':segment.spar_type,'from_hub':segment.from_hub,'to_hub':segment.to_hub,'fraction_along_spar':fraction,'distance_along_spar_m':fraction*segment.length_m,'distance_along_route_m':d,'x':xyz[0],'y':xyz[1],'z':xyz[2]})
   else:
    tail_index=i-next(j for j in range(1000) if j*PITCH>length+EPS); depth=d-length; apex=geometry.hubs['H061']
    leds.append({**base,'location_type':'tail','tail_index':tail_index,'distance_below_apex_m':depth,'x':apex.x,'y':apex.y,'z':apex.z-depth})
 return {'schema_version':1,'assumptions':{'led_pitch_m':PITCH,'first_led_offset_m':0.0,'route_model':'polyline_through_hub_centres','tail_direction':'negative_z','hub_boundary_convention':'preceding spar except route start'},'leds':leds}
def validate_positions(document,geometry:DomeGeometry,routes:list[RouteDefinition]):
 rows=document.get('leds') if isinstance(document,dict) else None
 if not isinstance(rows,list) or len(rows)!=5000: raise LedPositionsError('expected 5,000 records')
 if [r.get('global_index') for r in rows]!=list(range(5000)): raise LedPositionsError('indexes must be 0..4999')
 for route in routes:
  group=[r for r in rows if r.get('string_id')==route.string_id]
  if len(group)!=1000 or [r.get('string_index') for r in group]!=list(range(1000)): raise LedPositionsError('bad string indexing')
  tails=[r for r in group if r.get('location_type')=='tail']; spars=[r for r in group if r.get('location_type')=='spar']
  if any(r.get('location_type') not in {'spar','tail'} or not all(math.isfinite(float(r[k])) for k in ('x','y','z','distance_along_string_m')) for r in group): raise LedPositionsError('invalid location/XYZ')
  if any(abs(r['distance_along_string_m']-i*PITCH)>EPS for i,r in enumerate(group)): raise LedPositionsError('string distance must use 30mm pitch')
  if any(r['location_type']=='tail' for r in group[:len(spars)]) or [r['tail_index'] for r in tails]!=list(range(len(tails))): raise LedPositionsError('tail ordering')
  if tails and (tails[0]['distance_below_apex_m']<=0 or any(abs(x['distance_below_apex_m']-(x['distance_along_string_m']-route.total_length_m))>EPS for x in tails)): raise LedPositionsError('tail depth mismatch')
  if any(tails[i]['z']<tails[i+1]['z'] for i in range(len(tails)-1)): raise LedPositionsError('tail Z must decrease')
  for r in spars:
   if r['spar_id'] not in geometry.spars or not 0<=r['fraction_along_spar']<=1: raise LedPositionsError('invalid spar record')
 return rows
def write_positions(path,doc):
 path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
def load_led_positions(path,geometry=None,routes=None):
 d=json.loads(Path(path).read_text()); return validate_positions(d,geometry,routes) if geometry and routes else d['leds']
