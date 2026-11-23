"""Hanging arch + rest, 0.40 mm print geometry, with generous fillets on every truss joint
(cosmetic). The hook zone is left exactly as fit-tested."""
import math, sys, warnings
warnings.filterwarnings("ignore")
import json
from shapely.geometry import box
from shapely.ops import unary_union
from shapely import contains_xy
import design
from design import Params, geometry, thickness_factor, thick_zone
from model import Bracket
from evaluate import evaluate
from make_catalog import to_part
from build123d import export_stl

R = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
W040, L040 = 0.68, 0.40
S040 = W040 - L040 * (1 - math.pi / 4)
p040 = lambda n: W040 + (n - 1) * S040
n_of = lambda w: int(round((w - design.PERIM_W) / design.PERIM_S)) + 1
best = json.load(open("out/search_T13_rest.json"))["best"]
for k in ("wall", "lace", "tie_w", "post_w"):
    best[k] = p040(n_of(best[k]))
best["spine_w"] = p040(2)
p = Params(**best)
g = geometry(p)
keep = box(-30, -15, 15, 30)                          # hook + root: no fillets here
truss = g.difference(keep)
fil = truss.buffer(R, join_style=1, quad_segs=16).buffer(-R, join_style=1, quad_segs=16)
fil = fil.intersection(box(0, -1e3, 1e3, 1e3)).union(truss)   # stay in front of the wall face
geom = unary_union([fil, g.intersection(keep)]).buffer(0)
m = Bracket(depth=p.depth, z_bottom=-130.0, h=0.4, t=p.t, rest=True)
r = evaluate(m, contains_xy(geom, m.grid.xc, m.grid.zc), tf=thickness_factor(m, p))
print(f"fillet R{R}: {r['mass']:.1f} g, safe {r['allow_N'] / 9.81:.1f} kg "
      f"{ {k: round(v / 9.81, 1) for k, v in r['limits_N'].items()} }")
part = to_part(geom, p.t, p.t_hook)
export_stl(part, "out/print/hanging_arch_rest_fillet.stl")
print("valid", part.is_valid, f"{part.volume * 1.27e-3:.1f} g")
