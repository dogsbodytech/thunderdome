"""Repeatable offline lifecycle/cache diagnostics; stdout is measured JSON.

Run from the repository root:
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python controller/diagnostics/defect_audit.py
No generated positions, files, HTTP or DDP output are used.
"""
from __future__ import annotations

import gc
import json
from pathlib import Path
import socket
import sys
import threading
import tracemalloc
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.control import ControlAPI, ControlSettings, FrameRuntime
from thunderdome.effects.Common import SpatialContext
from thunderdome.effects.Procedural import (
    MAX_FIREFLIES, MAX_TWINKLE_SPAWN_RATE, create_renderer, particle_templates,
)
from thunderdome.frame import RGBFrame
from thunderdome.runtime import (
    CommandAction, CommandSource, OutputMode, RuntimeCommand, RuntimeCoordinator,
)


def command(action, *, duration=None):
    return RuntimeCommand(CommandSource.BROWSER, action, "same", "Fire", {},
                          OutputMode.NULL, duration_seconds=duration)


def retained():
    gc.collect()
    return tracemalloc.get_traced_memory()[0]


def worker_diagnostic():
    entered = threading.Event()
    frame = RGBFrame.allocate(5000)
    def factory(display):
        def render(number, elapsed):
            entered.set()
            return frame
        return render, 30
    runtime = FrameRuntime(ControlSettings("http://unused.invalid"), factory)
    coordinator = RuntimeCoordinator(runtime)
    peak_live = 0
    def batch(count):
        nonlocal peak_live
        for _ in range(count):
            entered.clear()
            result = coordinator.execute(command(CommandAction.SET_BASELINE))
            assert result.accepted, result.reason
            assert entered.wait(2), "worker never rendered"
            worker = runtime._thread
            peak_live = max(peak_live, sum(t.name == "thunderdome-control-runtime" for t in threading.enumerate()))
            result = coordinator.execute(command(CommandAction.STOP_ALL))
            assert result.accepted, result.reason
            assert not worker.is_alive()
            assert runtime._thread is None
            assert result.status["service_state"] == "idle"
            assert result.status["effective"] is None
    batch(20)
    tracemalloc.start()
    base = retained()
    batch(200)
    first = retained()
    batch(200)
    second = retained()
    tracemalloc.stop()
    runtime.shutdown()
    return {"warmup_cycles": 20, "measured_cycles": 400,
            "peak_runtime_threads": peak_live,
            "remaining_runtime_threads": sum(t.name == "thunderdome-control-runtime" for t in threading.enumerate()),
            "retained_bytes_after_200": first - base,
            "retained_bytes_after_400": second - base,
            "second_batch_growth_bytes": second - first}


class QuietRuntime:
    def start(self, display):
        pass
    def stop(self):
        pass
    def shutdown(self):
        pass


def timer_diagnostic():
    api = ControlAPI(ControlSettings("http://unused.invalid", default_output=OutputMode.NULL), QuietRuntime())
    peak_live = peak_meaningful = 0
    def batch(count):
        nonlocal peak_live, peak_meaningful
        # Keep only this batch's retired timers so we can verify actual exits.
        retired = []
        for i in range(count):
            old = api._override_timer
            result = api.coordinator.execute(command(CommandAction.APPLY_OVERRIDE, duration=60 if i % 2 else 5))
            assert result.accepted
            api._sync_override_timer(result.status)
            current = api._override_timer
            assert current is not old
            if old is not None:
                assert old.finished.is_set()
                retired.append(old)
            timers = [t for t in threading.enumerate() if isinstance(t, threading.Timer)]
            meaningful = sum(not t.finished.is_set() for t in timers)
            peak_live = max(peak_live, len(timers))
            peak_meaningful = max(peak_meaningful, meaningful)
            assert meaningful == 1
        for timer in retired:
            timer.join(2)
            assert not timer.is_alive()
        return len([t for t in threading.enumerate() if isinstance(t, threading.Timer)])
    batch(20)
    tracemalloc.start()
    base = retained()
    first_live = batch(200)
    first = retained()
    second_live = batch(200)
    second = retained()
    tracemalloc.stop()
    last = api._override_timer
    api.shutdown()
    api.shutdown()
    last.join(2)
    remaining = sum(isinstance(t, threading.Timer) for t in threading.enumerate())
    assert remaining == 0
    return {"warmup_replacements": 20, "measured_replacements": 400,
            "peak_meaningful_timers": peak_meaningful,
            "peak_live_timer_threads_including_cancelled": peak_live,
            "settled_live_timer_threads_after_each_batch": [first_live, second_live],
            "timer_threads_after_shutdown": remaining,
            "retained_bytes_after_200": first - base,
            "retained_bytes_after_400": second - base,
            "second_batch_growth_bytes": second - first}


def cache_diagnostic():
    particle_templates.cache_clear()
    gc.collect()
    tracemalloc.start()
    base = retained()
    for seed in range(16):
        particle_templates(MAX_FIREFLIES, seed)
    first = retained()
    for seed in range(16, 256):
        particle_templates(MAX_FIREFLIES, seed)
    second = retained()
    info = particle_templates.cache_info()
    assert info.currsize == info.maxsize == 16
    tracemalloc.stop()
    particle_templates.cache_clear()
    return {"max_count": MAX_FIREFLIES, "cache_entries": info.currsize,
            "maximum_retained_templates": info.maxsize * MAX_FIREFLIES,
            "retained_bytes_full_cache": first - base,
            "retained_bytes_after_256_seeds": second - base,
            "growth_after_saturation_bytes": second - first}


def twinkle_diagnostic():
    context = SpatialContext.from_rows([
        {"global_index": i, "x": float(i % 50), "y": float(i // 50),
         "z": float(i % 7), "location_type": "spar"} for i in range(5000)
    ], center=(0, 0, 0), apex=(0, 0, 6))
    renderer = create_renderer("Twinkle", context, spawn_rate=MAX_TWINKLE_SPAWN_RATE)
    for i in range(20):
        frame = renderer.render(i / 30)
        assert len(frame.data) == 15000
    tracemalloc.start()
    base = retained()
    for i in range(20, 120):
        frame = renderer.render(i / 30)
    first = retained()
    for i in range(120, 220):
        frame = renderer.render(i / 30)
    second = retained()
    tracemalloc.stop()
    return {"leds": 5000, "spawn_rate": MAX_TWINKLE_SPAWN_RATE,
            "warmup_frames": 20, "measured_frames": 200,
            "retained_bytes_after_100": first - base,
            "retained_bytes_after_200": second - base,
            "second_batch_growth_bytes": second - first}


def main():
    errors = []
    with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")), \
         patch.object(socket.socket, "sendto", side_effect=AssertionError("network forbidden")), \
         patch.object(threading, "excepthook", side_effect=lambda args: errors.append(str(args.exc_value))):
        results = {"workers": worker_diagnostic(), "timers": timer_diagnostic(),
                   "fireflies_cache": cache_diagnostic(), "twinkle": twinkle_diagnostic()}
    assert not errors, errors
    results["uncaught_worker_errors"] = errors
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
