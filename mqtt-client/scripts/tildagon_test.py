#!/usr/bin/env python3
"""Example handler for open/dogsbody/dome/test. argv[1] = MQTT payload.

Copy this to tildagon_<name>.py for a new button. No hardware needed — just
prints, so it works as a standalone smoke test.
"""
import sys

payload = sys.argv[1] if len(sys.argv) > 1 else ""
print(f"tildagon test fired: payload={payload!r}")
