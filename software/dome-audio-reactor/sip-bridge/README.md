# SIP audio bridge

This experimental bridge extends the existing WLED Audio Sync pulse test in the parent directory. It answers an incoming SIP call using Asterisk, reads the caller audio through EAGI, analyses its volume and frequency content, then sends WLED Audio Sync V2 packets.

This is not part of the active [`3d-controller`](../../../3d-controller/) rendering path. The production controller renders 5,000-pixel frames in Python and sends them directly to five WLED controllers using DDP. This bridge instead exercises WLED's separate AudioReactive receive mode as an exploratory feature.

## Flow

```text
EMF SIP account
  -> Asterisk
  -> EAGI Python script
  -> WLED Audio Sync UDP packets
  -> WLED AudioReactive effect
```

## Install

On Ubuntu or Debian:

```bash
sudo apt update
sudo apt install asterisk python3-venv

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Install the script for Asterisk:

```bash
sudo install -o asterisk -g asterisk -m 0755 \
  wled_call_bridge.py \
  /var/lib/asterisk/agi-bin/wled_call_bridge.py
```

When using the virtual environment, change the installed script's first line to the full path of `.venv/bin/python3`.

## Configure Asterisk

Copy and adapt the examples in [`asterisk/`](asterisk/). Replace the SIP username and password placeholders, then reload Asterisk:

```bash
sudo asterisk -rx 'pjsip reload'
sudo asterisk -rx 'dialplan reload'
sudo asterisk -rx 'pjsip show registrations'
```

The exact include directories vary between Asterisk packages, so the examples may need to be merged into `/etc/asterisk/pjsip.conf` and `/etc/asterisk/extensions.conf`.

## Configure WLED

On a test controller:

1. Set Audio Sync to `Receive` in the AudioReactive usermod settings.
2. Use UDP port `11988`.
3. Select an AudioReactive effect.
4. Keep this test separate from the normal DDP controller session.

The default destination is multicast `239.0.0.1:11988`. Use unicast when multicast is unavailable.

## Test without Asterisk

```bash
source .venv/bin/activate
python3 wled_call_bridge.py \
  --target 192.168.12.10 \
  --self-test \
  --duration 5 \
  --verbose
```

The self-test generates a pulsing tone and sends it through the same analysis and packet path used for call audio.

## Troubleshooting

Check that:

- the dialplan uses `EAGI`, not `AGI`
- the channel read format is `slin16`
- the selected WLED effect is AudioReactive
- the host can reach UDP port `11988` on the test controller
- another DDP session is not being used as part of the same test

Useful commands:

```bash
sudo journalctl -u asterisk -f
sudo asterisk -rx 'pjsip show endpoints'
sudo asterisk -rx 'pjsip show registrations'
```

## Status

The network self-test is suitable for validating the script and packet path. The complete flow still needs testing with the physical controller and an EMF SIP account.
