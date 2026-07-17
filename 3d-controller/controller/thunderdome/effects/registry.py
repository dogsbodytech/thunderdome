"""Authoritative effect catalogue for CLI and automatic showcase mode."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
@dataclass(frozen=True)
class EffectRegistration:
    name:str; description:str; auto_options:Mapping[str,object]; supports_auto:bool=True
REGISTRY=tuple(EffectRegistration(*x) for x in (
 ('clock-hand','rotating radial XY hand',{'rotation_seconds':12,'width_mm':300}),
 ('expanding-rings','true XYZ spherical shell',{'origin':'centre','speed_mps':1.,'thickness_mm':250}),
 ('height-wave','moving horizontal Z band',{'direction':'bounce','speed_mps':.8,'height_mm':300}),
 ('fire','rising turbulent flame field',{'speed':1.,'flame_height_m':2.5,'turbulence':.65,'cooling':.35,'palette':'fire'}),
 ('rotating-plane','soft signed-distance rotating plane',{'axis':'tilted','rotation_seconds':10,'thickness_mm':220,'trail_degrees':20}),
 ('radar','angular XY sweep',{'rotation_seconds':8,'beam_width_degrees':12,'trail_degrees':35}),
 ('aurora','flowing multi-frequency luminous bands',{'speed':.25,'scale':1.2,'band_width':.45,'palette':'mixed'}),
 ('fireflies','deterministic moving 3D glow particles',{'count':25,'speed':.35,'glow_radius_mm':300,'lifetime_seconds':8}),
))
BY_NAME={x.name:x for x in REGISTRY}
PRESETS={
 'calm':('height-wave','aurora','fireflies','expanding-rings'),
 'energetic':('clock-hand','fire','rotating-plane','radar','aurora','fireflies'),
}
def get(name:str)->EffectRegistration:
 if name not in BY_NAME: raise ValueError(f"unknown effect {name!r}; valid choices: {', '.join(BY_NAME)}")
 return BY_NAME[name]
