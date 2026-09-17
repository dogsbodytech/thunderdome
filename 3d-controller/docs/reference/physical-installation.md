# Physical installation reference

This is the controller-local physical lookup, not a replacement for the wider construction and electrical documentation.

## Dome facts used by the controller

The tracked geometry is a **3V 5/8** dome with **61 hubs**, **165 spars**, and **105 faces**. The public construction document records a diameter of **6 m** and height of about **3.5 m**. The five routed LED strings contain 1,000 LEDs each, for 5,000 logical LEDs total.

The current geometry export is the software authority for coordinates. H061 is the apex. Generated positions use nominal mathematical coordinates through hub centres. Each string has 937 dome LEDs and 63 tail LEDs in the current generated data; tails descend below the apex and share its XY coordinate.

## Physical lighting evidence

The public project records:

- 30 mm pitch, 12 V RGB addressable pixel strings;
- five 30 m strings of 1,000 pixels;
- QuinLED-Dig-Uno controllers;
- one 12 V, 100 W PSU per string;
- power injection at start, middle, and end of each string;
- five separate data paths, one controller per string.

These are installation records, not a substitute for checking an unknown/rebuilt physical setup. Confirm current/power configuration before normal brightness `255`.

Detailed sources:

- [Dome construction and assembly](https://github.com/dogsbodytech/thunderdome/blob/main/Dome.md)
- [Lighting, power, controller hardware and wiring](https://github.com/dogsbodytech/thunderdome/blob/main/Lighting.md)
- [LED layout drawing](https://github.com/dogsbodytech/thunderdome/blob/main/lighting/Layout.drawio.svg)
- [Dome assembly drawing](https://github.com/dogsbodytech/thunderdome/blob/main/dome/Assembly.drawio.svg)

## Controller/string mapping

| Human controller | WLED address | Internal `string_id` | Start hub | Global LEDs | Local LEDs |
| ---: | --- | ---: | --- | --- | --- |
| 1 | `192.168.12.10` | 0 | H032 | 0..999 | 0..999 |
| 2 | `192.168.12.20` | 1 | H033 | 1000..1999 | 0..999 |
| 3 | `192.168.12.30` | 2 | H034 | 2000..2999 | 0..999 |
| 4 | `192.168.12.40` | 3 | H035 | 3000..3999 | 0..999 |
| 5 | `192.168.12.50` | 4 | H031 | 4000..4999 | 0..999 |

The start-hub order is not numerical: controller 5 starts at H031. Human numbers 1–5 are not the same as internal `string_id` values 0–4.

## Apex/tail relationship

Every authoritative route ends at H061. The first tail LED is the next nominal 30 mm position after the route endpoint. It is below H061 by the residual pitch distance, so tails are real XYZ records rather than a flat centre marker. Effects include tails by default; `--exclude-tail` removes them from effect selection.

## Physical gaps

The following are **NOT CURRENTLY CAPTURED** in this controller component:

- controller-host hostname or IP;
- confirmed current router/AP administration details;
- a verified physical PSU isolation/power-off sequence;
- a verified association of the Ethernet-capable Dig-Uno to a human controller number;
- a current live audit proving that every deployed device still matches its public export.

Do not infer these values from the IP table or from a device name.
