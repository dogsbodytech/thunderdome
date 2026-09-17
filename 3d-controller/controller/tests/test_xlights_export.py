from __future__ import annotations
import tempfile, unittest, xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunderdome.config import GEOMETRY_PATH, ROUTES_PATH
from thunderdome.geometry import load_geometry
from thunderdome.routes import load_routes
from thunderdome.led_positions import generate_positions
from thunderdome.xlights_export import dome_to_xlights, export_xlights

class XlightsExportTests(unittest.TestCase):
 def setUp(self):
  self.geometry=load_geometry(GEOMETRY_PATH); self.routes=load_routes(ROUTES_PATH,self.geometry); self.rows=generate_positions(self.routes,self.geometry)['leds']
 def test_coordinate_transform(self): self.assertEqual(dome_to_xlights(1,2,3),(100.0,300.0,200.0))
 def test_export_has_routes_positions_and_actual_tail(self):
  with tempfile.TemporaryDirectory() as d:
   output=Path(d)/'xlights_rgbeffects.xml'; export_xlights(output,self.geometry,self.routes)
   root=ET.parse(output).getroot(); models=root.find('models').findall('model'); self.assertEqual(len(models),5)
   self.assertEqual(root.find('modelGroups').find('modelGroup').get('name'),'Thunderdome')
   for route,model in zip(self.routes,models):
    self.assertEqual(model.get('StartChannel'),str(route.global_index_start*3+1)); self.assertEqual(model.get('NodesPerString'),'1000')
    counts=[int(x) for x in model.get('SegmentCounts').split(',')]; self.assertEqual(len(counts),25); self.assertEqual(sum(counts),1000)
    rows=[r for r in self.rows if r['string_id']==route.string_id]; expected=[sum(r['spar_id']==s.spar_id for r in rows if r['location_type']=='spar') for s in route.segments]
    self.assertEqual(counts[:-1],expected); self.assertEqual(counts[-1],sum(r['location_type']=='tail' for r in rows))
    points=[float(v) for v in model.get('PointData').split(',')]; self.assertEqual(tuple(points[-3:]),dome_to_xlights(rows[-1]['x'],rows[-1]['y'],rows[-1]['z']))
 def test_update_preserves_unrelated_and_backups_atomically(self):
  with tempfile.TemporaryDirectory() as d:
   output=Path(d)/'xlights_rgbeffects.xml'; output.write_text('<xrgb><!-- keep --><models><model name="Other"/></models><modelGroups><modelGroup name="Other Group"/></modelGroups><setting id="keep"/></xrgb>')
   export_xlights(output,self.geometry,self.routes); self.assertTrue((Path(str(output)+'.thunderdome.bak')).exists()); root=ET.parse(output).getroot(); self.assertIn('<!-- keep -->',output.read_text()); self.assertIsNotNone(root.find("models/model[@name='Other']")); self.assertIsNotNone(root.find("modelGroups/modelGroup[@name='Other Group']")); self.assertIsNotNone(root.find('setting'))
   export_xlights(output,self.geometry,self.routes); root=ET.parse(output).getroot(); self.assertEqual(len(root.findall('.//model')),6)
 def test_malformed_target_is_untouched(self):
  with tempfile.TemporaryDirectory() as d:
   output=Path(d)/'bad.xml'; output.write_text('<broken>');
   with self.assertRaises(ValueError): export_xlights(output,self.geometry,self.routes)
   self.assertEqual(output.read_text(),'<broken>')
if __name__=='__main__': unittest.main()
