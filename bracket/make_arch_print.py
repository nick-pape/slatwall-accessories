"""Print-ready hanging arch + rest for the 0.40 mm STRUCTURAL HF0.6 profile."""
import json, math, sys, warnings
warnings.filterwarnings("ignore")
from dataclasses import replace
import numpy as np
from shapely import contains_xy
import design
from design import Params, geometry, thickness_factor, to_part
from model import Bracket
from evaluate import evaluate, diagnostics_png

W040, L040 = 0.68, 0.40
S040 = W040 - L040 * (1 - math.pi / 4)
p040 = lambda n: W040 + (n - 1) * S040
n_of = lambda w: int(round((w - design.PERIM_W) / design.PERIM_S)) + 1     # perimeter count at 0.15

best = json.load(open("out/search_T13_rest.json"))["best"]
for k in ("wall", "lace", "tie_w", "post_w"):
    best[k] = p040(n_of(best[k]))
best["spine_w"] = p040(2)                        # thin spine: keeps the tab seated if bumped upward
p = Params(**best)
print({k: round(v, 2) if isinstance(v, float) else v for k, v in best.items()})
m = Bracket(depth=p.depth, z_bottom=-130.0, h=0.4, t=p.t, rest=True)
geom = geometry(p)
r = evaluate(m, contains_xy(geom, m.grid.xc, m.grid.zc), tf=thickness_factor(m, p))
lim = {k: round(v / 9.81, 1) for k, v in r["limits_N"].items()}
print(f"FEA: {r['mass']:.1f} g, safe {r['allow_N'] / 9.81:.1f} kg per bracket, limits {lim}")
diagnostics_png(m, r, "out/arch_rest_040_diag.png")
from build123d import export_stl
part = to_part(p)
bb = part.bounding_box().size
print(f"part valid {part.is_valid}, {part.volume * 1.27e-3:.1f} g, bbox {bb.X:.1f} x {bb.Y:.1f} x {bb.Z:.1f}")
export_stl(part, "out/print/hanging_arch_rest.stl")
# tilt-in check with the real profile across two slots
sys.path.insert(0, "..")
from shapely import affinity
import slathook.tiltsim as ts
from slathook import SLOT_PITCH
w1 = ts.wall
ts.wall = lambda lip, cav_back=15.5, cav_top=21.0: w1(lip, cav_back, cav_top).intersection(
    affinity.translate(w1(lip, cav_back, cav_top), 0, -SLOT_PITCH))
for lip in (4.3, 5.0):
    print("tilt-in, lip", lip, "->", ts.can_insert(geom.simplify(0.3), lip, step=0.5, dth=1.0, cav_top=21.0, cav_back=15.5))
