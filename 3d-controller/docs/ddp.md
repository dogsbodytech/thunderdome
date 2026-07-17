# DDP

Python chooses RGB values for each physical LED and sends a linear full frame to WLED over UDP DDP, default port **4048**. WLED does not know XYZ coordinates. DDP packets use RGB8 payloads, byte offsets, and configurable chunks (default 480 LEDs). Start at low brightness and test with `clear`, `solid`, `pixel`, and `range` before animation.
