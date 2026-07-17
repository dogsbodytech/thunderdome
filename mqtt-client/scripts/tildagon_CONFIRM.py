#!/usr/bin/env python3
"""Handler for open/dogsbody/dome/CONFIRM. argv[1] = MQTT payload."""
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Fill the whole dome solid white.
subprocess.run([
    "thunderdome", "ddp", "solid",
    "--host", os.environ["WLED_HOST"],
    "--color", "FFFFFF",
    "--brightness", "32",
])
