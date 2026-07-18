#!/usr/bin/env python3
"""Handler for open/dogsbody/dome/TOUCH07. argv[1] = MQTT payload.

Brightness only, step 7/12 on a log curve:
round(4 * (255/4)^((n-1)/11)) = 39.
"""
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Set dome brightness to 39/255 (step 7/12, dim to full).
subprocess.run([
    "thunderdome", "controller", "brightness",
    "--host", os.environ["WLED_HOST"],
    "39",
])
