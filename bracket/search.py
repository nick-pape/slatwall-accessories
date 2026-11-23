"""Coordinate-descent search over the arch bracket parameters, full FEA per candidate.
Objective: least mass with allowable load >= TARGET kg per bracket (penalised if short)."""
import json, sys, time
from dataclasses import replace, asdict
from concurrent.futures import ProcessPoolExecutor
import numpy as np

TARGET = float(sys.argv[1]) if len(sys.argv) > 1 else 13.0
from design import perims as P
SPACE = {
    "t":          [6, 8, 10, 12, 14],
    "t_hook":     [12, 16, 20, 25],
    "S":          [8, 10, 12, 14, 16, 18, 20],
    "ctrl":       [0.2, 0.3, 0.4, 0.5, 0.6],
    "foot_z":     [-70, -85, -100, -108],
    "n_panels":   [2, 3, 4, 5],
    "wall":       [P(2), P(3), P(4), P(5)],
    "lace":       [P(2), P(3)],
    "lace_pitch": [7, 9, 11, 14],
    "tie_w":      [P(2), P(3), P(4), P(6)],
    "post_w":     [P(2), P(3), P(4), P(6)],
    "chord_h":    [2.5, 3.0, 4.0, 5.0],
    "spine_w":    [0.0, P(2), P(3), P(4), P(6)],
}

def score(kw):
    import warnings; warnings.filterwarnings("ignore")
    from design import Params, geometry, mask, thickness_factor
    from model import Bracket
    from evaluate import evaluate
    p = Params(**kw)
    try:
        m = Bracket(depth=p.depth, z_bottom=-130.0 if p.rest else p.foot_z - p.S - 6, h=0.4, t=p.t, rest=p.rest)
        r = evaluate(m, mask(m, geometry(p)), tf=thickness_factor(m, p))
        kg, g = r["allow_N"] / 9.81, r["mass"]
        lim = {k: v / 9.81 for k, v in r["limits_N"].items()}
    except Exception as e:
        return dict(kw=kw, obj=1e9, err=str(e))
    obj = g * max(1.0, TARGET / max(kg, 1e-3)) ** 2       # mass, penalised if under target
    return dict(kw=kw, obj=obj, kg=kg, mass=g, lim=lim)

if __name__ == "__main__":
    from design import Params
    REST = "--rest" in sys.argv
    start = json.load(open("out/search_T15.json"))["best"]
    best = {k: start.get(k, getattr(Params(), k)) for k in SPACE}
    if REST:
        best["rest"] = True
    cur = score(best)
    print(f"start {cur['mass']:.1f} g {cur['kg']:.1f} kg obj {cur['obj']:.1f}", flush=True)
    seen = {json.dumps(best, sort_keys=True): cur}
    with ProcessPoolExecutor(4) as ex:
        for rnd in range(3):
            improved = False
            for k, vals in SPACE.items():
                cands = [dict(best, **{k: v}) for v in vals if v != best[k]]
                cands = [c for c in cands if json.dumps(c, sort_keys=True) not in seen]
                for res in ex.map(score, cands):
                    seen[json.dumps(res["kw"], sort_keys=True)] = res
                    if res["obj"] < cur["obj"] - 1e-6:
                        cur, best, improved = res, res["kw"], True
                print(f"r{rnd} {k:10s} -> {best[k]!s:6.6s} | {cur['mass']:.1f} g, {cur['kg']:.1f} kg "
                      f"({cur['kg'] / cur['mass']:.2f} kg/g) lim {', '.join(f'{a} {b:.1f}' for a, b in cur['lim'].items())}",
                      flush=True)
            if not improved:
                break
    json.dump(dict(best=best, result={k: v for k, v in cur.items() if k != 'kw'}, target=TARGET),
              open(f"out/search_T{TARGET:.0f}{'_rest' if REST else ''}.json", "w"), indent=1)
    print("BEST", json.dumps(best), flush=True)
