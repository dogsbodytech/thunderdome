"""Direct local-frame DDP fan-out; never relays through controller 1."""
from __future__ import annotations
import socket,time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from ..controllers import ControllerSet
from ..config import CONTROLLER_LED_COUNT, LOGICAL_LED_COUNT
from ..frame import RGBFrame
from .ddp import packets_for_frame,send_frame
@dataclass(frozen=True)
class SendResult: controller_number:int; host:str; packets:int; duration_seconds:float; error:str|None=None
class MultiControllerDDPSession:
 def __init__(self,config:ControllerSet,sender=send_frame,executor_factory=ThreadPoolExecutor):
  self.config=config; self.sender=sender; self.sockets={}; self._executor=None; self._executor_factory=executor_factory
 def __enter__(self): return self
 def __exit__(self,*_): self.close()
 def close(self):
  try:
   for s in self.sockets.values(): s.close()
  finally:
   self.sockets.clear()
   if self._executor is not None:
    self._executor.shutdown(wait=True); self._executor=None
 def split_frame(self,frame:RGBFrame):
  if frame.led_count!=LOGICAL_LED_COUNT: raise ValueError('fan-out requires exactly 5,000 LEDs')
  return {c.controller_number:RGBFrame(CONTROLLER_LED_COUNT,bytearray(frame.data[c.global_start*3:(c.global_end+1)*3])) for c in self.config.controllers}
 def send_frame(self,frame,*,mode='parallel',dry_run=False,subset=None):
  pieces=self.split_frame(frame); selected=[c for c in self.config.controllers if c.enabled and (subset is None or c.controller_number in subset)]
  def one(c):
   t=time.monotonic(); local=pieces[c.controller_number]
   if dry_run:return SendResult(c.controller_number,c.host,len(packets_for_frame(local.data,chunk_leds=self.config.ddp.chunk_size,destination_id=self.config.ddp.destination_id)),0.0)
   try:
    sock=self.sockets.get(c.controller_number)
    if sock is None:
     sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); sock.settimeout(self.config.ddp.timeout_seconds); self.sockets[c.controller_number]=sock
    n=self.sender(c.host,local.data,port=self.config.ddp.port,chunk_leds=self.config.ddp.chunk_size,destination_id=self.config.ddp.destination_id,sock=sock); return SendResult(c.controller_number,c.host,n,time.monotonic()-t)
   except Exception as e:return SendResult(c.controller_number,c.host,0,time.monotonic()-t,str(e))
  if mode=='sequential' or dry_run: return [one(c) for c in selected]
  if self._executor is None: self._executor=self._executor_factory(max_workers=5)
  return list(self._executor.map(one,selected))
