from __future__ import annotations
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunderdome.geometry import load_geometry
from thunderdome.routes import RouteError, load_routes, generate_route_document
from thunderdome.led_positions import generate_positions, validate_positions

ROOT=Path(__file__).resolve().parents[2]
ROUTE=ROOT/'geometry/reference_string_route.md'; GEOM=ROOT/'geometry/thunderdome_geometry.json'
class AuthoritativeRoutesTests(unittest.TestCase):
 def setUp(self): self.geometry=load_geometry(GEOM); self.routes=load_routes(ROUTE,self.geometry)
 def test_five_routes_are_exactly_validated(self):
  self.assertEqual(len(self.routes),5); self.assertEqual([r.start_hub for r in self.routes],['H032','H033','H034','H035','H031'])
  self.assertTrue(all(len(r.hubs)==25 and len(r.segments)==24 for r in self.routes)); self.assertEqual(len({s.spar_id for r in self.routes for s in r.segments}),120)
  self.assertEqual({round(r.total_length_m,5) for r in self.routes}, {round(self.routes[0].total_length_m,5)}); self.assertTrue(all(r.end_hub=='H061' for r in self.routes))
 def test_route_and_positions_are_deterministic_and_complete(self):
  self.assertEqual(generate_route_document(self.routes,ROUTE,GEOM),generate_route_document(self.routes,ROUTE,GEOM))
  document=generate_positions(self.routes,self.geometry); validate_positions(document,self.geometry,self.routes)
  self.assertEqual(len(document['leds']),5000); self.assertEqual([x['global_index'] for x in document['leds']],list(range(5000)))
  self.assertTrue(all(len([x for x in document['leds'] if x['string_id']==s])==1000 for s in range(5)))
  first=document['leds'][0]; self.assertEqual((first['location_type'],first['fraction_along_spar']),('spar',0.0))
  for s in range(5):
   row=[x for x in document['leds'] if x['string_id']==s]; tail=[x for x in row if x['location_type']=='tail']; self.assertTrue(tail); self.assertEqual([x['tail_index'] for x in tail],list(range(len(tail))))
 def test_tail_preserves_pitch_after_apex(self):
  rows=generate_positions(self.routes,self.geometry)['leds']; group=[x for x in rows if x['string_id']==0]; dome=[x for x in group if x['location_type']=='spar']; tail=[x for x in group if x['location_type']=='tail']
  self.assertIn('distance_along_string_m', group[0]); self.assertGreater(tail[0]['distance_below_apex_m'],0.0)
  self.assertAlmostEqual(tail[0]['distance_below_apex_m'],tail[0]['distance_along_string_m']-self.routes[0].total_length_m,places=9)
  self.assertAlmostEqual(tail[0]['distance_along_string_m']-dome[-1]['distance_along_string_m'],.03,places=8)
  self.assertAlmostEqual(tail[-1]['distance_below_apex_m'],1.881449,places=6)
 def test_corrupt_route_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.md'; p.write_text('## String 1\nController: 1\nString ID: 0\nGlobal LED indexes: 0-999\nStart hub: H001\nEnd hub: H061\n```text\nH001 > H061\n```')
   with self.assertRaises(RouteError): load_routes(p,self.geometry)
if __name__=='__main__': unittest.main()
