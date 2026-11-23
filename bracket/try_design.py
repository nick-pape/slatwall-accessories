import sys, time, numpy as np
from design import Params, geometry, mask, area_mass, thickness_factor
from model import Bracket
from evaluate import evaluate, summary, diagnostics_png
from PIL import Image

def run(p, h=0.4, name="arch", png=True):
    geom = geometry(p)
    m = Bracket(depth=p.depth, z_bottom=p.foot_z - p.S - 6, h=h, t=p.t)
    mk = mask(m, geom)
    t0 = time.time()
    r = evaluate(m, mk, tf=thickness_factor(m, p))
    r["geom_mass"] = area_mass(geom, p.t)
    print(summary(name, r), f"[{time.time()-t0:.0f}s]", flush=True)
    if png:
        g = m.grid
        img = np.full((g.nz, g.nx, 3), 255, np.uint8)
        f = g.field(mk.astype(float)); img[f > 0.5] = (240, 140, 50)
        wall = g.field(((g.xc < 0) & ~m.solid).astype(float)); img[wall > 0.5] = (215, 218, 224)
        Image.fromarray(img).save(f"out/{name}.png")
        diagnostics_png(m, r, f"out/{name}_diag.png")
    return r

if __name__ == "__main__":
    from dataclasses import replace
    base = Params(lace_pitch=10.0, wall=3 * 0.68)
    run(base, name="arch_b")
