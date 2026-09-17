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
 if document.get('schema_version')!=1: raise LedPositionsError('unsupported positions schema')
 expected_rows=generate_positions(routes,geometry)['leds']
 numeric_fields={'distance_along_string_m','distance_along_route_m','x','y','z','fraction_along_spar','distance_along_spar_m','distance_below_apex_m'}
 tolerance=1e-8
 for index,(actual,expected) in enumerate(zip(rows,expected_rows)):
  if not isinstance(actual,dict): raise LedPositionsError(f'record {index} must be an object')
  for field,expected_value in expected.items():
   if field not in actual: raise LedPositionsError(f'record {index} is missing {field}')
   actual_value=actual[field]
   if field in numeric_fields:
    try: valid=math.isfinite(float(actual_value)) and math.isclose(float(actual_value),float(expected_value),rel_tol=0.0,abs_tol=tolerance)
    except (TypeError,ValueError): valid=False
   else: valid=actual_value==expected_value
   if not valid: raise LedPositionsError(f'record {index} has incorrect {field}')
 return rows
def write_positions(path,doc):
 path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
def load_led_positions(path,geometry=None,routes=None):
 d=json.loads(Path(path).read_text()); return validate_positions(d,geometry,routes) if geometry and routes else d['leds']
