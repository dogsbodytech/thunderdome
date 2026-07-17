import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thunderdome.wled.client import WLEDClient
from thunderdome.wled.favorites import FavoritesStore


class Response:
    def __init__(self, body): self.body = body.encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.body


class WLEDSupportTests(unittest.TestCase):
    def test_client_gets_state_and_posts_brightness(self):
        with patch("urllib.request.urlopen", return_value=Response('{"on": true}')) as call:
            client = WLEDClient("wled.local")
            self.assertEqual(client.get_state(), {"on": True})
            self.assertEqual(call.call_args.args[0].full_url, "http://wled.local/json/state")
        with patch.object(WLEDClient, "post_state", return_value={}) as post:
            WLEDClient("wled.local").set_brightness(32)
            post.assert_called_once_with({"bri": 32}, return_state=False)

    def test_client_sets_realtime_live_mode(self):
        with patch.object(WLEDClient, "post_state", return_value={}) as post:
            WLEDClient("wled.local").set_live(True)
            post.assert_called_once_with({"live": True}, return_state=False)

    def test_favorites_store_deduplicates_effects(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            store = FavoritesStore(Path(directory) / "favorites.json")
            store.add_effect(1, ["Solid", "Rainbow"])
            _, created = store.add_effect(1, ["Solid", "Rainbow"], notes="safe")
            self.assertFalse(created)
            self.assertEqual(store.list_effects(), [{"id": 1, "name": "Rainbow", "notes": "safe"}])


if __name__ == "__main__": unittest.main()
