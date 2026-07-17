# Thunderdome LED String Routes

This file defines the authoritative physical hub routes for all five LED strings.

The LED strings run along dome spars and physically pass through the centre of every hub on the route.

For mapping purposes:

- each adjacent hub pair represents one physical spar;
- the string path is a continuous polyline through hub centres;
- no extra hub-transition length is added;
- LED pitch continues through the centre of each hub;
- strings may pass through the same hub;
- strings must not share a spar;
- all five strings terminate at apex hub `H061`;
- faces are irrelevant to LED routing.

## Controller and LED index allocation

| Controller | String ID | Start hub | Global LED indexes |
|---:|---:|---|---:|
| 1 | 0 | `H032` | `0–999` |
| 2 | 1 | `H033` | `1000–1999` |
| 3 | 2 | `H034` | `2000–2999` |
| 4 | 3 | `H035` | `3000–3999` |
| 5 | 4 | `H031` | `4000–4999` |

The physical rotational order is clockwise when viewed from above:

```text
H032 → H033 → H034 → H035 → H031 → H032
```

In the Blender coordinate system, this corresponds to rotations around the Z axis of:

```text
0°, -72°, -144°, -216°, -288°
```

## String 1

Controller: `1`  
String ID: `0`  
Global LED indexes: `0–999`  
Start hub: `H032`  
End hub: `H061`

```text
H032 > H019 > H018 > H026 > H017 > H037 > H026 > H038 >
H018 > H032 > H039 > H047 > H032 > H038 > H037 > H052 >
H038 > H047 > H052 > H057 > H047 > H053 > H057 > H058 > H061
```

## String 2

Controller: `2`  
String ID: `1`  
Global LED indexes: `1000–1999`  
Start hub: `H033`  
End hub: `H061`

```text
H033 > H021 > H020 > H027 > H019 > H039 > H027 > H040 >
H020 > H033 > H041 > H048 > H033 > H040 > H039 > H053 >
H040 > H048 > H053 > H058 > H048 > H054 > H058 > H059 > H061
```

## String 3

Controller: `3`  
String ID: `2`  
Global LED indexes: `2000–2999`  
Start hub: `H034`  
End hub: `H061`

```text
H034 > H023 > H022 > H028 > H021 > H041 > H028 > H042 >
H022 > H034 > H043 > H049 > H034 > H042 > H041 > H054 >
H042 > H049 > H054 > H059 > H049 > H055 > H059 > H060 > H061
```

## String 4

Controller: `4`  
String ID: `3`  
Global LED indexes: `3000–3999`  
Start hub: `H035`  
End hub: `H061`

```text
H035 > H025 > H024 > H029 > H023 > H043 > H029 > H044 >
H024 > H035 > H045 > H050 > H035 > H044 > H043 > H055 >
H044 > H050 > H055 > H060 > H050 > H051 > H060 > H056 > H061
```

## String 5

Controller: `5`  
String ID: `4`  
Global LED indexes: `4000–4999`  
Start hub: `H031`  
End hub: `H061`

```text
H031 > H017 > H016 > H030 > H025 > H045 > H030 > H036 >
H016 > H031 > H037 > H046 > H031 > H036 > H045 > H051 >
H036 > H046 > H051 > H056 > H046 > H052 > H056 > H057 > H061
```

## Structural validation expectations

Each route must satisfy:

- 25 ordered hubs;
- 24 spar segments;
- every adjacent hub pair is connected by exactly one spar;
- no spar is repeated within the same string;
- no spar is shared between different strings;
- all routes have the same spar-type sequence;
- all routes have the same structural length within floating-point tolerance;
- all routes end at `H061`.

Across all five routes, the expected total is:

```text
120 route segments
120 unique spars
0 shared spars
```

The remaining 45 dome spars do not carry LEDs.

## LED placement assumptions

The initial XYZ generator should use these physical assumptions:

```text
LED pitch: 0.030 m
First LED offset: 0.000 m
Route model: continuous polyline through hub centres
Hub transition model: no additional transition length
Tail start: H061
Tail direction: vertically downward along negative Z
```

An LED positioned exactly at a route distance that reaches a hub should use the XYZ coordinate of that hub centre.

The string continues through the hub centre and immediately proceeds along the next spar.

No smoothing curve, corner-cutting, hub-radius correction, or additional cable length should be introduced unless later physical measurements require it.

## Global LED indexing

For zero-based `string_id`:

```text
global_index = string_id * 1000 + string_index
```

Where:

```text
string_id:    0–4
string_index: 0–999
global_index: 0–4999
```

Any LEDs remaining after the final dome route distance are part of that string's hanging tail from `H061`.
