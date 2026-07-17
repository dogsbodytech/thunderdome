"""Minimal WLED JSON API client.

Configure with WLED_BASE_URL, for example:

    export WLED_BASE_URL=http://wled.local

This client intentionally uses only the Python standard library so it can be
copied into small installation-control projects without extra dependencies.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any


JsonDict = dict[str, Any]
RGB = tuple[int, int, int]


class WLEDApiError(RuntimeError):
    """Raised when the WLED device cannot be reached or returns bad data."""


class WLEDClient:
    """Small HTTP JSON client for WLED.

    WLED's JSON API accepts POSTs to /json or /json/state containing partial
    state objects. This client posts to /json/state for state changes and uses
    GET requests for read-only endpoints.
    """

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        if not base_url:
            raise ValueError("base_url is required, e.g. http://wled.local")
        if not base_url.startswith(("http://", "https://")):
            base_url = "http://" + base_url
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._info_cache: JsonDict | None = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request_json(self, method: str, path: str, payload: JsonDict | None = None) -> Any:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            self._url(path),
            data=data,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise WLEDApiError(f"HTTP {exc.code} from {request.full_url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise WLEDApiError(f"Could not reach WLED at {request.full_url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise WLEDApiError(f"Timed out connecting to WLED at {request.full_url}") from exc
        except socket.timeout as exc:
            raise WLEDApiError(f"Timed out reading from WLED at {request.full_url}") from exc

        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            sample = body[:200].decode("utf-8", errors="replace")
            raise WLEDApiError(f"Invalid JSON from {request.full_url}: {sample!r}") from exc

    # Read endpoints -----------------------------------------------------

    def get_json(self) -> JsonDict:
        """GET /json: full object containing state, info, effects, palettes."""
        return self._request_json("GET", "/json")

    def get_state(self) -> JsonDict:
        """GET /json/state: current mutable light state."""
        return self._request_json("GET", "/json/state")

    def get_info(self, *, refresh: bool = False) -> JsonDict:
        """GET /json/info: read-only device metadata and capability counts."""
        if refresh or self._info_cache is None:
            self._info_cache = self._request_json("GET", "/json/info")
        return self._info_cache

    def get_effects(self) -> list[str]:
        """GET /json/eff: list of effect names by numeric ID."""
        return self._request_json("GET", "/json/eff")

    def get_palettes(self) -> list[str]:
        """GET /json/pal: list of palette names by numeric ID."""
        return self._request_json("GET", "/json/pal")

    # Write endpoint -----------------------------------------------------

    def post_state(self, payload: JsonDict, return_state: bool = False) -> Any:
        """POST a partial state object to /json/state.

        If return_state is true, WLED v0.13+ returns the updated full state when
        the transient `v: true` field is included in the request.
        """
        request_payload = dict(payload)
        if return_state:
            request_payload["v"] = True
        return self._request_json("POST", "/json/state", request_payload)

    # Convenience controls ----------------------------------------------

    def set_power(self, on: bool, *, return_state: bool = False) -> Any:
        # Payload: global on/off state.
        return self.post_state({"on": bool(on)}, return_state=return_state)

    def toggle_power(self, *, return_state: bool = False) -> Any:
        # Payload: WLED accepts string "t" to toggle a boolean.
        return self.post_state({"on": "t"}, return_state=return_state)

    def set_brightness(self, value: int, *, return_state: bool = False) -> Any:
        self._validate_byte(value, "brightness")
        # Payload: global brightness 0-255. Prefer on:false to fully turn off.
        return self.post_state({"bri": value}, return_state=return_state)

    def set_live(self, enabled: bool, *, return_state: bool = False) -> Any:
        """Enable or disable WLED realtime/live mode."""
        return self.post_state({"live": bool(enabled)}, return_state=return_state)

    def set_preset(self, preset_id: int, *, return_state: bool = False) -> Any:
        """Activate a positive WLED preset ID."""
        if not isinstance(preset_id, int) or preset_id <= 0:
            raise ValueError("preset_id must be a positive integer")
        return self.post_state({"ps": preset_id}, return_state=return_state)

    def prepare_ddp(self, *, return_state: bool = False) -> Any:
        """Set a safe persistent fallback state for application DDP output.

        WLED can turn on when brightness is posted separately, so all baseline
        fields intentionally travel in one state update.
        """
        return self.post_state({"on": False, "bri": 255, "live": False}, return_state=return_state)

    def set_transition(self, value: int, *, temporary: bool = False, return_state: bool = False) -> Any:
        self._validate_u16(value, "transition")
        # transition persists in state; tt applies only to this API call.
        key = "tt" if temporary else "transition"
        return self.post_state({key: value}, return_state=return_state)

    def set_color(self, rgb: RGB, segment_id: int | None = None, *, return_state: bool = False) -> Any:
        r, g, b = self._validate_rgb(rgb)
        segment: JsonDict = {"fx": 0, "col": [[r, g, b]]}
        if segment_id is not None:
            self._validate_nonnegative_int(segment_id, "segment_id")
            segment["id"] = segment_id
        # Payload: set primary color. If no id is supplied, this targets segment 0
        # by position in the seg array; include id for explicit per-segment updates.
        return self.post_state({"seg": [segment]}, return_state=return_state)

    def set_effect(self, effect_id: int, segment_id: int | None = None, *, return_state: bool = False) -> Any:
        self._validate_effect_id(effect_id)
        segment: JsonDict = {"fx": effect_id}
        if segment_id is not None:
            self._validate_nonnegative_int(segment_id, "segment_id")
            segment["id"] = segment_id
        # Payload: set effect by numeric ID from /json/eff.
        return self.post_state({"seg": [segment]}, return_state=return_state)

    def set_palette(self, palette_id: int, segment_id: int | None = None, *, return_state: bool = False) -> Any:
        self._validate_palette_id(palette_id)
        segment: JsonDict = {"pal": palette_id}
        if segment_id is not None:
            self._validate_nonnegative_int(segment_id, "segment_id")
            segment["id"] = segment_id
        # Payload: set palette by numeric ID from /json/pal.
        return self.post_state({"seg": [segment]}, return_state=return_state)

    def update_segment(self, segment_id: int, payload: JsonDict, *, return_state: bool = False) -> Any:
        self._validate_nonnegative_int(segment_id, "segment_id")
        segment = dict(payload)
        segment["id"] = segment_id
        # Payload: merge/update only the supplied fields on this segment.
        return self.post_state({"seg": [segment]}, return_state=return_state)

    def update_segments(self, segments: list[JsonDict], *, return_state: bool = False) -> Any:
        # Payload: create/update multiple segment objects in a single request.
        return self.post_state({"seg": segments}, return_state=return_state)

    def set_individual_leds(self, led_payload: list[Any], segment_id: int | None = None, *, return_state: bool = False) -> Any:
        """Set per-segment individual LEDs with WLED's `seg.i` payload.

        led_payload examples:
          ["FF0000", "00FF00", "0000FF"]
          [0, "FF0000", 2, "00FF00", 4, "0000FF"]
          [0, 8, "FF0000", 10, 18, "0000FF"]
        """
        segment: JsonDict = {"i": led_payload}
        if segment_id is not None:
            self._validate_nonnegative_int(segment_id, "segment_id")
            segment["id"] = segment_id
        # Use the list form for `seg` everywhere. WLED accepts a single object in
        # many cases, but a list is consistent with multi-segment operations.
        return self.post_state({"seg": [segment]}, return_state=return_state)

    # Validation ---------------------------------------------------------

    @staticmethod
    def _validate_byte(value: int, name: str) -> None:
        if not isinstance(value, int) or not 0 <= value <= 255:
            raise ValueError(f"{name} must be an integer from 0 to 255")

    @staticmethod
    def _validate_u16(value: int, name: str) -> None:
        if not isinstance(value, int) or not 0 <= value <= 65535:
            raise ValueError(f"{name} must be an integer from 0 to 65535")

    @classmethod
    def _validate_rgb(cls, rgb: RGB) -> RGB:
        if len(rgb) != 3:
            raise ValueError("rgb must contain exactly three values")
        for channel in rgb:
            cls._validate_byte(channel, "RGB channel")
        return rgb

    @staticmethod
    def _validate_nonnegative_int(value: int, name: str) -> None:
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    def _validate_effect_id(self, effect_id: int) -> None:
        self._validate_nonnegative_int(effect_id, "effect_id")
        fxcount = self.get_info().get("fxcount")
        if isinstance(fxcount, int) and effect_id >= fxcount:
            raise ValueError(f"effect_id must be less than info.fxcount ({fxcount})")

    def _validate_palette_id(self, palette_id: int) -> None:
        self._validate_nonnegative_int(palette_id, "palette_id")
        palcount = self.get_info().get("palcount")
        if isinstance(palcount, int) and palette_id >= palcount:
            raise ValueError(f"palette_id must be less than info.palcount ({palcount})")
