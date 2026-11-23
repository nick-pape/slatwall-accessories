"""Evaluate + draw every catalog design.  uv run python run_catalog.py [names...]"""
import json, sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np
from shapely import contains_xy
from catalog import DESIGNS, thick_zone, hanging_arch, D
from model import Bracket
from evaluate import evaluate, diagnostics_png

T, T_HOOK = 12.0, 16.0

def run(name):
    style, fn, rest = DESIGNS[name]
    if name == "hanging_arch":
        geom, p = hanging_arch()
        t, th, zb = p.t, p.t_hook, p.foot_z - p.S - 6
    else:
        geom, t, th, zb = fn(), T, T_HOOK, -130.0
    m = Bracket(depth=D, z_bottom=zb, h=0.4, t=t, rest=rest)
    g = m.grid
    mk = contains_xy(geom, g.xc, g.zc)
    tf = np.where(contains_xy(thick_zone(), g.xc, g.zc), th / t, 1.0)
    t0 = time.time()
    r = evaluate(m, mk, tf=tf)
    lim = {k: v / 9.81 for k, v in r["limits_N"].items()}
    gov = min(lim, key=lim.get)
    out = dict(name=name, style=style, mass=r["mass"], kg=r["allow_N"] / 9.81, governs=gov, limits=lim,
               tip_mm_per_10kg=r["cases"]["uniform"]["tip_mm"], hook_pull_per_10kg=r["cases"]["uniform"]["hook_pull_N"],
               t=t, t_hook=th, rest=rest)
    out["kg_per_g"] = out["kg"] / out["mass"]
    print(f"{name:18s} {style:10s} {out['mass']:5.1f} g  {out['kg']:5.1f} kg  {out['kg_per_g']:.2f} kg/g  "
          f"governs: {gov:9s} ({', '.join(f'{k} {v:.1f}' for k, v in lim.items())}) [{time.time()-t0:.0f}s]", flush=True)
    diagnostics_png(m, r, f"out/cat_{name}_diag.png")
    import pickle
    pickle.dump(dict(geom=geom, t=t, t_hook=th, result=out), open(f"out/cat_{name}.pkl", "wb"))
    return out

if __name__ == "__main__":
    names = sys.argv[1:] or [n for n in DESIGNS if n != "bone"]
    res = [run(n) for n in names]
