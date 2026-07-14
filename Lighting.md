# Lighting and power

This document contains the design notes, wiring plans, controller configuration, layout files and supporting documentation for lighting the dome.

## Contents

- [LEDs](#leds)
- [Networking](#networking)
- [Layout](#layout)
- [Power](#power)
- [Controllers](#controllers)
- [WLED](#wled)

## LEDs

We went with WS2815 LEDs because they are 12 V and have a backup data line. They are RGB rather than RGBW, which is fine for the dome because it is all about colour.

We found waterproof LEDs with black wire. A 30 mm pitch means each string of 1,000 LEDs is 30 metres long, making it the right size for both a controller and the dome.

- Five [30 mm pitch pixel strings](https://www.aliexpress.com/item/1005009115166973.html): 12 V, 1,000 individually addressable RGB pixels, IP67 and black wire. The supplier listing describes the IC as WS2818.

| Wire                                      | Heat-shrink colour |
| ----------------------------------------- | ------------------ |
| Ground / 0 V                              | Black              |
| Backup data line                          | Green              |
| Main data line                            | Yellow             |
| +12 V (marked with a dot on the LED wire) | Red                |

Power injection points have been added to the middle and end of each string using the same heat-shrink colours. We should be able to reach full brightness this way.

**Important: The backup data line should be tied to GND so that it is not floating.** The first LED in the line mirrors the signal if required.

## Networking

We have borrowed a router from Dan for this.

- Gateway: 192.168.12.1
- Broadcast: 192.168.12.255
- Subnet mask: 255.255.255.0
- DHCP range: 192.168.12.200 to 192.168.12.254

| Controller | Connection | MAC address       | IP address |
| :--------- | :--------: | :---------------- | :--------- |
| Controller 1 | Wi-Fi    | 00:70:07:7f:bd:6c | [192.168.12.10](http://192.168.12.10) |
| Controller 1 | Wired    | 00:70:07:7f:bd:6f | [192.168.12.11](http://192.168.12.11) |
| Controller 2 | Wi-Fi    | 00:70:07:7f:b2:34 | [192.168.12.20](http://192.168.12.20) |
| Controller 3 | Wi-Fi    | 00:70:07:7f:b9:60 | [192.168.12.30](http://192.168.12.30) |
| Controller 4 | Wi-Fi    | 20:e7:c8:6c:4b:b8 | [192.168.12.40](http://192.168.12.40) |
| Controller 5 | Wi-Fi    | 00:70:07:7e:f5:5c | [192.168.12.50](http://192.168.12.50) |

There is a hidden SSID, used with permission from the organisers.

**Important: Follow [the EMF guidance on bringing wireless access points](https://www.emfcamp.org/about/internet#bringing-wireless-access-points).**

## Layout

The dome is large enough that five 30 metre strings of 1,000 pixels are a good fit. The intended layout is five separate data paths from the top of the dome down to the lower structure, with each controller driving one complete string.

![Diagram showing the paths the LED strings will follow](lighting/Layout.drawio.svg "Dome LED layout paths")

- Struts 1 to 12: 14.2 metres
- Struts 13 to 24: 13.8 metres
- Total: 28 metres

In practice, it is easier to start at strut 24 and work backwards, leaving 2 metres to hang down from the centre of the dome.

We would love to devise a layout in which one string starts where another ends. However, this is unlikely to be feasible without doubling back because of the five-pointed pentagons. We have left this as a project for another year :-)

The LEDs do not go on the bottom struts, so we can build the dome up to the last layer, install the LEDs and then install the last layer. However, it WILL BE HEAVY!

- 500 [blue cable ties](https://www.aliexpress.com/item/1005004609102546.html), sized 5 × 200 mm

## Power

Each 1,000 pixel string is rated at approximately 100 W, so the design uses one 12 V, 100 W PSU per string.

- Five 12 V, 100 W waterproof constant-voltage drivers: [TGR-12V-100W-IP67](https://cpc.farnell.com/tiger-power-supplies/tgr-12v-100w-ip67/led-driver-100w-ip67-12v-dc-8/dp/PW05064)

The difference between running 12 V DC and 230 V AC over distance is HUGE (Nikola Tesla was right, suck it Edison). If we wanted to run DC from a central location to all points on the dome, we would need to use 6 mm² cable!

According to the [WLED power calculator](https://wled-calculator.github.io/), the largest wire we need is 1.5 mm².

|                         | Start injection  | Middle injection | End injection    |
| ----------------------- | ---------------  | ---------------- | ---------------- |
| Wire length             | 226 cm           | 300 cm            | 753 cm           |
| Minimum cross-section   | 0.5 mm² (AWG 20) | 1 mm² (AWG 17)    | 1.5 mm² (AWG 15) |
| Maximum current         | 2.97 A           | 5.94 A             | 2.97 A            |
| Fuse rating             | 4 A              | 7.5 A              | 4 A               |
| Fuse colour             | Pink             | Brown              | Pink              |
| Maximum voltage drop    | 0.663 V          | 0.868 V            | 0.727 V           |

By positioning the five PSUs around the dome, we can keep the DC runs short and use the same 1.5 mm² cable for the 230 V AC runs to the PSUs.

- One [100 metre drum of 1.5 mm² two-core PVC flex](https://www.tlc-direct.co.uk/Products/CA1dot5F2.html), type 3182Y, white
- Ten [1,000 µF aluminium electrolytic capacitors](https://www.aliexpress.com/item/1005004400860497.html), rated for 25 V

**Important: Use a common ground everywhere. Place the capacitor as close as possible to the first LED and ensure that its polarity is correct.**

## Controllers

We chose the [QuinLED-Dig-Uno](https://quinled.info/2018/09/15/quinled-dig-uno/) because it includes the components required to make the ESP32 work, including a fuse, capacitor, logic-level converter and debounce resistor.

- Four [QuinLED-Dig-Uno controllers](https://shop.allnetchina.cn/products/quinled-dig-uno-v3r7-digital-led-controller?variant=39296748585062)
- One [QuinLED-Dig-Uno controller with Ethernet](https://shop.allnetchina.cn/products/quinled-dig-uno-v3r7-digital-led-controller?variant=39297009713254)

All controllers have been flashed with the QuinLED build of WLED: [WLED_16.0.0_Dig-Uno-V3.bin](lighting/WLED_16.0.0_Dig-Uno-V3.bin).

**Important: Mount each Dig-Uno as close as possible to the start of its LED string, not next to the PSU. The data line is fragile; the power line is not.**

## WLED

All controllers have been set up identically, except Controller 1, which is the main controller.

Controller configurations have been exported to the [lighting directory](lighting/) and should be kept up to date.

All controllers have been numbered 1 to 5 and their fallback SSIDs changed so that we can identify them.

Controllers 2 to 5 each control their own 1,000 LEDs.

Controller 1 is set up to control all 5,000 LEDs, with the 4,000 remote LEDs configured as virtual outputs pointing to the IP addresses of the other controllers.
