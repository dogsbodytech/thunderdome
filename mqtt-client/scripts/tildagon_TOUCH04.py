#!/usr/bin/env python3
"""Handler for open/dogsbody/dome/TOUCH04. argv[1] = MQTT payload.

Brightness only, step 4/12 on a log curve:
round(4 * (255/4)^((n-1)/11)) = 12.
"""
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Set dome brightness to 12/255 (step 4/12, dim to full).
subprocess.run([
    "thunderdome", "controller", "brightness",
    "--host", os.environ["WLED_HOST"],
    "12",
])
