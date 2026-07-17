"""Validated direct-DDP controller allocation."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
EXPECTED={1:(0,'H032'),2:(1,'H033'),3:(2,'H034'),4:(3,'H035'),5:(4,'H031')}
class ControllerConfigError(ValueError): pass
@dataclass(frozen=True)
class Controller:
 controller_number:int; string_id:int; start_hub:str; host:str; global_start:int; global_end:int; local_led_count:int; enabled:bool
@dataclass(frozen=True)
class DDPDefaults: port:int=4048; chunk_size:int=480; destination_id:int=1; timeout_seconds:float=1.0
@dataclass(frozen=True)
class ControllerSet:
 ddp:DDPDefaults; controllers:tuple[Controller,...]
 def controller_for_global_index(self,index):
  if not 0<=index<5000: raise ControllerConfigError('global index outside 0..4999')
  return next(c for c in self.controllers if c.global_start<=index<=c.global_end)
 def local_index_for_global_index(self,index): return index-self.controller_for_global_index(index).global_start
 def slice_for_controller(self,number):
  c=next((x for x in self.controllers if x.controller_number==number),None)
  if not c: raise ControllerConfigError('unknown controller')
  return slice(c.global_start,c.global_end+1)
def load_controllers(path)->ControllerSet:
 try: d=json.loads(Path(path).read_text()); ddp=DDPDefaults(**d['ddp']); cs=tuple(Controller(**x) for x in d['controllers'])
 except Exception as e: raise ControllerConfigError(f'invalid controller config: {e}') from e
 if len(cs)!=5 or {c.controller_number for c in cs}!={1,2,3,4,5} or {c.string_id for c in cs}!={0,1,2,3,4}: raise ControllerConfigError('requires controllers 1..5 and strings 0..4')
 if sorted((c.global_start,c.global_end) for c in cs)!=[(i*1000,i*1000+999) for i in range(5)]: raise ControllerConfigError('ranges must completely cover 0..4999 in blocks of 1000')
 if any((c.string_id,c.start_hub)!=EXPECTED[c.controller_number] or c.local_led_count!=1000 or not c.host.strip() for c in cs): raise ControllerConfigError('invalid controller allocation, host, or LED count')
 return ControllerSet(ddp,tuple(sorted(cs,key=lambda c:c.controller_number)))
