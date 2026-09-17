# Geometry

`assets/blender/thunderdome_3v_5_8_scaled.blend` is the authoritative editable physical model. `geometry/thunderdome_geometry.json` is its authoritative structural export: right-handed metres, base-centre origin, horizontal X/Y, Z up; hubs H001–H061; spars S001–S165. H061 is the apex. The graph contains 30 A, 55 B, and 80 C spars.

`geometry/routes/string_routes.json` is the authoritative LED traversal dataset: it records controller/string allocation and ordered hubs only. Geometry derives the spar IDs, types, lengths, and route summaries from each adjacent hub pair. Validate with `thunderdome geometry validate` and `thunderdome route validate`.
