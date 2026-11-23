"""Size every catalog design for the same job: least mass with allowable load >= TARGET kg.
Coordinate descent over each design's own parameters plus print height t / hook height."""
import json, sys, warnings
warnings.filterwarnings("ignore")
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from design import perims as P

TARGET = 15.0
COMMON = {"t": [8, 10, 12, 14, 16, 20], "t_hook": [12, 16, 20, 25]}
SPACES = {
    "minimal_two_bars": {"w_strut": [4, 6, 8, 10, 12, 14], "w_chord": [3, 4, 5, 6, 8]},
    "salginatobel": {"n_cols": [5, 7, 9, 11], "rib0": [6, 8, 10, 12, 14], "rib1": [3, 4, 5, 6, 8],
                     "ch": [3, 4, 5, 6], "col_w": [P(2), P(3), P(4), P(6)]},
    "victorian": {"ch": [3, 4, 5, 6, 8], "post": [3, 4, 5, 7], "brace": [4, 5, 6, 8, 10], "ring": [P(2), P(3), P(4)]},
    "forth_bridge": {"n": [4, 5, 6, 8], "ch": [3, 4, 5], "bottom": [4, 5, 6, 8, 10], "lattice": [P(2), P(3), P(4)],
                     "post_w": [P(2), P(3), P(4), P(6)]},
    "twin_triangle": {"S": [8, 10, 12, 16], "wall": [P(2), P(3), P(4), P(5)], "lace": [P(2), P(3)],
                      "lace_pitch": [6, 8, 10, 12], "n_posts": [3, 5, 7], "post_w": [P(2), P(3), P(4)], "ch": [3, 4, 5]},
    "gaudi_tree": {"levels": [2, 3], "leaf_w": [P(2), P(3), P(4), P(6)], "grow": [0.5, 0.62, 0.75, 0.9],
                   "ch": [3, 4, 5], "curl": [0.08, 0.18, 0.3]},
}
START = {"minimal_two_bars": {"w_strut": 8, "w_chord": 5}, "salginatobel": {}, "victorian": {}, "forth_bridge": {},
         "twin_triangle": {}, "gaudi_tree": {}}

def score(args):
    name, kw = args
    import warnings; warnings.filterwarnings("ignore")
    import numpy as np
    from shapely import contains_xy
    from catalog import DESIGNS, thick_zone, D
    from model import Bracket
    from evaluate import evaluate
    _, fn, rest = DESIGNS[name]
    kw = dict(kw); t = kw.pop("t"); th = kw.pop("t_hook")
    try:
        geom = fn(**kw)
        m = Bracket(depth=D, z_bottom=-130.0, h=0.4, t=t, rest=rest)
        g = m.grid
        tf = np.where(contains_xy(thick_zone(), g.xc, g.zc), th / t, 1.0)
        r = evaluate(m, contains_xy(geom, g.xc, g.zc), tf=tf)
        kg, mass = r["allow_N"] / 9.81, r["mass"]
        lim = {k: v / 9.81 for k, v in r["limits_N"].items()}
    except Exception as e:
        return dict(obj=1e9, err=repr(e))
    return dict(obj=mass * max(1.0, TARGET / max(kg, 1e-3)) ** 2, kg=kg, mass=mass, lim=lim)

def search(name, ex):
    space = dict(SPACES[name], **COMMON)
    import inspect
    from catalog import DESIGNS
    defaults = {k: v.default for k, v in inspect.signature(DESIGNS[name][1]).parameters.items()}
    best = {k: defaults.get(k, START[name].get(k)) for k in SPACES[name]}
    best.update(START[name]); best.update(t=12, t_hook=16)
    cur = score((name, best)); seen = {json.dumps(best, sort_keys=True)}
    for rnd in range(4):
        improved = False
        for k, vals in space.items():
            cands = [dict(best, **{k: v}) for v in vals if v != best[k]]
            cands = [c for c in cands if json.dumps(c, sort_keys=True) not in seen]
            for c, res in zip(cands, ex.map(score, [(name, c) for c in cands])):
                seen.add(json.dumps(c, sort_keys=True))
                if res["obj"] < cur["obj"] - 1e-6:
                    cur, best, improved = res, c, True
        print(f"{name:16s} round {rnd}: {cur.get('mass', 0):.1f} g, {cur.get('kg', 0):.1f} kg "
              f"({cur.get('kg', 0) / max(cur.get('mass', 1), 1e-9):.2f} kg/g) {cur.get('lim')}", flush=True)
        if not improved:
            break
    return dict(best=best, result=cur)

if __name__ == "__main__":
    names = sys.argv[1:] or list(SPACES)
    out = {}
    with ProcessPoolExecutor(5) as ex:
        for n in names:
            out[n] = search(n, ex)
            json.dump(out, open("out/catalog_sized.json", "w"), indent=1)
    print("DONE", flush=True)
