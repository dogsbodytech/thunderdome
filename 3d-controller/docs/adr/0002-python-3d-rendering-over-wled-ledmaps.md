# ADR 0001: Python 3D rendering over WLED ledmaps

## Decision

Use authoritative XYZ coordinates and Python-rendered linear RGB frames sent through DDP.

## Rejected primary approach

WLED 2D `ledmap.json`.

## Reasons

Ledmaps are 1D/2D remapping structures, not arbitrary 3D geometry. They cannot retain height; hanging tails overlap in top-down projection; grid uniqueness forces artificial nudging; and 3D effects require XYZ access. DDP already supports efficient complete frames.

## WLED retained role

WLED remains the LED output driver and network receiver, provides brightness/current safeguards, supports native fallback effects, and exposes status/configuration through HTTP.
