# Software and interactive features

This doc should contain the code for controlling the dome lights via something other than WLED itself.

## Contents
- [WLED Mapping](#wled-mapping)
- [Audio Control](#audio-control)
- [SIP to Audio feed](#sip-to-audio-feed)


## WLED Mapping
WLED does have a way of natively [mapping LED's to areas of space](https://kno.wled.ge/advanced/mapping/) (on a 2D plane).

In order to map 5,000 LEDs with the correct spacing we calculated we need a grid of **at least** 600 x 600. This would give us 360,000 positions of which only 5,000 will be filled with LEDs and 355,000 would be empty.

The resulting map is just too large for WLED to store and use!


## Audio Control
The WLED controllers we have don't contain a microphone however we can [send audio from a laptop](https://kno.wled.ge/advanced/audio-reactive/#audio-sync-from-a-pc)


## SIP to Audio feed
Wouldn't it be cooll if anyone on site could use the EMF phone system to call the dome and light up the LED's via their voice or whatever the are near...

