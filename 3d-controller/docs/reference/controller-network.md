# Controller network reference

## Known controller destinations

The current controller allocation requires these five WLED hosts:

| Human controller | Address | Internal `string_id` | String/global range |
| ---: | --- | ---: | --- |
| 1 | `192.168.12.10` | 0 | string 1 / 0..999 |
| 2 | `192.168.12.20` | 1 | string 2 / 1000..1999 |
| 3 | `192.168.12.30` | 2 | string 3 / 2000..2999 |
| 4 | `192.168.12.40` | 3 | string 4 / 3000..3999 |
| 5 | `192.168.12.50` | 4 | string 5 / 4000..4999 |

Each local WLED destination receives local LEDs `0..999`. The Python controller sends the five slices directly; it does not send a complete frame to controller 1 for relay.

## Transport

- DDP: UDP/`4048`
- DDP payload: RGB8
- Current controller config chunk size: 480 LEDs
- Default host network details beyond the addresses below: **NOT CURRENTLY CAPTURED**

The public Lighting document records gateway `192.168.12.1`, broadcast `192.168.12.255`, mask `255.255.255.0`, DHCP range `192.168.12.200`–`192.168.12.254`, and an installation SSID. These are historical/public installation notes, not current live proof. Confirm them locally before relying on them, and do not add a guessed gateway, subnet, router, DHCP, SSID, or controller-host address to runtime documentation.

## Checks

Offline allocation check:

```bash
thunderdome controllers validate --controllers config/controllers.json
thunderdome controllers summary --controllers config/controllers.json
```

Network/HTTP check, used only in the physical runbook:

```bash
ping -c 1 192.168.12.10
thunderdome controller info --host 192.168.12.10
```

Repeat for the other four hosts. `ping` is not proof that WLED HTTP or DDP is configured; it only checks basic reachability.

## Links

- [Physical installation](physical-installation.md)
- [WLED Controller recovery](../setup-and-recovery/wled-controller.md)
- [First light and DDP](../runbooks/03-first-light-and-ddp.md)
