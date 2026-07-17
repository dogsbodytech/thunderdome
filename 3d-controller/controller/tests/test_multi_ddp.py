import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from thunderdome.controllers import load_controllers
from thunderdome.frame import RGBFrame
from thunderdome.transport.multi_ddp import MultiControllerDDPSession
ROOT=Path(__file__).resolve().parents[2]
class MultiDDPTests(unittest.TestCase):
 def setUp(self): self.config=load_controllers(ROOT/'config/controllers.example.json')
 def test_ranges_convert_global_to_local(self):
  self.assertEqual((self.config.controller_for_global_index(3000).controller_number,self.config.local_index_for_global_index(3000)),(4,0));self.assertEqual(self.config.local_index_for_global_index(4999),999)
 def test_splits_preserve_global_order(self):
  f=RGBFrame.allocate(5000)
  for i in range(5000): f.set_pixel(i,(i//1000,0,i%256))
  s=MultiControllerDDPSession(self.config); pieces=s.split_frame(f)
  self.assertEqual([x.led_count for x in pieces.values()],[1000]*5);self.assertEqual(tuple(pieces[4].data[:3]),(3,0,184))
 def test_dry_run_has_no_sender_calls(self):
  sender=Mock(); s=MultiControllerDDPSession(self.config,sender=sender); results=s.send_frame(RGBFrame.allocate(5000),dry_run=True)
  self.assertEqual(len(results),5); sender.assert_not_called()
