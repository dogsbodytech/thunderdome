# Dome Audio Reactor

This directory contains exploratory WLED Audio Sync tools. They are separate from the active [`3d-controller`](../../3d-controller/) application, which renders the complete 5,000-pixel dome in Python and sends five direct DDP frames to the WLED controllers.

These experiments temporarily use WLED's AudioReactive receive mode instead of the normal spatial DDP rendering path.

## Experiments

- [`pulse_generator.py`](pulse_generator.py) sends fake WLED Audio Sync V2 packets for basic network testing.
- [`sip-bridge/`](sip-bridge/) converts incoming Asterisk EAGI call audio into WLED Audio Sync packets.

## Pulse generator flow

```text
Linux server
  -> WLED Audio Sync V2 UDP packets
  -> test WLED controller in AudioReactive receive mode
  -> LEDs attached to that controller
```

## WLED setup

On a test controller:

1. Go to `Config -> Usermods -> AudioReactive`.
2. Set Audio Sync to `Receive`.
3. Use UDP port `11988`.
4. Save and reboot the controller if needed.
5. Select an AudioReactive effect, for example `Gravimeter`, `DJ Light` or `GEQ`.

The default target is multicast `239.0.0.1:11988`. For unicast testing, use one controller address from the current mapping in [`Software.md`](../../Software.md).

Do not assume controller 1 relays pixels to the other controllers. The current architecture sends a separate local DDP frame to each of the five controllers.

## Run the pulse generator

From this directory:

```bash
python3 pulse_generator.py
```

This sends a 120 BPM pulse to the WLED multicast address.

Useful examples:

```bash
# Slower pulse
python3 pulse_generator.py --bpm 60

# Stronger pulse
python3 pulse_generator.py --level 255

# Run for 30 seconds
python3 pulse_generator.py --duration 30

# Send directly to controller 1
python3 pulse_generator.py --target 192.168.12.10

# Force the source interface on a multi-homed host
python3 pulse_generator.py --interface-ip 192.168.12.123
```

## Troubleshooting

If WLED does not react:

1. Confirm the selected effect supports AudioReactive input.
2. Confirm Audio Sync is set to `Receive`, not `Send`.
3. Try unicast to a single controller.
4. Confirm the Linux host can reach the controller network.
5. Check whether the router or access point blocks multicast.
6. Keep the test separate from the normal DDP controller session.
