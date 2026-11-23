"""Build the sized catalog: STLs, renders, and one comparison sheet (out/catalog.png)."""
import json, pickle, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely import contains_xy
from catalog import DESIGNS, thick_zone, hanging_arch, D, RF
from model import Bracket
from evaluate import evaluate, diagnostics_png, save_fig

OUT = Path(__file__).parent / "out"
STYLE_COL = {"beautiful": "#c2410c", "optimized": "#1d4ed8", "minimalist": "#374151", "organic": "#15803d"}
TITLES = {"minimal_two_bars": "Two bars", "salginatobel": "Salginatobel arch", "victorian": "Victorian cast iron",
          "forth_bridge": "Forth Bridge", "hanging_arch": "Hanging arch", "hanging_arch_rest": "Hanging arch + rest", "twin_triangle": "Twin-wall triangle",
          "gaudi_tree": "Gaudi tree", "bone": "Bone"}


def to_part(geom, t, t_hook, tol=0.05):
    from build123d import Face, Wire, Vector, extrude
    def face(poly):
        poly = poly.simplify(tol)
        ext = Wire.make_polygon([Vector(x, z, 0) for x, z in poly.exterior.coords[:-1]], close=True)
        holes = [Wire.make_polygon([Vector(x, z, 0) for x, z in r.coords[:-1]], close=True) for r in poly.interiors]
        return Face(ext, holes)
    def solid(g, h):
        out = None
        for gg in getattr(g, "geoms", [g]):
            if gg.area < 1:
                continue
            e = extrude(face(gg), amount=h)
            out = e if out is None else out + e
        return out
    return solid(geom, t) + solid(geom.intersection(thick_zone()), t_hook)


def build(name, kw):
    style, fn, rest = DESIGNS[name]
    if name.startswith("hanging_arch"):
        geom, p = hanging_arch("search_T13_rest.json" if name.endswith("rest") else "search_T15.json")
        t, th, zb = p.t, p.t_hook, (-130.0 if p.rest else p.foot_z - p.S - 6)
    else:
        kw = dict(kw); t = kw.pop("t", 12); th = kw.pop("t_hook", 16)
        geom, zb = fn(**kw), -130.0
    m = Bracket(depth=D, z_bottom=zb, h=0.4, t=t, rest=rest)
    g = m.grid
    tf = np.where(contains_xy(thick_zone(), g.xc, g.zc), th / t, 1.0)
    r = evaluate(m, contains_xy(geom, g.xc, g.zc), tf=tf)
    diagnostics_png(m, r, OUT / f"cat_{name}_diag.png")
    lim = {k: v / 9.81 for k, v in r["limits_N"].items()}
    res = dict(name=name, style=style, mass=r["mass"], kg=r["allow_N"] / 9.81, limits=lim,
               governs=min(lim, key=lim.get), t=t, t_hook=th, rest=rest,
               tip_mm_10kg=r["cases"]["uniform"]["tip_mm"] * 0.981, params=kw)
    from build123d import export_stl
    export_stl(to_part(geom, t, th), str(OUT / f"bracket_{name}.stl"))
    return geom, res


def fill_geom(ax, geom, color):
    """Fill polygons with their holes cut out (compound path)."""
    from matplotlib.path import Path as MPath
    from matplotlib.patches import PathPatch
    from shapely.geometry.polygon import orient
    for gg in getattr(geom, "geoms", [geom]):
        gg = orient(gg, 1.0)
        verts, codes = [], []
        for ring in [gg.exterior, *gg.interiors]:
            c = list(ring.coords)
            verts += c; codes += [MPath.MOVETO] + [MPath.LINETO] * (len(c) - 2) + [MPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MPath(verts, codes), facecolor=color, lw=0))


def silhouette(geom, r, path):
    """Single design drawing, transparent background, wall + slots for context."""
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    for z0, z1 in ((-135, RF), (RF + 10, 0), (10, 30)):          # slats, leaving the two slots open
        ax.fill_between([-22, 0], z0, z1, color="#9ca3af", alpha=0.45, lw=0)
    fill_geom(ax, geom, STYLE_COL[r["style"]])
    ax.set_xlim(-22, 212); ax.set_ylim(-132, 26); ax.set_aspect("equal"); ax.axis("off")
    fig.subplots_adjust(0, 0, 1, 1)
    save_fig(fig, path, dpi=100, transparent=True)


def sheet(items, path):
    n = len(items)
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axs = plt.subplots(rows, cols, figsize=(4.6 * cols, 3.9 * rows))
    for ax in np.ravel(axs)[n:]:
        ax.axis("off")
    for ax, (geom, r) in zip(np.ravel(axs), items):
        ax.axhspan(-140, 30, xmin=0, xmax=16 / 236, color="#e5e7eb", lw=0)
        ax.fill_between([-20, 0], RF, RF + 10, color="white", lw=0)
        ax.fill_between([-20, 0], 0, 10, color="white", lw=0)
        fill_geom(ax, geom, STYLE_COL[r["style"]])
        ax.set_xlim(-20, 216); ax.set_ylim(-135, 30); ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(f"{TITLES[r['name']]}  ·  {r['style']}", fontsize=12, loc="left", color=STYLE_COL[r["style"]],
                     fontweight="bold")
        ax.text(0.0, -0.06, f"{r['mass']:.0f} g PETG  →  {r['kg']:.1f} kg safe  ({r['kg'] / r['mass']:.2f} kg/g)\n"
                f"limited by {r['governs']}; {r['t']:.0f} mm wide" + ("; rests in lower slot" if r["rest"] else ""),
                transform=ax.transAxes, fontsize=9.5, va="top", color="#374151")
    fig.tight_layout()
    save_fig(fig, path, dpi=110)


if __name__ == "__main__":
    sized = json.load(open(OUT / "catalog_sized.json"))
    if (OUT / "bone_sized.json").exists():
        sized.update(json.load(open(OUT / "bone_sized.json")))
    order = ["salginatobel", "victorian", "forth_bridge", "hanging_arch", "hanging_arch_rest", "twin_triangle",
             "minimal_two_bars", "gaudi_tree", "bone"]
    items = []
    for name in order:
        if name in sized:
            kw = sized[name]["best"]
        elif name in ("hanging_arch", "bone"):
            kw = {}
        elif name == "hanging_arch_rest":
            if not (OUT / "search_T13_rest.json").exists():
                continue
            kw = {}
        else:
            continue
        if name == "bone" and not (OUT / "bone_simp.npz").exists():
            continue
        geom, res = build(name, kw)
        print(f"{name:18s} {res['mass']:5.1f} g {res['kg']:5.1f} kg {res['kg'] / res['mass']:.2f} kg/g ({res['governs']})", flush=True)
        items.append((geom, res))
        silhouette(geom, res, OUT / f"sil_{name}.png")
    pickle.dump(items, open(OUT / "catalog.pkl", "wb"))
    sheet(items, OUT / "catalog.png")
    json.dump([r for _, r in items], open(OUT / "catalog.json", "w"), indent=1, default=float)
