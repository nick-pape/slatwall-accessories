# Slatwall accessories

Parametric [build123d](https://github.com/gumyr/build123d) slatwall parts, plus a few standalone
helpers. First set: PTFE tube routing for 3D printers.

> The hook in `slathook.py` was designed from my own measurements of my panel and refined over six
> fit tests. It is **not** a generic 3"-pitch slatwall hook. Check fit with `fit_test.stl` first.

## Parts (`stl/`, all in print orientation, no supports)

| File | What |
|---|---|
| `swivel_base.stl` | Hooks into a slot (designed to fit Proslat slatwall); bore + rear counterbore for the guide's axle |
| `swivel_guide_5.stl` | Block with 5 full 4 mm PTFE sleeves and a split snap axle. Hang the base, push the axle in from the front until it clicks; rotates to any angle |
| `sleeve_2..5.stl` | Standalone bundling sleeves for 2-5 tubes (not slatwall) |
| `fit_test.stl` | Small hook coupons to check fit on your panel before printing real parts |

`slatwall_ptfe_plate.3mf` / `hook_fit_test.3mf` are ready-made PrusaSlicer projects
(MK4 Input Shaper, HF0.6 nozzle, Prusament PETG; 0.15 mm / 0.40 mm layers).

PTFE holes are 4.4 mm (sliding fit for 4 mm OD tube in PETG) at 6.6 mm pitch, chamfered both ends.

## Hook (`slathook.py`)

Shared module for every accessory: `hooked_body(width, depth, z0)` returns a
BuildPart with the hook and a front body you can keep modelling into; `on_side()` puts it in
print orientation.

The default hook (`HOOK = "zF0"`) is a thick "Z": a flat 8 mm bar through the 10 mm slot,
back to 14.5 mm behind the face, then a 4 mm riser up to 19 mm, leaning forward 0.30 mm/mm,
with a 7 mm radius on the lower-back corner. Rules:

* Nothing in front of the wall may rise above the bar top (`NECK_TOP`), or it hits the slat
  above while you tilt the part in. Hang bodies below the slot.
* Solid wedge-shaped hooks don't go in: the face lip has to swing into the open space
  between the bar and the riser during insertion.

`tiltsim.py` is a small 2D search of the tilt-in motion (shapely) used to screen hook shapes
before printing; `hooksearch*.py` are the sweeps behind each fit test. `HOOKS` keeps every
variant tried, with the fit-test notes.

## Build

```sh
uv sync
uv run python ptfe_mount.py                 # -> stl/
uv run python make_3mf.py                   # -> slatwall_ptfe_plate.3mf (uses cfg.ini)
uv run python make_3mf.py hook_fit_test     # -> hook_fit_test.3mf     (uses cfg_fit.ini)
```

## Disclaimer

Independent hobby project. Not affiliated with, endorsed by, or made from any drawings or files
of any slatwall manufacturer. "Proslat" is a trademark of its owner and is used here only to
describe what these parts are designed to fit. Dimensions are my own measurements; no warranty --
don't hang anything valuable or heavy on printed parts without testing.
