# xLights layout export

Export the canonical Thunderdome layout to an xLights `xlights_rgbeffects.xml` file:

```bash
thunderdome xlights generate --output /path/to/xlights_rgbeffects.xml
```

The export creates five 1,000-node **Poly Line** models, `Thunderdome String 1` through `Thunderdome String 5`, and the `Thunderdome` model group. Start channels derive from the canonical route allocation: `1`, `3001`, `6001`, `9001`, and `12001`.

It consumes canonical geometry and structured routes (use `--geometry-path` and `--route-path` to override them). LED allocation and the physical tail endpoint come directly from generated nominal positions; no generated positions file is required. Coordinates convert dome metres `(X, Y, Z)` to xLights units `(X*100, Z*100, Y*100)`.

When updating an existing file, unrelated models, groups, and root-level elements are preserved semantically. Previous Thunderdome models/group are replaced, and the exporter writes atomically after saving `xlights_rgbeffects.xml.thunderdome.bak`. Malformed input is left untouched.

This exports layout/model definitions only. It does not configure xLights controllers, sequences, or effects; configure controller definitions separately in xLights.
