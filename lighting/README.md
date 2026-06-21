## This Directory
This directory should (hopefully) contain all the design notes, wiring plans, controller configuration, layout files, and supporting documentation for the lighting of the dome.


## LEDs
We went with WS2818 LEDS as these are 12V with a backup data line. They are RGB (not RGBW) however this should be fine for the dome as it's all about the colour.

We found some lovely waterproof LED's with black wire. A 30mm pitch means each length of 1000 LEDs is 30meters and is perfect for a controller each as well as a being the right size for the dome.

- 5 x [30mm Pitch WS2818 Pixel String DC12V 1000ct Pixels RGB IC Addressable IP67 Black Wire](https://www.aliexpress.com/item/1005009115166973.html?spm=a2g0o.cart.0.0.549b38dazIQOVE&mp=1&pdp_npi=6%40dis%21GBP%21GBP%2063.53%21GBP%2060.99%21%21GBP%2060.99%21%21%21%40211b615317761987215187255e9494%2112000047971421451%21ct%21UK%21750918518%21%214%210%21)


## Networking
We have borrowed a router from Dan to do this.

- Gateway: 192.168.12.1
- Broadcast: 192.168.12.255
- Subnet Mask: 255.255.255.0
- DHCP Range: 192.168.12.200 - 192.168.12.254

| Controller # | Connection | MAC               | IP Addr       |
| :----------- | :--------: | :---------------: | ------------- |
| Controller 1 | WiFi       | 00:70:07:7f:bd:6c | [192.168.12.10](http://192.168.10) |
| Controller 1 | Wired      | 00:70:07:7f:bd:6f | [192.168.12.11](http://192.168.11) |
| Controller 2 | WiFi       | 00:70:07:7f:b2:34 | [192.168.12.20](http://192.168.20) |
| Controller 3 | WiFi       | 00:70:07:7f:b9:60 | [192.168.12.30](http://192.168.30) |
| Controller 4 | WiFi       | 20:e7:c8:6c:4b:b8 | [192.168.12.40](http://192.168.40) |
| Controller 5 | WiFi       | 00:70:07:7e:f5:5c | [192.168.12.50](http://192.168.50) |

There is a hidden ssid used with permission of the organisers.

**Important: Follow [the EMF guide regarding bringing wireless access points](https://www.emfcamp.org/about/internet#bringing-wireless-access-points).**


## Layout
The dome is large enough that five 30 metre strings of 1000 pixels are a good fit. The intended layout is five separate data paths from the top of the dome down to the lower structure, with each controller driving one complete string.

![Disagram showing the path the LED strings will follow](Layout.drawio.svg "Dome LED Layout Path")

- Struts 1 to 12 = 14.2 meters
- Struts 13 to 24 =  13.8 meters

We have to inject power at each end of the string as well as in the middle. Handily (after a lot of working out) we managed to get the start/end in the same location/node as the middle of the string (between strut 12 & 13). This means we only need to inject power at two physical locations across the dome per string

When building the dome we can build the first three layers and then install the LED strings from their middle point at the centre of each pentagon. Half the string can then be installed up to the top of the dome and the other half later when the dome is built (which is all within arms reach). 

- 400 x [5x200mm blue zip ties](https://www.aliexpress.com/item/1005004609102546.html?spm=a2g0o.detail.0.0.1ba2HaZXHaZXB1&mp=1&pdp_npi=6%40dis%21GBP%21GBP%203.68%21GBP%203.59%21%21GBP%203.59%21%21%21%40211b61ae17762036871267314e801f%2112000053124186326%21ct%21UK%21750918518%21%211%210%21)

## Power
Each 1000 pixel string is rated at approximately 100W, so the design uses one 12V 100W PSU per string.

- 5 x 12V 100W waterproof constant voltage drivers: [TGR-12V-100W-IP67](https://cpc.farnell.com/tiger-power-supplies/tgr-12v-100w-ip67/led-driver-100w-ip67-12v-dc-8/dp/PW05064)
- 1 x [10m 12AWG 2-pin Black Red Wire](https://www.aliexpress.com/item/1005006614755156.html?spm=a2g0o.detail.0.0.1dcbSqVHSqVHfs&mp=1&pdp_npi=6%40dis%21GBP%21GBP%2033.20%21GBP%2032.99%21%21GBP%2032.99%21%21%21%40211b612817761999643306390ebf72%2112000037830294890%21ct%21UK%21750918518%21%211%210%21)
- 1 x [10m 18AWG 2-pin Black Red Wire](https://www.aliexpress.com/item/1005006614755156.html?spm=a2g0o.detail.0.0.1dcbSqVHSqVHfs&mp=1&pdp_npi=6%40dis%21GBP%21GBP%209.15%21GBP%209.09%21%21GBP%209.09%21%21%21%40211b612817762000535478996ebf72%2112000037830294866%21ct%21UK%21750918518%21%211%210%21)
- 10 x [25V Aluminium Capacitor 1000UF](https://www.aliexpress.com/item/1005004400860497.html?spm=a2g0o.detail.0.0.12fe5D8g5D8gt0&mp=1&pdp_npi=6%40dis%21GBP%21GBP%202.63%21GBP%202.61%21%21GBP%202.61%21%21%21%402103847817762032518165181e3c64%2112000029045776767%21ct%21UK%21750918518%21%211%210%21)

Assuming that we have the power supplies in one location (1 meter away from the edge of the dome) 
| String   | Length to edge of dome | 
| ----     | ---------------------- |
| String 1 | 1.0 m                  | 
| String 2 | 4.5 m                  |
| String 3 | 4.5 m                  |
| String 4 | 8.0 m                  |
| String 5 | 8.0 m                  |

- The distance from the edge of the dome to the start/middle point at the centre of each pentagon is 2.263 meters
- The distance from the edge of the dome to the top point is 5.538 meters, adding the ~0.8 meters that maybe remaining = 6.338 meters

According to the [WLED power calculator](https://wled-calculator.github.io/) the largest wire we need is 1.5 mm2 but what about the sire from the PSUs to the bottom of the dome?

|                         | Start Injection  | Middle Injection | End Injection    |
| ----------------------- | ---------------  | ---------------- | ---------------- |
| Wire length             | 226 cm           | 226 cm           | 633 cm           |
| Min. wire cross-section | 0.5 mm2 (AWG 20) | 1 mm2 (AWG 17)   | 1.5 mm2 (AWG 15) |
| Max. current            | 3.28 A           | 6.56 A           | 3.28 A           |
| Fuse rated value        | 4 A              | 7.5 A            | 4 A              |
| Fuse color              | pink             | brown            | pink             |
| Max. voltage drop       | 0.732 V          | 0.750 V          | 0.690 V          |

**Important: Common ground everywhere. Capacitor should go as close to the first LED as possible and ensure correct polarity.**


## Controllers
We have decided on the [QuinLED-Dig-Uno](https://quinled.info/2018/09/15/quinled-dig-uno/) as it includes all the gubbins required to make the ESP32 work such as fuse, capacitor, logic convertor and de-bounce resistor.

- 4 x [QuinLED-Dig-Uno](https://shop.allnetchina.cn/products/quinled-dig-uno-v3r7-digital-led-controller?variant=39296748585062)
- 1 x [QuinLED-Dig-Uno with Ethernet](https://shop.allnetchina.cn/products/quinled-dig-uno-v3r7-digital-led-controller?variant=39297009713254)

**Important: Mount each Dig-Uno as close as possible to the start of its LED string, not next to the PSU. The data line is fragile, the power line is not.**

All controllers have been flashed with the latest version of WLED compiled by QuinLED [WLED_16.0.0_Dig-Uno-V3.bin](controller/WLED_16.0.0_Dig-Uno-V3.bin).


## WLED



[https://kno.wled.ge/advanced/mapping/](https://kno.wled.ge/advanced/mapping/)



