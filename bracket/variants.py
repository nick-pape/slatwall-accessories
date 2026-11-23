"""Several generator shapes for one shelf size on a single plate, for inspection."""
import sys, subprocess, warnings
warnings.filterwarnings("ignore")
from shelf_gen import frame, evaluate_geom, SIZES, candidates, to_part_lip
from make_catalog import to_part
from build123d import export_stl
W, D = float(sys.argv[1]), float(sys.argv[2])
load = (W / 10) * (D / 10) * 20 / 1000
LIP = float(sys.argv[3]) if len(sys.argv) > 3 else 1.5
# the generator's best L and best triangle, each with and without the lip
from shelf_gen import generate
cands = dict(candidates(D))
Ls = {k: v for k, v in cands.items() if k.startswith("L")}
Ts = {k: v for k, v in cands.items() if not k.startswith("L")}
V = {}
for group in (Ls, Ts):
    if group:
        best = None
        for k, kw in group.items():
            for perims, S in SIZES:
                g, bottom = frame(D, S=S, perims=perims, **kw)
                kg, mass, lim = evaluate_geom(g, D, W, bottom, kw.get("rest", False))
                if kg >= load:
                    if best is None or mass < best[1]:
                        best = (k, mass, dict(kw, S=S, perims=perims))
                    break
        if best:
            V[best[0]] = best[2]
            V[best[0] + "_lip"] = dict(best[2], _lip=True)
stls = []
for name, kw in V.items():
    kw = dict(kw); lip = LIP if kw.pop("_lip", False) else 0.0
    g, bottom = frame(D, **kw)
    kg, mass, lim = evaluate_geom(g, D, W, bottom, kw.get("rest", False))
    perims, S = kw["perims"], kw["S"]
    print(f"{name:8s} {perims}p/{S:.0f}mm safe {kg:6.1f} kg (rated {load:.1f}), {mass:5.0f} g solid-eq, limited by {min(lim, key=lim.get)}", flush=True)
    stl = f"out/print/var_{name}_{W:.0f}x{D:.0f}.stl"
    export_stl(to_part_lip(g, W, D, lip), stl); stls.append(stl + ":1")
subprocess.run([sys.executable, "../tools/make_3mf.py", f"out/print/variants_{W:.0f}x{D:.0f}.3mf", "../tools/prusa/cfg_extruded.ini", *stls], check=True)
