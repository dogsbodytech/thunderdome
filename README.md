# Addressable LED Dome for Electromagnetic Field
Every two years Dogsbody Technology attends the [Electromagnetic Field festival](https://www.emfcamp.org/) which can only be described as Glastonbury for geeks; and WE LOVE IT!

Each time we try to build something and each year we try and go bigger and better.

In 2024 [we built a huge geodesic dome](https://www.dogsbody.com/blog/electromagnetic-field-2024-the-best-yet/) and in 2026 we aim to cover the entire thing in 130 meters of 5,000 individually addressable RGB LEDs for interactive lighting, patterns, games, and general tinkering! 


## This Repo
This repository should (hopefully) contain all the design notes, wiring plans, controller configuration, layout files, and supporting documentation for project.


## The Dome
The dome is a 3v 5/8 Geodesic Dome, 6m in diameter and 3.5m high! It's constructed with a dome kit from [Build With Hubs](https://buildwithhubs.co.uk/) using 165 broom handles of three different lengths totalling over 181 metres.

Full information can be found in [dome/](dome/)


## The Lighting
The dome lighting is built around 5 x 30 meter LED strings. Each string has 1000 pixels at 30 mm spacing and is controlled by its own [QuinLED](https://quinled.info/) controller running [WLED](https://kno.wled.ge/).

Full information can be found in the [lighting/](lighting/)


## Tools
A list of tools required to build and maintain the dome
- 4mm hex/allen keys
- Soldering Iron
- Wire Strippers
- Knife
- Scissors
- Electrical Screwdriver Set
- Electric screwdriver and bits
- Drill bits
- Small saw for cutting poles
- Gloves
- Magnetic pots for small parts
- Fire Extinguisher
- Gaffer Tape
- Warning Signs
- high visibility vest x no of people
- Ladder?
- Wago connectors
- Red button?
- Magnet for if we drop stuff

## Shopping List
- Spare fuses
- Lots of wire

## ToDo
- Buy wire to connect all of this!
- How to make sound reactive?
- How to map LEDs to location?
- How to play games?


## Notes for contributors
This repo is intended to capture both final decisions and the reasoning behind them. When adding documentation, prefer practical notes that would help someone rebuild, debug, or safely operate the system later.


## Licence
licensed under the [MIT License](LICENSE)
