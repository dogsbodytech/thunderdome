import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from thunderdome.config import CONTROLLER_LED_COUNT, LOGICAL_LED_COUNT
from thunderdome.controllers import load_controllers
from thunderdome.frame import RGBFrame
from thunderdome.transport.multi_ddp import MultiControllerDDPSession
ROOT=Path(__file__).resolve().parents[2]
class MultiDDPTests(unittest.TestCase):
 def setUp(self): self.config=load_controllers(ROOT/'config/controllers.example.json')
 def test_ranges_convert_global_to_local(self):
  self.assertEqual((self.config.controller_for_global_index(3000).controller_number,self.config.local_index_for_global_index(3000)),(4,0));self.assertEqual(self.config.local_index_for_global_index(4999),999)
 def test_splits_preserve_global_order(self):
  self.assertEqual((LOGICAL_LED_COUNT,CONTROLLER_LED_COUNT),(5000,1000))
  f=RGBFrame.allocate(LOGICAL_LED_COUNT)
  for i in range(LOGICAL_LED_COUNT): f.set_pixel(i,(i//CONTROLLER_LED_COUNT,0,i%256))
  s=MultiControllerDDPSession(self.config); pieces=s.split_frame(f)
  self.assertEqual([x.led_count for x in pieces.values()],[CONTROLLER_LED_COUNT]*5);self.assertEqual(tuple(pieces[4].data[:3]),(3,0,184))
 def test_dry_run_has_no_sender_calls(self):
  sender=Mock(); s=MultiControllerDDPSession(self.config,sender=sender); results=s.send_frame(RGBFrame.allocate(LOGICAL_LED_COUNT),dry_run=True)
  self.assertEqual(len(results),5); sender.assert_not_called()
 def test_send_attempts_all_enabled_controllers_after_one_failure(self):
  attempted=[]
  def sender(host,*_args,**_kwargs):
   attempted.append(host)
   if host==self.config.controllers[1].host: raise OSError('simulated failure')
   return 3
  with patch('thunderdome.transport.multi_ddp.socket.socket',return_value=Mock()):
   with MultiControllerDDPSession(self.config,sender=sender) as session: results=session.send_frame(RGBFrame.allocate(LOGICAL_LED_COUNT))
  self.assertEqual(set(attempted),{controller.host for controller in self.config.controllers})
  self.assertEqual([result.controller_number for result in results if result.error],[2])
