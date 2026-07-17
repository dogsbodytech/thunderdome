"""Direct local-frame DDP fan-out; never relays through controller 1."""
from __future__ import annotations
import socket,time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from ..controllers import ControllerSet
from ..frame import RGBFrame
from .ddp import packets_for_frame,send_frame
@dataclass(frozen=True)
class SendResult: controller_number:int; host:str; packets:int; duration_seconds:float; error:str|None=None
class MultiControllerDDPSession:
 def __init__(self,config:ControllerSet,sender=send_frame): self.config=config; self.sender=sender; self.sockets={}
 def __enter__(self): return self
 def __exit__(self,*_): self.close()
 def close(self):
  for s in self.sockets.values(): s.close()
  self.sockets.clear()
 def split_frame(self,frame:RGBFrame):
  if frame.led_count!=5000: raise ValueError('fan-out requires exactly 5,000 LEDs')
  return {c.controller_number:RGBFrame(1000,bytearray(frame.data[c.global_start*3:(c.global_end+1)*3])) for c in self.config.controllers}
 def send_frame(self,frame,*,mode='parallel',dry_run=False,subset=None):
  pieces=self.split_frame(frame); selected=[c for c in self.config.controllers if c.enabled and (subset is None or c.controller_number in subset)]
  def one(c):
   t=time.monotonic(); local=pieces[c.controller_number]
   if dry_run:return SendResult(c.controller_number,c.host,len(packets_for_frame(local.data,chunk_leds=self.config.ddp.chunk_size)),0.0)
   try:
    sock=self.sockets.setdefault(c.controller_number,socket.socket(socket.AF_INET,socket.SOCK_DGRAM)); n=self.sender(c.host,local.data,port=self.config.ddp.port,chunk_leds=self.config.ddp.chunk_size,sock=sock); return SendResult(c.controller_number,c.host,n,time.monotonic()-t)
   except Exception as e:return SendResult(c.controller_number,c.host,0,time.monotonic()-t,str(e))
  if mode=='sequential': return [one(c) for c in selected]
  with ThreadPoolExecutor(max_workers=5) as pool:return list(pool.map(one,selected))
