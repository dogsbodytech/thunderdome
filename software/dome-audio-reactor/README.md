# Dome Audio Reactor

This is the start of a Linux-side audio source for the dome.

The first step is deliberately simple: send fake WLED Audio Sync packets so we can confirm that the WLED controller reacts to network audio before adding SIP call handling.

## Current flow

```text
Linux server
  -> WLED Audio Sync V2 UDP packets
  -> WLED controller in AudioReactive receive mode
  -> Dome LEDs
```

## WLED setup

On the main WLED controller:

1. Go to `Config -> Usermods -> AudioReactive`.
2. Set Audio Sync to `Receive`.
3. Use UDP port `11988`.
4. Save and reboot the controller if needed.
5. Select an audio reactive effect, for example `Gravimeter`, `DJ Light`, `GEQ`, or similar.

The default target is multicast `239.0.0.1:11988`, which is what WLED Audio Sync uses.

For the current dome layout, controller 1 is the main controller and drives the other controllers using virtual LEDs. Start by testing against controller 1 only.

Known controller 1 addresses from the lighting notes:

- Wi-Fi: `192.168.12.10`
- Wired: `192.168.12.11`

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

# If multicast does not work, send directly to controller 1 wired
python3 pulse_generator.py --target 192.168.12.11

# If the server has multiple network interfaces, force the source interface
python3 pulse_generator.py --interface-ip 192.168.12.123
```

## Troubleshooting

If WLED does not react:

1. Confirm the WLED effect actually supports Audio Reactive.
2. Confirm Audio Sync is set to `Receive`, not `Send`.
3. Try unicast to the controller IP using `--target 192.168.12.11`.
4. Confirm the Linux server is on the same network as the controller.
5. Check whether the router or access point blocks multicast.
6. Try the wired controller IP if Wi-Fi multicast is unreliable.

## Next step

Once this is working, add a SIP bridge:

```text
EMF SIP account
  -> Asterisk
  -> Python EAGI script
  -> WLED Audio Sync packets
  -> Dome LEDs
```

The SIP bridge should reuse the packet sender from this pulse generator and replace the fake pulse with analysed call audio.
