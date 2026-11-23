"""Browser entry point (Pyodide): pick a shelf from the capacity table and return its outline.

The geometry is bracket/shelf_geom.py -- the same code the CLI generator uses -- copied next to
this file at build time. Meshing / STL / 3MF happen in JavaScript (site/common/mesh.js).
"""
import json
from shapely.ops import unary_union
import shelf_geom as sg

_TABLE = None


def load_table(text):
    global _TABLE
    _TABLE = json.loads(text)
    return {"min_depth": _TABLE["depths"][0], "max_depth": _TABLE["depths"][-1]}


def _rings(geom, tol=0.05):
    out = []
    for g in getattr(geom, "geoms", [geom]):
        if g.area < 1:
            continue
        g = g.simplify(tol)
        out.append({"outer": [list(p) for p in g.exterior.coords[:-1]],
                    "holes": [[list(p) for p in r.coords[:-1]] for r in g.interiors]})
    return out


def generate(width, depth, load_kg, lip):
    best = sg.pick(_TABLE, width, depth, load_kg)
    if best is None:
        return json.dumps({"ok": False})
    geom, bottom = sg.design(best["name"], depth, best["S"], best["perims"])
    geom = unary_union([geom, sg.lip_profile(depth, lip)])
    minx, minz, maxx, maxz = geom.bounds
    return json.dumps({
        "ok": True, "design": best,
        "profile": _rings(geom),
        "side_lips": [{"quad": [list(p) for p in q], "x0": x0, "x1": depth} for q, x0 in sg.side_lips(width, lip)],
        "bounds": [minx, minz, maxx, maxz],
        "slot_pitch": sg.SLOT_PITCH, "slot_open": sg.SLOT_OPEN, "top": sg.TOP,
    })
