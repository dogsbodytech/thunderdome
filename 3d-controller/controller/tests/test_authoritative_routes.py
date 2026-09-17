from __future__ import annotations
import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunderdome.geometry import load_geometry
from thunderdome.config import ROUTES_PATH
from thunderdome.routes import RouteError, load_routes
from thunderdome.led_positions import LedPositionsError, generate_positions, validate_positions

ROOT=Path(__file__).resolve().parents[2]
ROUTE=ROUTES_PATH; GEOM=ROOT/'geometry/thunderdome_geometry.json'
class AuthoritativeRoutesTests(unittest.TestCase):
 def setUp(self): self.geometry=load_geometry(GEOM); self.routes=load_routes(ROUTE,self.geometry)
 def test_json_is_the_default_route_authority(self):
  self.assertEqual(ROUTE, ROOT/'geometry/routes/string_routes.json')
 def test_five_routes_are_exactly_validated(self):
  self.assertEqual(len(self.routes),5); self.assertEqual([r.start_hub for r in self.routes],['H032','H033','H034','H035','H031'])
  self.assertTrue(all(len(r.hubs)==25 and len(r.segments)==24 for r in self.routes)); self.assertEqual(len({s.spar_id for r in self.routes for s in r.segments}),120)
  self.assertEqual({round(r.total_length_m,5) for r in self.routes}, {round(self.routes[0].total_length_m,5)}); self.assertTrue(all(r.end_hub=='H061' for r in self.routes))
 def test_route_and_positions_are_deterministic_and_complete(self):
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
 def test_position_validation_rejects_authoritative_placement_corruption(self):
  document=generate_positions(self.routes,self.geometry); rows=document['leds']; spar=next(row for row in rows if row['location_type']=='spar' and row['string_index']>0); tail=next(row for row in rows if row['location_type']=='tail')
  other_spar=next(spar_id for spar_id in self.geometry.spars if spar_id!=spar['spar_id'])
  cases=[
   ('x',spar['global_index'],spar['x']+.001),
   ('spar_id',spar['global_index'],other_spar),
   ('from_hub',spar['global_index'],spar['to_hub']),
   ('fraction_along_spar',spar['global_index'],min(1.0,spar['fraction_along_spar']+.1)),
   ('string_index',spar['global_index'],spar['string_index']+1),
   ('x',tail['global_index'],tail['x']+.001),
   ('z',tail['global_index'],tail['z']+.001),
  ]
  for field,index,value in cases:
   with self.subTest(field=field,index=index):
    corrupted=copy.deepcopy(document); corrupted['leds'][index][field]=value
    with self.assertRaises(LedPositionsError): validate_positions(corrupted,self.geometry,self.routes)
 def test_malformed_json_route_authority_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   def rejects(mutate):
    document=json.loads(ROUTE.read_text()); mutate(document)
    path=Path(d)/'bad.json'; path.write_text(json.dumps(document))
    with self.assertRaises(RouteError): load_routes(path,self.geometry)
   rejects(lambda document: document.__setitem__('schema_version', 1))
   rejects(lambda document: document['routes'][0]['ordered_hubs'].__setitem__(1, 'H999'))
   rejects(lambda document: document['routes'][0]['ordered_hubs'].__setitem__(1, 'H061'))
   rejects(lambda document: document['routes'][0].__setitem__('controller_number', 9))
   rejects(lambda document: document['routes'][1].__setitem__('ordered_hubs', document['routes'][0]['ordered_hubs']))
if __name__=='__main__': unittest.main()
