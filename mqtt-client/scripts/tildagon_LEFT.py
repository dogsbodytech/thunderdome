#!/usr/bin/env python3
"""Handler for open/dogsbody/dome/LEFT. argv[1] = MQTT payload."""
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
payload = sys.argv[1] if len(sys.argv) > 1 else ""  # wire in per button as needed

subprocess.run([
    "thunderdome", "ddp", "range",
    "--host", os.environ["WLED_HOST"], "0", "4999",
    "--color", "00FF00",
    "--brightness", "32",
])
